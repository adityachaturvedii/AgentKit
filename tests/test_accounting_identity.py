import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from agentkit.controller import UsageRecord
from agentkit.delivery import EngineOutcome
from agentkit.git_broker import GitBroker, GitBrokerError, GitIdentity
from agentkit.orchestration import Phase4Workflow
from agentkit.phase4_fixtures import CALCULATOR
from agentkit.usage_summary import summarize_usage


class UsageSummaryTests(unittest.TestCase):
    def execution(self, engine, usage=None, *, status='succeeded', elapsed=1):
        return {'engine': engine, 'status': status, 'elapsed_seconds': elapsed,
                'usage_json': json.dumps(usage) if usage is not None else None}

    def test_partial_provider_usage_excludes_local_checks(self):
        summary = summarize_usage([
            self.execution('codex', {'input_tokens': 12, 'output_tokens': 3,
                                     'estimated_cost_usd': .02}),
            self.execution('claude', {'output_tokens': 4, 'billed_cost_usd': .03},
                           status='failed'),
            self.execution('local', None),
        ], wall_elapsed_seconds=2.5, reservations={'active_calls': 0, 'remaining_calls': 2})
        self.assertEqual(summary['cli_launches'],
                         {'provider': 2, 'local_checks': 1, 'total': 3})
        inputs = summary['provider_usage']['input_tokens']
        self.assertEqual(inputs, {'reported_subtotal': 12,
                                  'contributing_execution_count': 1,
                                  'missing_execution_count': 1,
                                  'completeness': 'partial'})
        self.assertEqual(summary['provider_usage']['output_tokens']['reported_subtotal'], 7)
        self.assertEqual(summary['provider_usage']['output_tokens']['completeness'], 'complete')
        self.assertEqual(summary['provider_usage']['estimated_cost_usd']['reported_subtotal'], .02)
        self.assertEqual(summary['provider_usage']['estimated_cost_usd']['completeness'], 'partial')
        self.assertEqual(summary['provider_usage']['billed_cost_usd']['reported_subtotal'], .03)
        self.assertEqual(summary['provider_usage']['billed_cost_usd']['completeness'], 'partial')
        self.assertEqual(summary['elapsed'],
                         {'wall_seconds': 2.5, 'summed_execution_seconds': 3})
        self.assertEqual(summary['reservations']['remaining_calls'], 2)

    def test_no_provider_usage_stays_unknown_and_zero_is_reported(self):
        unknown = summarize_usage([self.execution('codex'), self.execution('local')])
        quantity = unknown['provider_usage']['input_tokens']
        self.assertIsNone(quantity['reported_subtotal'])
        self.assertEqual(quantity['missing_execution_count'], 1)
        self.assertEqual(quantity['completeness'], 'unknown')
        self.assertIsNone(unknown['provider_internal_requests'])
        self.assertIsNone(unknown['provider_internal_turns'])

        zero = summarize_usage([self.execution('codex', {'input_tokens': 0})])
        self.assertEqual(zero['provider_usage']['input_tokens']['reported_subtotal'], 0)
        self.assertEqual(zero['provider_usage']['input_tokens']['completeness'], 'complete')

    def test_reserved_execution_is_not_a_launch_but_auth_failure_is(self):
        summary = summarize_usage([
            self.execution('codex', status='reserved'),
            self.execution('claude', status='authentication_required'),
            self.execution('local', status='reconciled_not_started'),
        ])
        self.assertEqual(summary['cli_launches'],
                         {'provider': 1, 'local_checks': 0, 'total': 1})
        self.assertEqual(summary['provider_usage']['input_tokens']['missing_execution_count'], 1)

    def test_local_usage_never_becomes_provider_usage(self):
        summary = summarize_usage([
            self.execution('local', {'input_tokens': 999, 'estimated_cost_usd': 8}),
        ])
        self.assertEqual(summary['provider_usage']['input_tokens']['completeness'], 'unknown')
        self.assertIsNone(summary['provider_usage']['input_tokens']['reported_subtotal'])
        self.assertEqual(summary['local_checks']['cli_launches'], 1)

    def test_phase4_status_shows_partial_subtotals_and_keeps_legacy_unknown(self):
        class ReportingSpecialist:
            engine = 'codex'
            model = None

            def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
                (Path(workspace) / 'calculator.py').write_text(
                    CALCULATOR.final_files['calculator.py'])
                return EngineOutcome(
                    'succeeded', .01,
                    UsageRecord(input_tokens=11, output_tokens=3, source='fixture'),
                    {'simulated': True})

        with tempfile.TemporaryDirectory(prefix='agentkit-usage-status-') as temporary:
            workflow = Phase4Workflow.submit(
                Path(temporary) / 'status-workflow', 'usage-status',
                'Correct total arithmetic.', 'calculator', max_calls=3,
                max_provider_calls=2, max_concurrency=1)
            workflow.specialist_factory = lambda provider, fixture: ReportingSpecialist()
            workflow.start('usage-status')
            budget = workflow.status('usage-status')['budget']
            reporting = budget['usage_reporting']

            self.assertEqual(reporting['cli_launches'],
                             {'provider': 2, 'local_checks': 1, 'total': 3})
            self.assertEqual(reporting['provider_usage']['input_tokens'], {
                'reported_subtotal': 11,
                'contributing_execution_count': 1,
                'missing_execution_count': 1,
                'completeness': 'partial',
            })
            self.assertIsNone(budget['token_usage']['input_tokens'])


class GitIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-identity-test-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def git(self, repository, *args):
        environment = dict(os.environ)
        environment.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
        return subprocess.run(['git', '-C', str(repository), *args], env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True, timeout=10).stdout.decode().strip()

    def test_invalid_identity_data_is_rejected(self):
        for identity in (
                ('', 'valid@example.com', 'run-config'),
                ('Bad\nName', 'valid@example.com', 'run-config'),
                ('Name', 'bad address', 'run-config'),
                ('Name', 'valid@example.com', '../worker')):
            with self.subTest(identity=identity), self.assertRaises(GitBrokerError):
                GitIdentity(*identity)
        with self.assertRaises(GitBrokerError):
            GitBroker(self.root / 'wrong-type', identity={
                'name': 'Worker', 'email': 'worker@example.com', 'source': 'model-output'})

    def test_configured_identity_wins_over_hostile_repository_config(self):
        identity = GitIdentity('Aditya Chaturvedi', 'chaturvediaditya910@gmail.com',
                               'user-instruction')
        broker = GitBroker(self.root / 'managed', identity=identity)
        repository, base = broker.create_repository('fixture', {'source.py': 'before\n'})
        self.git(repository, 'config', 'user.name', 'Hostile Repository')
        self.git(repository, 'config', 'user.email', 'hostile@example.invalid')
        self.git(repository, 'config', 'author.name', 'Another Override')
        branch, worktree, _ = broker.create_task_worktree(repository, 'task', base)
        worker = broker.export_snapshot(repository, base, broker.worker_copies / 'task')
        (worker / 'source.py').write_text('after\n')
        revision, _ = broker.apply_worker_changes(
            repository, worktree, worker, ('source.py',), 'candidate')

        expected = 'Aditya Chaturvedi <chaturvediaditya910@gmail.com>'
        self.assertEqual(self.git(repository, 'show', '-s', '--format=%an <%ae>', revision), expected)
        self.assertEqual(self.git(repository, 'show', '-s', '--format=%cn <%ce>', revision), expected)
        self.assertEqual(broker.identity.source, 'user-instruction')
        self.assertEqual(broker.revision(repository, branch), revision)


if __name__ == '__main__':
    unittest.main()
