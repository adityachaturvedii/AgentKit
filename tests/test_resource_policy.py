import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentkit.adapters import ADAPTERS, _apply_fixture_smoke_environment, execute
from agentkit.resource_policy import (
    capability_profile, output_exhaustion_recovery, policy_document,
    resolve_product_task_budget, resolve_role_resources)
from agentkit.runtime_contracts import ExecutionRequest, LivePolicy


class ResourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-resource-policy-')
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_precedence_and_unset_productive_output_control(self):
        default = resolve_role_resources('planning')
        self.assertEqual(default['timeout_seconds']['source'], 'role-policy')
        self.assertEqual(default['generated_output_tokens'], {
            'value': None, 'source': 'provider-default',
            'classification': 'observable-only',
            'rationale': 'Unset: provider behavior and effective ceiling are unknown.'})
        explicit = resolve_role_resources(
            'planning', task_timeout_seconds=37, task_capture_bytes=2048,
            provider_output_tokens=65536)
        self.assertEqual(explicit['timeout_seconds']['source'], 'task-override')
        self.assertEqual(explicit['generated_output_tokens']['value'], 65536)

    def test_timeout_has_no_universal_three_hundred_second_ceiling(self):
        resources = resolve_role_resources('implementation', task_timeout_seconds=901)
        request = ExecutionRequest(
            'codex', 'long-bounded-task', 'fixture', str(self.root),
            timeout_seconds=901, mode='owned-code',
            capability_profile='code-implementation',
            resource_resolution=resources)
        self.assertEqual(request.timeout_seconds, 901)

    def test_product_task_bounds_are_policy_defaults_not_old_trial_maxima(self):
        resolved = resolve_product_task_budget(
            max_calls=12, max_provider_calls=10, max_elapsed_seconds=2400)
        self.assertEqual(resolved['max_calls']['value'], 12)
        self.assertEqual(resolved['max_calls']['source'], 'task-override')
        self.assertEqual(resolved['max_concurrency']['source'], 'role-policy')

    def test_output_recovery_removes_only_an_imposed_override_once(self):
        imposed = resolve_role_resources('planning', provider_output_tokens=512)
        recovered = output_exhaustion_recovery(
            imposed, remaining_calls=1, remaining_seconds=10)
        self.assertIsNone(recovered['generated_output_tokens']['value'])
        self.assertEqual(recovered['generated_output_tokens']['source'], 'provider-default')
        self.assertIsNone(output_exhaustion_recovery(
            recovered, remaining_calls=1, remaining_seconds=10))
        self.assertIsNone(output_exhaustion_recovery(
            imposed, remaining_calls=1, remaining_seconds=10,
            repeated_failure=True))

    def test_productive_output_override_fails_before_cli_probe(self):
        workspace = self.root / 'workspace'
        workspace.mkdir()
        resources = resolve_role_resources('planning', provider_output_tokens=32768)
        request = ExecutionRequest(
            'claude', 'unsupported-output-control', 'fixture', str(workspace),
            timeout_seconds=180,
            capability_profile='structured-planning',
            max_generated_output_tokens=32768,
            resource_resolution=resources)
        with patch('agentkit.adapters.native_sandbox_capability',
                   side_effect=AssertionError('must fail before host probe')):
            result = execute(
                request, self.root / 'evidence',
                policy=LivePolicy(True, 'fixture authorization'))
        self.assertEqual((result.status, result.error_class),
                         ('blocked', 'unsupported_provider_control'))

    def test_role_capabilities_construct_narrow_claude_permissions(self):
        workspace = self.root / 'owned'
        workspace.mkdir()
        from agentkit.runtime_contracts import ExecutionBoundary
        boundary = ExecutionBoundary(str(workspace), (str(self.root / 'denied'),))
        for name, expected_bash in (
                ('code-implementation', 'Bash(python3 -B -m unittest*)'),
                ('web-product-implementation', 'Bash(node --check *)')):
            request = ExecutionRequest(
                'claude', name, 'fixture', str(workspace), mode='owned-code',
                capability_profile=name)
            argv = ADAPTERS['claude'].argv(
                'claude', request, self.root, boundary,
                session_id='00000000-0000-4000-8000-000000000000')
            import json
            settings = json.loads(argv[argv.index('--settings') + 1])
            self.assertEqual(argv[argv.index('--tools') + 1], 'Read,Edit,Write,Bash')
            self.assertIn(expected_bash, settings['permissions']['allow'])
            self.assertNotIn('Bash', settings['permissions']['allow'])
            self.assertNotIn('WebFetch', argv[argv.index('--tools') + 1])
        for name in ('structured-planning', 'independent-review'):
            request = ExecutionRequest(
                'claude', name, 'fixture', str(self.root),
                capability_profile=name)
            argv = ADAPTERS['claude'].argv('claude', request, self.root)
            self.assertEqual(argv[argv.index('--tools') + 1], '')

    def test_policy_classifies_provider_controls_honestly(self):
        document = policy_document()
        self.assertEqual(document['precedence'], [
            'task-override', 'role-policy', 'provider-default'])
        self.assertEqual(
            document['provider_controls']['claude']['generated_output_tokens'][0],
            'observable-only')
        self.assertEqual(
            document['provider_controls']['codex']['generated_output_tokens'][0],
            'unsupported')
        self.assertEqual(capability_profile(
            'web-product-implementation', 'owned-code').tools,
            ('Read', 'Edit', 'Write', 'Bash'))

    def test_fixture_environment_limits_do_not_leak_to_productive_roles(self):
        productive = ExecutionRequest(
            'claude', 'plan', 'fixture', str(self.root),
            capability_profile='structured-planning')
        env = {}
        _apply_fixture_smoke_environment(productive, env)
        self.assertEqual(env, {})
        smoke = ExecutionRequest(
            'claude', 'smoke', 'fixture', str(self.root),
            capability_profile='smoke-model-only',
            max_generated_output_tokens=512)
        _apply_fixture_smoke_environment(smoke, env)
        self.assertEqual(env, {
            'CLAUDE_CODE_MAX_RETRIES': '0',
            'CLAUDE_CODE_MAX_TURNS': '1',
            'CLAUDE_CODE_MAX_OUTPUT_TOKENS': '512'})


if __name__ == '__main__':
    unittest.main()
