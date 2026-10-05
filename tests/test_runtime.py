import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from agentkit.adapters import (ADAPTERS, effective_allowed_tools, execute,
                               execute_owned_code, normalize, persist_result, stop_on_limit,
                               structured_json_text)
from agentkit.doctor import auth_summary, clean_environment, detect_engine, owned_code_profile
from agentkit.process import ProcessOutcome, group_exists, run_process
from agentkit.redaction import redact, redacted_stream
from agentkit.runtime_contracts import (Capability, CancellationStatus, EngineCapabilities,
                                        ExecutionBoundary, ExecutionRequest, LivePolicy)
from agentkit.smoke import acceptance
from agentkit.execution_check import _provider_test_evidence

FIXTURE = str(Path(__file__).parent / 'fixtures/runtime/fake_cli.py')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-test-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def request(self, engine='codex', **kw):
        return ExecutionRequest(engine, 'fixture', 'sum synthetic input', str(self.root), **kw)

    def fixture(self, engine, scenario, **kw):
        return run_process([sys.executable, FIXTURE, engine, scenario], cwd=str(self.root),
                           env=clean_environment(), timeout=kw.pop('timeout', 3), **kw)

    def test_success_both_providers_independent_oracle(self):
        for engine in ADAPTERS:
            with self.subTest(engine=engine):
                result = normalize(self.request(engine), self.fixture(engine, 'success'))
                self.assertEqual(result.status, 'succeeded')
                self.assertTrue(acceptance(result, [17, 25])['passed'])
                self.assertEqual(result.usage.input_tokens, 12)
                self.assertIsNone(result.usage.billed_cost_usd)
                self.assertTrue(result.cancellation.leader_reaped)
                self.assertTrue(result.cancellation.process_group_gone)

    def test_self_report_success_cannot_pass_wrong_answer(self):
        for engine in ADAPTERS:
            result = normalize(self.request(engine), self.fixture(engine, 'wrong'))
            self.assertEqual(result.status, 'succeeded')
            self.assertFalse(acceptance(result, [17, 25])['passed'])

    def test_unknown_usage_is_not_zero(self):
        for engine in ADAPTERS:
            result = normalize(self.request(engine), self.fixture(engine, 'no_usage'))
            self.assertIsNone(result.usage.input_tokens)
            self.assertIsNone(result.usage.estimated_cost_usd)
            self.assertFalse(result.usage.final)

    def test_bad_streams_fail_closed(self):
        for engine in ADAPTERS:
            for scenario in ('malformed', 'truncated', 'invalid_utf8', 'no_terminal', 'duplicate'):
                with self.subTest(engine=engine, scenario=scenario):
                    result = normalize(self.request(engine), self.fixture(engine, scenario))
                    self.assertEqual(result.status, 'failed')
                    self.assertEqual(result.error_class, 'truncated_output' if scenario in ('truncated', 'no_terminal') else 'malformed_output')

    def test_nonfinite_duplicate_keys_and_wrong_shape(self):
        for raw in (b'{"type":"turn.completed","usage":{"input_tokens":NaN}}\n',
                    b'{"type":"error","type":"turn.completed"}\n', b'[]\n'):
            out = ProcessOutcome(raw, b'', 0, .01, None, CancellationStatus())
            self.assertEqual(normalize(self.request(), out).error_class, 'malformed_output')

    def test_single_json_fence_is_accepted_without_relaxing_json_validation(self):
        self.assertEqual(structured_json_text('```json\n{"verdict":"no_findings","findings":[]}\n```'),
                         {'verdict': 'no_findings', 'findings': []})
        for value in ('before ```json\n{}\n```', '```JSON\n{}\n```', '```json\n{}\n``` after',
                      '```json\n{"x":1,"x":2}\n```', '```json\nNaN\n```'):
            self.assertIsNone(structured_json_text(value))

    def test_one_prose_wrapped_json_fence_is_recovered_only_when_explicitly_allowed(self):
        wrapped = ('I prepared the requested plan.\n```json\n'
                   '{"project":"fixture","assignments":[]}\n```\n'
                   'The controller should still validate every field.')
        self.assertIsNone(structured_json_text(wrapped))
        self.assertEqual(structured_json_text(wrapped, allow_wrapping_prose=True),
                         {'project': 'fixture', 'assignments': []})
        self.assertIsNone(structured_json_text(
            wrapped + '\n```json\n{"second":true}\n```', allow_wrapping_prose=True))

    def test_structured_output_schema_reaches_each_real_adapter_request(self):
        schema = {'type': 'object', 'additionalProperties': False,
                  'required': ['answer'], 'properties': {'answer': {'type': 'string'}}}
        for engine in ('codex', 'claude'):
            with self.subTest(engine=engine):
                runtime = self.root / ('runtime-' + engine)
                runtime.mkdir()
                request = self.request(engine, output_schema=schema)
                argv = ADAPTERS[engine].argv(engine, request, runtime)
                if engine == 'codex':
                    index = argv.index('--output-schema')
                    schema_path = Path(argv[index + 1])
                    self.assertEqual(json.loads(schema_path.read_text()), schema)
                    self.assertEqual(schema_path.stat().st_mode & 0o777, 0o600)
                else:
                    index = argv.index('--json-schema')
                    self.assertEqual(json.loads(argv[index + 1]), schema)

    def test_expired_oauth_is_classified_as_authentication(self):
        result = normalize(
            self.request('claude'),
            ProcessOutcome(b'', b'Error: OAuth access token has expired', 1, .01, None,
                           CancellationStatus()))
        self.assertEqual(result.error_class, 'authentication')
        self.assertEqual(result.provider_details['authentication_failure'], 'expired')

    def test_provider_schema_rejection_is_actionable_request_failure(self):
        result = normalize(
            self.request('claude'),
            ProcessOutcome(b'', b'Error: --json-schema is not a valid JSON Schema: unknown schema',
                           1, .01, None, CancellationStatus()))
        self.assertEqual(result.error_class, 'invalid_request')

    def test_simulated_errors_both_providers(self):
        for engine in ADAPTERS:
            for category in ('authentication', 'rate_limit', 'usage_limit'):
                result = normalize(self.request(engine), self.fixture(engine, category))
                self.assertEqual(result.error_class, category)

    def test_limit_detection_stops_a_still_running_cli(self):
        for category in ('usage_limit', 'rate_limit', 'authentication'):
            out = run_process([sys.executable, FIXTURE, 'codex', category, 'wait'],
                              cwd=str(self.root), env=clean_environment(), timeout=3,
                              stop_predicate=stop_on_limit)
            self.assertEqual(out.stop_reason, category)
            self.assertLess(out.elapsed_seconds, 2)
            self.assertTrue(out.cancellation.process_group_gone)

    def test_missing_executable(self):
        out = run_process([str(self.root / 'absent')], cwd=str(self.root), env={})
        self.assertEqual(normalize(self.request(), out).error_class, 'missing_executable')

    def test_timeout_and_child_cleanup(self):
        out = self.fixture('codex', 'children', timeout=.3)
        self.assertEqual(out.stop_reason, 'timeout')
        self.assertTrue(out.cancellation.kill_sent)
        self.assertTrue(out.cancellation.leader_reaped)
        self.assertTrue(out.cancellation.process_group_gone)
        self.assertProcessExited(int((self.root / 'child.pid').read_text()))

    def assertProcessExited(self, pid):
        """An exit record still answers signal probing until its parent reaps it."""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        try:
            with open('/proc/%d/stat' % pid, 'rb') as handle:
                state = handle.read().rpartition(b')')[2].split()[0]
        except OSError:
            return
        self.assertEqual(state, b'Z', 'process %d is still running' % pid)

    def test_normal_leader_exit_still_cleans_child(self):
        out = self.fixture('claude', 'orphan')
        self.assertEqual(out.exit_code, 0)
        self.assertTrue(out.cancellation.process_group_gone)

    def test_cancellation_before_and_during_execution(self):
        for before in (True, False):
            event = threading.Event()
            if before:
                event.set()
            else:
                timer = threading.Timer(.3, event.set)
                timer.start()
                self.addCleanup(timer.join)
            out = self.fixture('claude', 'hang', cancel_event=event)
            result = normalize(self.request('claude'), out)
            self.assertEqual(result.status, 'cancelled')
            self.assertTrue(result.cancellation.requested)
            self.assertTrue(result.cancellation.process_group_gone)

    def test_output_memory_bound(self):
        out = self.fixture('codex', 'flood', max_bytes=1024)
        self.assertEqual(out.stop_reason, 'output_limit')
        self.assertEqual(len(out.stdout) + len(out.stderr), 1024)
        self.assertTrue(out.cancellation.process_group_gone)

    def test_redaction_handles_chunk_split_and_structured_values(self):
        out = self.fixture('codex', 'secrets')
        result = normalize(self.request(), out)
        folder = self.root / 'artifact'
        persist_result(folder, self.request(), result, out)
        combined = ''.join(p.read_text() for p in folder.iterdir())
        self.assertNotIn('fake-secret-value', combined)
        self.assertNotIn('sk-fake-split-value', combined)
        self.assertEqual(redact({'access_token': 'fake', 'thinking': 'private'}),
                         {'access_token': '[REDACTED]', 'thinking': '[REDACTED]'})
        self.assertNotIn('fragment', redacted_stream(b'secret=fragment', True).replace('[incomplete fragment withheld]', ''))
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        for file in folder.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            persist_result(folder, self.request(), result)

    def test_runtime_tools_violate_model_only_mode(self):
        result = normalize(self.request('claude'), self.fixture('claude', 'tools'))
        self.assertEqual(result.error_class, 'unexpected_tools')

    def test_claude_structured_output_surface_is_allowed_only_for_validated_schema(self):
        request = self.request('claude', output_schema={
            'type': 'object', 'additionalProperties': False,
            'required': ['answer'], 'properties': {'answer': {'type': 'string'}}})
        events = [
            {'type': 'system', 'subtype': 'init', 'tools': ['StructuredOutput'],
             'mcp_servers': [], 'model': 'fixture-model'},
            {'type': 'result', 'subtype': 'success', 'is_error': False,
             'structured_output': {'answer': 'fixture'}, 'usage': {}},
        ]
        raw = ''.join(json.dumps(event) + '\n' for event in events).encode()
        allowed = effective_allowed_tools(request)
        self.assertEqual(allowed, ('StructuredOutput',))
        self.assertIsNone(stop_on_limit(raw, b'', allowed))
        result = normalize(
            request, ProcessOutcome(raw, b'', 0, .01, None, CancellationStatus()))
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(result.structured_output, {'answer': 'fixture'})
        self.assertEqual(effective_allowed_tools(self.request('claude')), ())
        self.assertEqual(stop_on_limit(raw, b''), 'unexpected_tools')

    def test_tool_use_events_fail_even_without_init_advertisement(self):
        for engine, event, terminal in [
            ('codex', {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'fake'}}, {'type': 'turn.completed'}),
            ('claude', {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Bash'}]}},
             {'type': 'result', 'subtype': 'success', 'result': '{"sum":42}'})]:
            raw = (json.dumps(event) + '\n' + json.dumps(terminal) + '\n').encode()
            self.assertEqual(stop_on_limit(raw, b''), 'unexpected_tools')
            out = ProcessOutcome(raw, b'', 0, .01, None, CancellationStatus())
            self.assertEqual(normalize(self.request(engine), out).error_class, 'unexpected_tools')

    def test_owned_code_allows_only_reviewed_tool_events(self):
        request = self.request('codex', mode='owned-code')
        events = [
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'python3 -B -m unittest -v'}},
            {'type': 'turn.completed', 'usage': {}}
        ]
        raw = ''.join(json.dumps(event) + '\n' for event in events).encode()
        self.assertIsNone(stop_on_limit(raw, b'', ('Read', 'Edit', 'Write', 'Bash')))
        self.assertEqual(normalize(request, ProcessOutcome(raw, b'', 0, .01, None, CancellationStatus())).status, 'succeeded')
        events[0]['item']['type'] = 'mcp_tool_call'
        raw = ''.join(json.dumps(event) + '\n' for event in events).encode()
        self.assertEqual(stop_on_limit(raw, b'', ('Read', 'Edit', 'Write', 'Bash')),
                         'unexpected_tools')

    def test_owned_acceptance_requires_successful_provider_test_record(self):
        artifact = self.root / 'stdout.redacted.jsonl'
        failed = [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'test-1',
             'name': 'Bash', 'input': {'command': 'python3 -B -m unittest -v'}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'test-1',
             'is_error': True, 'content': 'EPERM'}]}}
        ]
        artifact.write_text(''.join(json.dumps(event) + '\n' for event in failed))
        self.assertFalse(_provider_test_evidence('claude', self.root)['passed'])
        failed[1]['message']['content'][0].update(is_error=False, content='Ran 1 test\nOK')
        artifact.write_text(''.join(json.dumps(event) + '\n' for event in failed))
        self.assertTrue(_provider_test_evidence('claude', self.root)['passed'])

    def test_owned_profile_is_narrow(self):
        workspace = self.root / 'workspace'
        runtime = self.root / 'runtime'
        denied = self.root / 'protected'
        lock = self.root / 'installation_id'
        for path in (workspace, runtime, denied):
            path.mkdir()
        lock.write_text('fixture')
        profile = owned_code_profile(runtime, workspace, (denied,), (lock,), network=True)
        self.assertIn('(deny file-write*)', profile)
        self.assertIn('(subpath ' + json.dumps(str(workspace)) + ')', profile)
        self.assertIn('(literal ' + json.dumps(str(lock)) + ')', profile)
        self.assertIn('(allow file-write* (literal "/dev/null"))', profile)
        self.assertIn('(deny file-read*', profile)
        self.assertNotIn('(allow file-write* (subpath ' + json.dumps(str(self.root)) + '))', profile)

    def test_owned_execution_routes_shell_temporary_files_into_runtime(self):
        from agentkit.doctor import COMPATIBLE, REQUIRED
        workspace = self.root / 'workspace-owned'
        output = self.root / 'owned-result'
        protected = self.root / 'protected-owned'
        home = self.root / 'home'
        workspace.mkdir()
        protected.mkdir()
        (home / '.codex').mkdir(parents=True)
        (home / '.codex/installation_id').write_text('fixture-installation-id')
        request = ExecutionRequest('codex', 'owned-temp', 'fixture task', str(workspace),
                                   mode='owned-code')
        boundary = ExecutionBoundary(str(workspace), (str(protected),))
        cap = EngineCapabilities(
            'codex', '/fake/codex', COMPATIBLE['codex'], 'fixture-hash',
            {flag: Capability('verified', 'fixture') for flag in REQUIRED['codex']},
            Capability('verified', 'fixture subscription'), authentication_mode='subscription')

        def launch(argv, **kwargs):
            self.assertEqual(argv[0], '/usr/bin/sandbox-exec')
            self.assertIn('(allow file-write* (literal "/dev/null"))', argv[2])
            self.assertTrue(kwargs['env']['TMPPREFIX'].startswith(kwargs['env']['TMPDIR'] + '/'))
            event = b'{"type":"turn.completed","usage":{}}\n'
            return ProcessOutcome(event, b'', 0, .01, None, CancellationStatus())

        with patch('agentkit.adapters.native_sandbox_capability',
                   return_value=Capability('verified', 'fixture')), \
             patch('agentkit.adapters.detect_engine', return_value=cap), \
             patch('agentkit.adapters.run_process', side_effect=launch), \
             patch.object(Path, 'home', return_value=home):
            result = execute_owned_code(request, output, boundary,
                                        policy=LivePolicy(True, 'fixture only'))
        self.assertEqual(result.status, 'succeeded')

    def test_request_rejects_policy_injection_and_invalid_bounds(self):
        args = dict(engine='codex', task_id='fixture', prompt='test', cwd=str(self.root))
        for key, value in [('timeout_seconds', float('nan')), ('timeout_seconds', -1),
                           ('max_output_bytes', True), ('schema_version', 2), ('cwd', 'relative')]:
            with self.assertRaises(ValueError):
                ExecutionRequest.from_dict(dict(args, **{key: value}))
        with self.assertRaises(TypeError):
            ExecutionRequest.from_dict(dict(args, subscription_smoke_authorized=True))
        for schema in ([], {'value': float('nan')}, {'value': object()}):
            with self.assertRaisesRegex(ValueError, 'output schema'):
                ExecutionRequest.from_dict(dict(args, output_schema=schema))

    def test_model_and_supported_effort_are_explicit_cli_arguments(self):
        runtime = self.root / 'runtime-model-options'
        runtime.mkdir()
        claude = self.request('claude', model='claude-fixture-model', effort='high')
        argv = ADAPTERS['claude'].argv('claude', claude, runtime)
        self.assertEqual(argv[argv.index('--model') + 1], 'claude-fixture-model')
        self.assertEqual(argv[argv.index('--effort') + 1], 'high')
        codex = self.request('codex', model='codex-fixture-model')
        argv = ADAPTERS['codex'].argv('codex', codex, runtime)
        self.assertEqual(argv[:4], ['codex', '--no-daemon', 'exec', '--strict-config'])
        self.assertEqual(argv[argv.index('--model') + 1], 'codex-fixture-model')
        self.assertNotIn('--effort', argv)
        with self.assertRaisesRegex(ValueError, 'unsupported by the tested Codex'):
            self.request('codex', effort='high')
        with self.assertRaisesRegex(ValueError, 'unsupported Claude effort'):
            self.request('claude', effort='ultra')
        self.assertEqual(self.request('claude', max_generated_output_tokens=8192).
                         max_generated_output_tokens, 8192)
        self.assertEqual(self.request('claude', max_generated_output_tokens=65536).
                         max_generated_output_tokens, 65536)
        for value in (True, 0, -1, float('inf')):
            with self.assertRaisesRegex(ValueError, 'generated-output token allocation'):
                self.request('claude', max_generated_output_tokens=value)
        with self.assertRaisesRegex(ValueError, 'generated-output token allocation'):
            self.request('codex', max_generated_output_tokens=512)

    def test_generated_output_limit_is_not_misclassified_as_rate_or_usage_limit(self):
        text = ('rate_limit_event status allowed overageDisabledReason out_of_credits\n'
                "API Error: response exceeded the 512 output token maximum. "
                'Set CLAUDE_CODE_MAX_OUTPUT_TOKENS.')
        from agentkit.adapters import error_class
        self.assertEqual(error_class(text), 'output_limit')

    def test_live_is_default_denied_without_even_doctor(self):
        with patch('agentkit.adapters.native_sandbox_capability', side_effect=AssertionError('must not probe')):
            result = execute(self.request(), self.root / 'blocked')
        self.assertEqual(result.status, 'blocked')
        self.assertEqual(result.error_class, 'billing_policy')

    def test_existing_artifacts_reject_before_launch(self):
        with patch('agentkit.adapters.native_sandbox_capability', side_effect=AssertionError('must not probe')):
            with self.assertRaises(ValueError):
                execute(self.request(), self.root, policy=LivePolicy(True))

    def test_guard_failure_is_visible(self):
        out = ProcessOutcome(b'', b'failed to initialize in-process app-server client: Operation not permitted', 1, .1, None, CancellationStatus())
        self.assertEqual(normalize(self.request(), out).error_class, 'guard_denied')

    def test_unsupported_modes_and_sandbox_never_fall_back(self):
        for mode in ('owned-code', 'untrusted'):
            result = execute(self.request(mode=mode), self.root / mode, policy=LivePolicy(True))
            self.assertEqual(result.error_class, 'unsupported_isolation')
        with patch('agentkit.adapters.native_sandbox_capability', return_value=Capability('unavailable', 'fixture unavailable')):
            result = execute(self.request(), self.root / 'sandbox', policy=LivePolicy(True))
        self.assertEqual(result.error_class, 'sandbox_unavailable')

    def test_missing_version_and_non_subscription_preflight_fail_closed(self):
        from agentkit.doctor import COMPATIBLE, REQUIRED
        for case in ('missing_executable', 'incompatible_cli', 'authentication'):
            cap = EngineCapabilities('codex', None if case == 'missing_executable' else '/fake/cli',
                  'unreviewed' if case == 'incompatible_cli' else COMPATIBLE['codex'], 'fixture',
                  {flag: Capability('verified', 'fixture') for flag in REQUIRED['codex']},
                  Capability('verified', 'fixture API key'), authentication_mode='api-key')
            with patch('agentkit.adapters.native_sandbox_capability', return_value=Capability('verified', 'fixture')), \
                 patch('agentkit.adapters.detect_engine', return_value=cap), \
                 patch('agentkit.adapters.run_process', side_effect=AssertionError('must not infer')):
                result = execute(self.request(), self.root / case, policy=LivePolicy(True))
            self.assertEqual(result.error_class, case)

    def test_codex_current_contract_requires_daemon_and_strict_config_controls(self):
        from agentkit.doctor import COMPATIBLE, REQUIRED, compatible_version
        self.assertEqual(COMPATIBLE['codex'], '0.160.0')
        self.assertTrue(compatible_version('codex', '0.159.3'))
        self.assertTrue(compatible_version('codex', '0.160.0'))
        self.assertFalse(compatible_version('codex', '0.160.1'))
        self.assertIn('--no-daemon', REQUIRED['codex'])
        self.assertIn('--strict-config', REQUIRED['codex'])
        request = self.request('codex', mode='owned-code',
                               capability_profile='web-product-implementation')
        argv = ADAPTERS['codex'].argv('/fixture/codex', request, self.root)
        self.assertEqual(argv[:4], ['/fixture/codex', '--no-daemon', 'exec', '--strict-config'])
        self.assertIn('--ignore-user-config', argv)
        self.assertIn('--ignore-rules', argv)

    def test_environment_does_not_inherit_credentials_or_loaders(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'fake', 'OPENAI_API_KEY': 'fake',
                                     'NODE_OPTIONS': 'fake', 'CLAUDE_CODE_USE_BEDROCK': '1'}):
            env = clean_environment()
        for key in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'NODE_OPTIONS', 'CLAUDE_CODE_USE_BEDROCK'):
            self.assertNotIn(key, env)

    def test_doctor_absent_cli(self):
        with patch('agentkit.doctor.shutil.which', return_value=None):
            cap = detect_engine('codex', Capability('unknown', 'fixture'))
        self.assertIsNone(cap.version)
        self.assertEqual(cap.authentication.state, 'unavailable')

    def test_doctor_combines_codex_root_and_exec_help(self):
        from agentkit.doctor import REQUIRED
        executable = self.root / 'codex-fixture'
        executable.write_bytes(b'fixture')
        for version in ('0.159.3', '0.160.0'):
            with self.subTest(version=version):
                outcomes = [
                    ProcessOutcome(('codex-cli ' + version + '\n').encode(), b'', 0, .01,
                                   None, CancellationStatus()),
                    ProcessOutcome((' '.join(flag for flag in REQUIRED['codex']
                                              if flag != '--no-daemon') + '\n').encode(),
                                   b'', 0, .01, None, CancellationStatus()),
                    ProcessOutcome(b'--no-daemon\n', b'', 0, .01, None,
                                   CancellationStatus()),
                ]
                with patch('agentkit.doctor.shutil.which', return_value=str(executable)), \
                     patch('agentkit.doctor.run_process', side_effect=outcomes):
                    cap = detect_engine('codex', Capability('unknown', 'fixture'))
                self.assertEqual(cap.version, version)
                self.assertTrue(all(cap.features[flag].state == 'verified'
                                    for flag in REQUIRED['codex']))
                self.assertEqual(cap.features['tested_version'].state, 'verified')

    def test_auth_status_filters_identifiers(self):
        raw = json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty',
                          'subscriptionType': 'max', 'email': 'fake@example.test', 'access_token': 'fake'}).encode()
        cap, mode, details = auth_summary('claude', ProcessOutcome(raw, b'', 0, .01, None, CancellationStatus()))
        self.assertEqual(mode, 'subscription')
        self.assertEqual(details, {'subscription_type': 'max'})

    def test_adapter_arguments_disable_fallback_and_tools(self):
        for engine in ADAPTERS:
            args = ADAPTERS[engine].argv('/fake/cli', self.request(engine), self.root)
            self.assertNotIn('--dangerously-skip-permissions', args)
            self.assertNotIn('--fallback-model', args)
            self.assertNotIn('--bare', args)
            if engine == 'codex':
                self.assertFalse(any(x.startswith('model_providers.openai.') for x in args))
                self.assertIn('features.shell_tool=false', args)
            else:
                self.assertEqual(args[args.index('--tools') + 1], '')

    def test_owned_adapter_arguments_enable_bounded_tools(self):
        from agentkit.runtime_contracts import ExecutionBoundary
        workspace = self.root / 'workspace'
        workspace.mkdir()
        boundary = ExecutionBoundary(str(workspace), (str(self.root / 'canary'),))
        for engine in ADAPTERS:
            request = ExecutionRequest(engine, 'owned', 'fixture task', str(workspace), mode='owned-code')
            args = ADAPTERS[engine].argv('/fake/cli', request, self.root, boundary,
                                         session_id='00000000-0000-4000-8000-000000000000')
            self.assertNotIn('--dangerously-skip-permissions', args)
            if engine == 'codex':
                self.assertEqual(args[args.index('--sandbox') + 1], 'danger-full-access')
                self.assertNotIn('features.shell_tool=false', args)
            else:
                self.assertEqual(args[args.index('--tools') + 1], 'Read,Edit,Write,Bash')
                settings = json.loads(args[args.index('--settings') + 1])
                self.assertFalse(settings['sandbox']['enabled'])
                self.assertFalse(settings['sandbox']['failIfUnavailable'])
                self.assertFalse(settings['sandbox']['allowUnsandboxedCommands'])
                self.assertTrue(settings['permissions']['blockReadsOutsideWorkingDirectories'])
                self.assertNotIn('Bash', settings['permissions']['allow'])
                self.assertIn('Bash(python3 -B -m unittest*)', settings['permissions']['allow'])
                self.assertIn('--session-id', args)

    def test_allowed_rate_metadata_and_identifier_digits_are_not_errors(self):
        event = {'type': 'rate_limit_event', 'rate_limit_info': {'status': 'allowed',
                 'overageDisabledReason': 'out_of_credits', 'isUsingOverage': False}, 'session_id': '429-401'}
        self.assertIsNone(stop_on_limit((json.dumps(event) + '\n').encode(), b''))
        event['rate_limit_info']['status'] = 'rejected'
        self.assertEqual(stop_on_limit((json.dumps(event) + '\n').encode(), b''), 'usage_limit')

    def test_reported_retries_and_effective_tools_stop_early(self):
        self.assertIsNone(stop_on_limit(b'', b'Reconnecting... 1/5'))
        raw = b'{"type":"system","subtype":"init","tools":["Bash"]}\n'
        self.assertEqual(stop_on_limit(raw, b''), 'unexpected_tools')
        terminal = raw + b'{"type":"result","subtype":"error_during_execution","is_error":true}\n'
        outcome = ProcessOutcome(terminal, b'', 143, .01, 'unexpected_tools',
                                 CancellationStatus(requested=True, reason='unexpected_tools'))
        self.assertEqual(normalize(self.request('claude'), outcome).error_class,
                         'unexpected_tools')

    def test_stopped_authentication_launch_preserves_complete_terminal_usage(self):
        events = [
            {'type': 'system', 'subtype': 'api_retry', 'attempt': 1,
             'error_status': 401},
            {'type': 'system', 'subtype': 'api_retry', 'attempt': 2,
             'error_status': 401},
            {'type': 'result', 'subtype': 'success', 'is_error': True,
             'result': 'Failed to authenticate. API Error: 401', 'num_turns': 1,
             'usage': {'input_tokens': 0, 'output_tokens': 0,
                       'cache_read_input_tokens': 0,
                       'cache_creation_input_tokens': 0},
             'total_cost_usd': 0, 'modelUsage': {}}]
        raw = ''.join(json.dumps(event) + '\n' for event in events).encode()
        outcome = ProcessOutcome(raw, b'', 1, .1, 'authentication',
                                 CancellationStatus())
        result = normalize(self.request('claude'), outcome)
        self.assertEqual((result.status, result.error_class),
                         ('failed', 'authentication'))
        self.assertEqual((result.usage.input_tokens, result.usage.output_tokens), (0, 0))
        self.assertEqual(result.usage.estimated_cost_usd, 0)
        self.assertEqual(result.provider_details['observed_retry_events'], 2)
        self.assertEqual(result.provider_details['reported_turns'], 1)

    @unittest.skipUnless(sys.platform == 'darwin',
                         'the managed launch wraps the tested macOS Seatbelt profile')
    def test_managed_adapter_pipeline_with_fake_subscription_cli(self):
        from agentkit.doctor import COMPATIBLE, REQUIRED
        for engine in ADAPTERS:
            cwd = self.root / engine
            cwd.mkdir()
            request = ExecutionRequest(
                engine, 'managed-fixture', 'synthetic', str(cwd),
                capability_profile='smoke-model-only',
                max_generated_output_tokens=512 if engine == 'claude' else None)
            cap = EngineCapabilities(engine, '/fake/cli', COMPATIBLE[engine], 'fixture-hash',
                  {flag: Capability('verified', 'fixture') for flag in REQUIRED[engine]},
                  Capability('verified', 'fixture subscription'), authentication_mode='subscription')
            actual_transport = run_process
            def simulated_launch(argv, **kw):
                self.assertEqual(argv[0], '/usr/bin/sandbox-exec')
                self.assertIn('(deny file-write*)', argv[2])
                self.assertNotIn('OPENAI_API_KEY', kw['env'])
                if engine == 'claude':
                    self.assertEqual(kw['env']['CLAUDE_CODE_MAX_RETRIES'], '0')
                    self.assertEqual(kw['env']['CLAUDE_CODE_MAX_TURNS'], '1')
                    self.assertEqual(kw['env']['CLAUDE_CODE_MAX_OUTPUT_TOKENS'], '512')
                return actual_transport([sys.executable, FIXTURE, engine, 'success'], **kw)
            with patch('agentkit.adapters.native_sandbox_capability', return_value=Capability('verified', 'fixture')), \
                 patch('agentkit.adapters.detect_engine', return_value=cap), \
                 patch('agentkit.adapters.run_process', side_effect=simulated_launch):
                result = execute(request, self.root / (engine + '-result'), policy=LivePolicy(True, 'fixture only'))
            self.assertTrue(acceptance(result, [17, 25])['passed'])
            self.assertTrue((self.root / (engine + '-result') / 'stdout.redacted.jsonl').is_file())
            launch = result.provider_details['launch_configuration']
            self.assertFalse(launch['environment_values_recorded'])
            self.assertEqual(launch['provider_limit_environment']
                             ['CLAUDE_CODE_MAX_OUTPUT_TOKENS'],
                             'set' if engine == 'claude' else 'unset')


class ProcessGroupLivenessTests(unittest.TestCase):
    """An exited-but-unreaped member is contained, not an outstanding process."""

    @unittest.skipUnless(os.path.isdir('/proc'), 'requires a procfs host')
    def test_unreaped_exited_group_member_is_not_reported_live(self):
        process = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
        try:
            for _ in range(200):
                if os.path.exists('/proc/%d/stat' % process.pid):
                    with open('/proc/%d/stat' % process.pid, 'rb') as handle:
                        if handle.read().rpartition(b')')[2].split()[0] == b'Z':
                            break
                time.sleep(0.01)
            else:
                self.skipTest('the child was reaped before it could be observed')
            os.killpg(process.pid, 0)  # Still addressable by signal probing.
            self.assertFalse(group_exists(process.pid))
        finally:
            process.wait(timeout=5)
        self.assertFalse(group_exists(process.pid))


if __name__ == '__main__':
    unittest.main()
