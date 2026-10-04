import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentkit.adapters import execute_owned_code
from agentkit.doctor import COMPATIBLE, REQUIRED, clean_environment
from agentkit.process import ProcessOutcome
from agentkit.runtime_contracts import (CancellationStatus, Capability, EngineCapabilities,
                                        ExecutionBoundary, ExecutionRequest, LivePolicy)
from agentkit.runtime_readiness import (RuntimeReadiness, RuntimeRequirement,
                                        evaluate_readiness, prepared_environment,
                                        requirement_for_profile)


class RuntimeReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-runtime-readiness-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = self.root / 'worker'
        self.workspace.mkdir()
        self.guard = self.root / 'guard.py'
        self.guard.write_text(
            'import os, sys\n'
            'os.execv(sys.argv[1], sys.argv[1:])\n')

    def guard_prefix(self):
        return (sys.executable, str(self.guard))

    def evaluate(self, requirement):
        env = prepared_environment(clean_environment(), requirement)
        return evaluate_readiness(requirement, env, self.workspace, self.guard_prefix())

    def test_versioned_records_round_trip_and_reject_unknown_fields(self):
        requirement = RuntimeRequirement(
            'node', 'web-product-implementation', '/approved/bin/node',
            (('node', '--check'),), 'v22.19.0', '0' * 64)
        self.assertEqual(RuntimeRequirement.from_dict(requirement.to_dict()), requirement)
        readiness = RuntimeReadiness(
            'node', 'web-product-implementation', '/approved/bin/node', '0' * 64,
            'v22.19.0', 'verified', 'fixture observation', (('node', '--check'),))
        self.assertEqual(RuntimeReadiness.from_dict(readiness.to_dict()), readiness)
        bad = requirement.to_dict()
        bad['approval'] = True
        with self.assertRaises(TypeError):
            RuntimeRequirement.from_dict(bad)
        with self.assertRaisesRegex(ValueError, 'schema version'):
            RuntimeRequirement.from_dict({**requirement.to_dict(), 'schema_version': 2})

    @unittest.skipUnless(shutil.which('node'), 'installed Node is required for host runtime fixture')
    def test_approved_node_is_visible_in_the_prepared_worker_environment(self):
        node = Path(shutil.which('node')).resolve()
        version = subprocess.run([str(node), '--version'], text=True, check=True,
                                 stdout=subprocess.PIPE).stdout.strip()
        digest = hashlib.sha256(node.read_bytes()).hexdigest()
        requirement = requirement_for_profile(
            'web-product-implementation', executable=str(node), version_evidence=version,
            expected_executable_sha256=digest)
        env = prepared_environment({**clean_environment(), 'PATH': '/untrusted/bin'}, requirement)
        self.assertEqual(env['PATH'].split(os.pathsep),
                         [str(node.parent), '/usr/bin', '/bin'])
        readiness = evaluate_readiness(requirement, env, self.workspace, self.guard_prefix())
        self.assertEqual(readiness.state, 'verified')
        self.assertEqual(Path(readiness.resolved_path), node)
        self.assertEqual(readiness.executable_sha256, digest)
        self.assertEqual(readiness.version, version)

    def test_missing_and_hash_tampered_node_fail_closed_without_fallback(self):
        missing = RuntimeRequirement(
            'node', 'web-product-implementation', str(self.root / 'missing' / 'node'),
            (('node', '--check'),))
        self.assertEqual(self.evaluate(missing).state, 'unavailable')

        bindir = self.root / 'bin'
        bindir.mkdir()
        node = bindir / 'node'
        node.write_text('#!/bin/sh\nprintf "v1.0.0\\n"\n')
        node.chmod(0o700)
        requirement = RuntimeRequirement(
            'node', 'web-product-implementation', str(node), (('node', '--check'),),
            'v1.0.0', '0' * 64)
        with patch('agentkit.runtime_readiness.run_process',
                   side_effect=AssertionError('hash mismatch must block before execution')):
            readiness = self.evaluate(requirement)
        self.assertEqual(readiness.state, 'unavailable')
        self.assertIn('hash differs', readiness.evidence)

    def test_commands_outside_the_selected_profile_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside the capability profile'):
            RuntimeRequirement(
                'node', 'web-product-implementation', '/approved/bin/node',
                (('node', '-e'),))
        with self.assertRaisesRegex(ValueError, 'declared runtime'):
            RuntimeRequirement(
                'node', 'web-product-implementation', '/approved/bin/node',
                (('python3', '-c'),))

    def test_existing_python_capability_is_prepared_and_probed(self):
        python = Path(shutil.which('python3')).resolve()
        requirement = requirement_for_profile('code-implementation', executable=str(python))
        readiness = self.evaluate(requirement)
        self.assertEqual(readiness.state, 'verified')
        self.assertEqual(Path(readiness.resolved_path), python)
        self.assertTrue(readiness.version.startswith('Python 3.'))
        self.assertEqual(readiness.approved_command_prefixes,
                         (('python3', '-B', '-m', 'unittest'),))

    @unittest.skipUnless(shutil.which('node'), 'installed Node is required for adapter boundary fixture')
    def test_real_owned_code_request_probes_node_before_stubbed_provider_transport(self):
        node = Path(shutil.which('node')).resolve()
        digest = hashlib.sha256(node.read_bytes()).hexdigest()
        version = subprocess.run([str(node), '--version'], text=True, check=True,
                                 stdout=subprocess.PIPE).stdout.strip()
        requirement = requirement_for_profile(
            'web-product-implementation', executable=str(node), version_evidence=version,
            expected_executable_sha256=digest)
        denied = self.root / 'controller-secret'
        denied.write_text('fake secret')
        boundary = ExecutionBoundary(str(self.workspace), (str(denied), str(self.root / '.git')))
        request = ExecutionRequest(
            'codex', 'node-worker', 'Inspect and validate game.js.', str(self.workspace),
            mode='owned-code', capability_profile='web-product-implementation')
        cap = EngineCapabilities(
            'codex', '/fixture/codex', COMPATIBLE['codex'], 'fixture-cli-hash',
            {flag: Capability('verified', 'fixture') for flag in REQUIRED['codex']},
            Capability('verified', 'fixture subscription'), authentication_mode='subscription')
        provider_launches = []

        def probe_with_disposable_guard(req, env, workspace, requested_guard, **kwargs):
            self.assertEqual(requested_guard[:2], ('/usr/bin/sandbox-exec', '-p'))
            self.assertIn('(deny file-read*', requested_guard[2])
            self.assertIn(str(denied), requested_guard[2])
            return evaluate_readiness(req, env, workspace, self.guard_prefix())

        def external_transport(argv, **kwargs):
            self.assertEqual(argv[3:7],
                             ['/fixture/codex', '--no-daemon', 'exec', '--strict-config'])
            provider_launches.append((argv, kwargs))
            stdout = (json.dumps({'type': 'thread.started', 'thread_id': 'fixture'}) + '\n' +
                      json.dumps({'type': 'item.completed', 'item': {
                          'type': 'agent_message', 'text': 'done'}}) + '\n' +
                      json.dumps({'type': 'turn.completed', 'usage': {}}) + '\n').encode()
            return ProcessOutcome(stdout, b'', 0, .01, None, CancellationStatus())

        with patch('agentkit.adapters.native_sandbox_capability',
                   return_value=Capability('verified', 'fixture guard')), \
             patch('agentkit.adapters.detect_engine', return_value=cap), \
             patch('agentkit.adapters.evaluate_readiness', side_effect=probe_with_disposable_guard), \
             patch('agentkit.adapters.run_process', side_effect=external_transport), \
             patch('agentkit.adapters._file_fingerprint',
                   return_value={'sha256': 'fixture', 'size': 1, 'mode': '0o600'}):
            result = execute_owned_code(
                request, self.root / 'evidence', boundary,
                policy=LivePolicy(True, 'fixture authorization'),
                runtime_requirement=requirement)
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(len(provider_launches), 1)
        argv, kwargs = provider_launches[0]
        self.assertEqual(argv[:2], ['/usr/bin/sandbox-exec', '-p'])
        self.assertEqual(kwargs['env']['PATH'].split(os.pathsep),
                         [str(node.parent), '/usr/bin', '/bin'])
        self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
        self.assertEqual(result.provider_details['runtime_readiness']['state'], 'verified')
        self.assertEqual(result.provider_details['runtime_readiness']['executable_sha256'], digest)


if __name__ == '__main__':
    unittest.main()
