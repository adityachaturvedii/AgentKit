#!/usr/bin/env python3
"""One authorized six-launch direct-versus-adapter integration checkpoint."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentkit.adapters import (ADAPTERS, execute, execute_owned_code, normalize,
                               persist_result, stop_on_limit)
from agentkit.doctor import (clean_environment, owned_code_profile,
                             readonly_profile)
from agentkit.process import run_process
from agentkit.redaction import redact
from agentkit.resource_policy import capability_profile, resolve_role_resources
from agentkit.runtime_contracts import ExecutionBoundary, ExecutionRequest, LivePolicy


EXECUTABLE_REVISION = 'a0f2906b59d7adf0858c1749228a5b2d815ea0c6'
MAX_LAUNCHES = 6
OVERALL_SECONDS = 1200.0
POLICY = LivePolicy(True, 'Authorized six-launch subscription integration checkpoint; no game inference.')
ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
started = time.monotonic()
deadline = started + OVERALL_SECONDS
launches = []


def write_json(name, value):
    target = ROOT / name
    target.write_text(json.dumps(redact(value), indent=2, sort_keys=True, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(root).rglob('*'))
            if path.is_file() and path.name != 'manifest.json'}


def remaining_timeout(role):
    remaining = deadline - time.monotonic()
    if remaining <= 5:
        raise RuntimeError('overall checkpoint deadline exhausted before launch')
    configured = resolve_role_resources(role)['timeout_seconds']['value']
    return min(configured, remaining - 2)


def record(label, kind, result, accepted, detail):
    launches.append({
        'ordinal': len(launches) + 1,
        'label': label,
        'kind': kind,
        'engine': result.engine,
        'status': result.status,
        'error_class': result.error_class,
        'elapsed_seconds': result.elapsed_seconds,
        'accepted': accepted,
        'acceptance': detail,
        'usage': asdict(result.usage),
        'execution_counts': result.provider_details.get('execution_counts', {
            'cli_launches': 1, 'provider_requests': None, 'turns': None}),
    })
    write_json('checkpoint-progress.json', {
        'executable_revision': EXECUTABLE_REVISION,
        'launches': launches,
        'elapsed_seconds': time.monotonic() - started,
        'remaining_seconds': max(0, deadline - time.monotonic()),
    })
    if len(launches) > MAX_LAUNCHES:
        raise RuntimeError('launch budget exceeded')
    if result.error_class in ('usage_limit', 'rate_limit'):
        raise RuntimeError('provider limit reported; checkpoint stopped without retry')


def direct_codex(request, output):
    executable = shutil.which('codex')
    if not executable:
        raise RuntimeError('Codex executable unavailable')
    install_id = Path.home() / '.codex' / 'installation_id'
    if not install_id.is_file() or install_id.is_symlink():
        raise RuntimeError('Codex startup state unavailable')
    before = sha(install_id)
    with tempfile.TemporaryDirectory(prefix='agentkit-direct-codex-') as tmp:
        runtime = Path(tmp).resolve()
        settings = {
            'forced_login_method': '"chatgpt"',
            'approval_policy': '"never"',
            'model_provider': '"openai"',
            'web_search': '"disabled"',
            'shell_environment_policy.inherit': '"none"',
            'sqlite_home': json.dumps(str(runtime)),
            'history.persistence': '"none"',
            'log_dir': json.dumps(str(runtime)),
            'apps._default.enabled': 'false',
            'features.shell_tool': 'false',
            'features.plugins': 'false',
            'features.apps': 'false',
            'features.browser_use': 'false',
            'features.computer_use': 'false',
            'features.multi_agent': 'false',
            'features.memories': 'false',
        }
        argv = [executable, 'exec', '--json', '--ephemeral', '--ignore-user-config',
                '--ignore-rules', '--sandbox', 'read-only', '--skip-git-repo-check',
                '--color', 'never', '-C', request.cwd]
        for key, value in settings.items():
            argv.extend(['-c', key + '=' + value])
        if request.model:
            argv.extend(['--model', request.model])
        argv.append('-')
        env = clean_environment()
        env['TMPDIR'] = str(runtime)
        prefix = ['/usr/bin/sandbox-exec', '-p', readonly_profile(
            runtime, network=True, literal_write_paths=(install_id,))]
        outcome = run_process(
            prefix + argv, cwd=request.cwd, env=env, stdin=request.prompt.encode(),
            timeout=request.timeout_seconds, max_bytes=request.max_output_bytes,
            stop_predicate=lambda stdout, stderr: stop_on_limit(stdout, stderr, ()))
        result = normalize(request, outcome)
        result.provider_details.update({
            'version': '0.154.0',
            'authentication': 'subscription-reported',
            'managed_mode': 'direct-external-seatbelt-model-only',
            'capability_profile': request.capability_profile,
            'resource_resolution': request.resource_resolution,
            'execution_counts': {'cli_launches': 1, 'provider_requests': None,
                                 'turns': None},
            'launch_configuration': {
                'argv': redact(prefix + argv),
                'environment_keys': sorted(env),
                'provider_limit_environment': {
                    key: 'set' if key in env else 'unset' for key in (
                        'CLAUDE_CODE_MAX_OUTPUT_TOKENS', 'CLAUDE_CODE_MAX_TURNS',
                        'CLAUDE_CODE_MAX_RETRIES')},
                'environment_values_recorded': False,
            },
            'installation_id_unchanged': before == sha(install_id),
        })
        return persist_result(output, request, result, outcome)


def direct_claude_owned(request, output, boundary):
    executable = shutil.which('claude')
    if not executable:
        raise RuntimeError('Claude executable unavailable')
    workspace = Path(request.cwd).resolve()
    denied = tuple(Path(path).resolve() for path in boundary.denied_read_paths)
    selected = capability_profile(request.capability_profile, request.mode)
    session_parent = Path.home() / '.claude' / 'session-env'
    if not session_parent.is_dir() or session_parent.is_symlink():
        raise RuntimeError('Claude startup state unavailable')
    session_id = str(uuid.uuid4())
    session_path = session_parent / session_id
    with tempfile.TemporaryDirectory(prefix='agentkit-direct-claude-') as tmp:
        runtime = Path(tmp).resolve()
        settings = {
            'disableAllHooks': True,
            'sandbox': {
                'enabled': False, 'failIfUnavailable': False,
                'allowUnsandboxedCommands': False, 'excludedCommands': [],
                'filesystem': {'disabled': False,
                               'denyRead': list(boundary.denied_read_paths)},
                'network': {'allowedDomains': [], 'allowLocalBinding': False}},
            'permissions': {
                'defaultMode': 'dontAsk',
                'blockReadsOutsideWorkingDirectories': True,
                'allow': [tool for tool in selected.tools if tool != 'Bash'] +
                         list(selected.bash_rules),
                'deny': ['WebFetch', 'WebSearch', 'Agent']},
        }
        argv = [executable, '--print', '--output-format', 'stream-json', '--verbose',
                '--safe-mode', '--setting-sources', '', '--settings', json.dumps(settings),
                '--tools', ','.join(selected.tools), '--strict-mcp-config', '--mcp-config',
                '{"mcpServers":{}}', '--disable-slash-commands',
                '--no-session-persistence', '--no-chrome', '--permission-mode', 'dontAsk',
                '--session-id', session_id]
        if request.model:
            argv.extend(['--model', request.model])
        if request.effort:
            argv.extend(['--effort', request.effort])
        env = clean_environment()
        env.update(TMPDIR=str(runtime), TMPPREFIX=str(runtime / 'zsh-tmp-'),
                   PYTHONDONTWRITEBYTECODE='1', CLAUDE_CODE_TMPDIR=str(runtime),
                   CLAUDE_TMPDIR=str(runtime))
        outer = owned_code_profile(runtime, workspace, denied, (session_path,), network=True)
        prefix = ['/usr/bin/sandbox-exec', '-p', outer]
        outcome = run_process(
            prefix + argv, cwd=str(workspace), env=env, stdin=request.prompt.encode(),
            timeout=request.timeout_seconds, max_bytes=request.max_output_bytes,
            stop_predicate=lambda stdout, stderr: stop_on_limit(
                stdout, stderr, selected.tools))
        result = normalize(request, outcome)
        result.provider_details.update({
            'version': '2.1.220',
            'authentication': 'subscription-reported',
            'managed_mode': 'direct-external-seatbelt-owned-code',
            'capability_profile': selected.profile_id,
            'resource_resolution': request.resource_resolution,
            'execution_counts': {'cli_launches': 1, 'provider_requests': None,
                                 'turns': None},
            'launch_configuration': {
                'argv': redact(prefix + argv),
                'environment_keys': sorted(env),
                'provider_limit_environment': {
                    key: 'set' if key in env else 'unset' for key in (
                        'CLAUDE_CODE_MAX_OUTPUT_TOKENS', 'CLAUDE_CODE_MAX_TURNS',
                        'CLAUDE_CODE_MAX_RETRIES')},
                'environment_values_recorded': False,
            },
        })
        persisted = persist_result(output, request, result, outcome)
    if session_path.exists():
        shutil.rmtree(session_path)
    return persisted


def plan_acceptance(result):
    value = result.structured_output
    required = {'objective', 'requirements', 'assumptions', 'acceptance',
                'assignments', 'dependencies', 'integration_strategy',
                'verification_requirements', 'review_requirements'}
    passed = (result.status == 'succeeded' and isinstance(value, dict) and
              set(value) == required and isinstance(value['requirements'], list) and
              len(value['requirements']) >= 4 and isinstance(value['acceptance'], list) and
              len(value['acceptance']) >= 5 and isinstance(value['assignments'], list) and
              1 <= len(value['assignments']) <= 2 and
              len(json.dumps(value, sort_keys=True).encode()) >= 900)
    return passed, {
        'controller_validated_shape': passed,
        'serialized_bytes': (len(json.dumps(value, sort_keys=True).encode())
                             if isinstance(value, dict) else None),
        'requirements': len(value.get('requirements', [])) if isinstance(value, dict) else None,
        'acceptance': len(value.get('acceptance', [])) if isinstance(value, dict) else None,
    }


def seed_implementation(workspace):
    workspace.mkdir(mode=0o700)
    (workspace / 'README.md').write_text('# Integration fixture\n')
    (workspace / 'test_widget.py').write_text(
        'import unittest\nfrom widget import describe\n\n'
        'class WidgetTests(unittest.TestCase):\n'
        '    def test_description(self):\n'
        '        self.assertEqual(describe(), "portable agentkit")\n\n'
        'if __name__ == "__main__": unittest.main()\n')
    return {path.name: sha(path) for path in workspace.iterdir() if path.is_file()}


def implementation_acceptance(workspace, before):
    current = {path.name: sha(path) for path in workspace.iterdir() if path.is_file()}
    run = subprocess.run(
        ['/usr/bin/python3', '-B', '-m', 'unittest', '-v'], cwd=str(workspace),
        env={'PATH': '/usr/bin:/bin', 'HOME': str(workspace),
             'PYTHONDONTWRITEBYTECODE': '1'},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        timeout=10, check=False)
    changed = sorted(name for name in set(before) | set(current)
                     if before.get(name) != current.get(name))
    passed = (run.returncode == 0 and changed == ['README.md', 'widget.py'] and
              before['test_widget.py'] == current.get('test_widget.py') and
              'portable agentkit' in (workspace / 'README.md').read_text())
    return passed, {'test_exit_code': run.returncode,
                    'test_output': run.stdout[-4000:], 'changed_files': changed,
                    'controller_test_passed': run.returncode == 0}


def candidate_payload(workspace):
    files = {path.name: path.read_text() for path in sorted(workspace.iterdir())
             if path.is_file()}
    digest = hashlib.sha256(json.dumps(
        files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return files, digest


def review_acceptance(result, digest):
    value = result.structured_output
    passed = (result.status == 'succeeded' and isinstance(value, dict) and
              set(value) == {'verdict', 'findings', 'candidate_sha256'} and
              value['verdict'] in ('no_findings', 'findings') and
              isinstance(value['findings'], list) and
              value['candidate_sha256'] == digest and
              (value['verdict'] == 'findings' or value['findings'] == []))
    return passed, {'controller_validated_shape': passed,
                    'verdict': value.get('verdict') if isinstance(value, dict) else None,
                    'candidate_sha256_matches': (
                        value.get('candidate_sha256') == digest
                        if isinstance(value, dict) else False)}


def request(engine, task_id, prompt, cwd, role, profile, mode):
    timeout = remaining_timeout(role)
    resources = resolve_role_resources(role, task_timeout_seconds=timeout)
    return ExecutionRequest(
        engine, task_id, prompt, str(Path(cwd).resolve()),
        timeout_seconds=timeout,
        max_output_bytes=resources['max_capture_bytes']['value'],
        mode=mode, capability_profile=profile,
        resource_resolution=resources)


def main():
    if subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(REPOSITORY),
                      text=True, stdout=subprocess.PIPE, check=True).stdout.strip() != EXECUTABLE_REVISION:
        raise RuntimeError('executable revision changed before checkpoint')
    if subprocess.run(['git', 'diff', '--quiet', '--', 'agentkit'],
                      cwd=str(REPOSITORY), check=False).returncode != 0:
        raise RuntimeError('executable code is dirty before checkpoint')
    write_json('preflight.json', {
        'schema_version': 1,
        'executable_revision': EXECUTABLE_REVISION,
        'platform': {'system': 'Darwin', 'release': '25.6.0', 'machine': 'arm64'},
        'cli': {
            'codex': {'version': '0.154.0',
                      'sha256': '61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70',
                      'authentication': 'subscription-reported'},
            'claude': {'version': '2.1.220',
                       'sha256': '8addc857f3fe64d5a0368af9ee50321b50afb4a6918ba3ef018ab84f5dbbe081',
                       'authentication': 'subscription-reported',
                       'subscription_type': 'max'}},
        'budget': {'cli_launches': MAX_LAUNCHES, 'overall_seconds': OVERALL_SECONDS,
                   'max_concurrency': 2, 'actual_schedule': 'sequential',
                   'retries': 0, 'provider_substitution': False,
                   'game_inference': False},
        'billing': {'mode': 'subscription-reported', 'paid_overflow': None,
                    'billed_cost_usd': None},
    })
    with tempfile.TemporaryDirectory(prefix='agentkit-cli-checkpoint-', dir='/private/tmp') as temp:
        base = Path(temp).resolve()
        planning_prompt = (
            'Return only one JSON object with exactly these keys: objective, requirements, '
            'assumptions, acceptance, assignments, dependencies, integration_strategy, '
            'verification_requirements, review_requirements. Plan a dependency-free command-line '
            'utility that reads a local UTF-8 text file and writes deterministic word and line '
            'counts. Include at least four sourced requirements, five observable acceptance '
            'criteria, explicit assumptions, one or two scoped assignments with allowed_paths, '
            'interfaces and dependencies, an integration strategy, independent verification and '
            'review requirements. Do not include source code, shell commands, network, publication '
            'or credentials. Produce a realistic plan of at least 900 JSON bytes.'
        )
        direct_plan_cwd = base / 'codex-direct-plan'
        adapter_plan_cwd = base / 'codex-adapter-plan'
        direct_plan_cwd.mkdir()
        adapter_plan_cwd.mkdir()
        direct_plan_request = request(
            'codex', 'checkpoint-direct-plan', planning_prompt, direct_plan_cwd,
            'planning', 'structured-planning', 'model-only')
        direct_plan = direct_codex(direct_plan_request, ROOT / '01-codex-direct-plan')
        accepted, detail = plan_acceptance(direct_plan)
        record('codex-direct-plan', 'direct', direct_plan, accepted, detail)

        adapter_plan_request = request(
            'codex', 'checkpoint-adapter-plan', planning_prompt, adapter_plan_cwd,
            'planning', 'structured-planning', 'model-only')
        adapter_plan = execute(
            adapter_plan_request, ROOT / '02-codex-adapter-plan', policy=POLICY)
        accepted, detail = plan_acceptance(adapter_plan)
        record('codex-adapter-plan', 'adapter', adapter_plan, accepted, detail)

        implementation_prompt = (
            'Work only in this disposable directory. Read README.md and test_widget.py. Create '
            'widget.py with describe() returning exactly "portable agentkit". Edit README.md to '
            'document that exact phrase. Do not change test_widget.py or create any other file. '
            'Run exactly `python3 -B -m unittest -v`. Do not access other paths or the network. '
            'Finish with a short summary.'
        )
        accepted_adapter_workspace = None
        for ordinal, kind in ((3, 'direct'), (4, 'adapter')):
            workspace = base / ('claude-' + kind + '-implementation')
            before = seed_implementation(workspace)
            sibling = base / ('sibling-' + kind)
            controller = base / ('controller-' + kind)
            protected = base / ('protected-' + kind)
            for path in (sibling, controller, protected):
                path.mkdir()
            (sibling / 'source.txt').write_text('SIBLING-CANARY')
            (controller / 'state.json').write_text('{"authority":"controller"}')
            (protected / 'fake-credentials').write_text('FAKE-CREDENTIALS-ONLY')
            protected_before = {str(path): sha(path) for path in (
                sibling / 'source.txt', controller / 'state.json',
                protected / 'fake-credentials')}
            boundary = ExecutionBoundary(
                str(workspace), (str(sibling), str(controller),
                                 str(protected / 'fake-credentials')))
            implementation_request = request(
                'claude', 'checkpoint-' + kind + '-implementation',
                implementation_prompt, workspace, 'implementation',
                'code-implementation', 'owned-code')
            if kind == 'direct':
                result = direct_claude_owned(
                    implementation_request,
                    ROOT / '03-claude-direct-implementation', boundary)
            else:
                result = execute_owned_code(
                    implementation_request,
                    ROOT / '04-claude-adapter-implementation', boundary,
                    policy=POLICY)
            accepted, detail = implementation_acceptance(workspace, before)
            detail['protected_canaries_unchanged'] = all(
                sha(path) == digest for path, digest in protected_before.items())
            accepted = accepted and detail['protected_canaries_unchanged']
            record('claude-' + kind + '-implementation', kind, result,
                   accepted and result.status == 'succeeded', detail)
            if kind == 'adapter' and accepted and result.status == 'succeeded':
                accepted_adapter_workspace = workspace
        if accepted_adapter_workspace is None:
            raise RuntimeError('adapter implementation did not produce an accepted candidate')

        files, candidate_digest = candidate_payload(accepted_adapter_workspace)
        review_prompt = (
            'Independently review this exact disposable candidate against these criteria: '
            'describe() returns exactly "portable agentkit"; the protected unittest passes; '
            'README documents the behavior; no unrelated files changed. Return only JSON with '
            'exactly verdict (no_findings or findings), findings (an array), and '
            'candidate_sha256. Each finding, if present, must name id, severity, path, criterion '
            'and description. Use this candidate_sha256 exactly: ' + candidate_digest +
            '\nCANDIDATE_FILES_JSON:\n' + json.dumps(files, sort_keys=True)
        )
        for ordinal, kind in ((5, 'direct'), (6, 'adapter')):
            cwd = base / ('codex-' + kind + '-review')
            cwd.mkdir()
            review_request = request(
                'codex', 'checkpoint-' + kind + '-review', review_prompt, cwd,
                'review', 'independent-review', 'model-only')
            if kind == 'direct':
                result = direct_codex(
                    review_request, ROOT / '05-codex-direct-review')
            else:
                result = execute(
                    review_request, ROOT / '06-codex-adapter-review', policy=POLICY)
            accepted, detail = review_acceptance(result, candidate_digest)
            record('codex-' + kind + '-review', kind, result, accepted, detail)

        comparison = {
            'schema_version': 1,
            'candidate_sha256': candidate_digest,
            'launches': launches,
            'pairs': {},
        }
        labels = (('planning', direct_plan, adapter_plan),)
        for name, direct, adapter in labels:
            comparison['pairs'][name] = {
                'direct_launch': direct.provider_details.get('launch_configuration'),
                'adapter_launch': adapter.provider_details.get('launch_configuration'),
                'direct_status': direct.status,
                'adapter_status': adapter.status,
            }
        for role, direct_dir, adapter_dir in (
                ('implementation', '03-claude-direct-implementation',
                 '04-claude-adapter-implementation'),
                ('review', '05-codex-direct-review', '06-codex-adapter-review')):
            comparison['pairs'][role] = {
                'direct_result_sha256': sha(ROOT / direct_dir / 'result.json'),
                'adapter_result_sha256': sha(ROOT / adapter_dir / 'result.json'),
            }
        write_json('comparison.json', comparison)

    elapsed = time.monotonic() - started
    summary = {
        'schema_version': 1,
        'executable_revision': EXECUTABLE_REVISION,
        'status': ('passed' if len(launches) == MAX_LAUNCHES and
                   all(item['status'] == 'succeeded' and item['accepted']
                       for item in launches) else 'failed'),
        'cli_launches': len(launches),
        'provider_requests': None,
        'turns': None,
        'elapsed_seconds': elapsed,
        'within_overall_deadline': elapsed <= OVERALL_SECONDS,
        'launches': launches,
        'billing': {'estimated_cost_usd': None, 'billed_cost_usd': None,
                    'note': 'Per-launch provider estimates remain observations; billed cost is unknown.'},
        'game_trial_executed': False,
    }
    estimates = [item['usage']['estimated_cost_usd'] for item in launches]
    if all(value is not None for value in estimates):
        summary['billing']['estimated_cost_usd'] = sum(estimates)
    write_json('summary.json', summary)
    write_json('manifest.json', {'schema_version': 1, 'files': manifest(ROOT)})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
