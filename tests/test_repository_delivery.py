import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from agentkit.controller import ControllerError, StaleEvidence, UsageRecord
from agentkit.delivery import EngineOutcome, LiveImplementer, LiveReviewer
from agentkit.git_broker import GitBroker
from agentkit.doctor import native_sandbox_capability
from agentkit.projects import ProjectRegistry, example_python_profile
from agentkit.repository_delivery import (
    DeterministicReviewer, FixtureRepositoryVerifier, IndependentRepositoryImporter,
    RepositoryDeliveryError, RepositoryDeliveryWorkflow, RepositoryVerifier,
    resolve_repository_task, validate_prepared_environment,
)
from agentkit.process import ProcessOutcome
from agentkit.runtime_contracts import (CancellationStatus, Capability, ExecutionResult,
                                        LivePolicy, UsageObservation)


class FixNormalizeImplementer:
    engine = 'fake-implementer'
    model = 'deterministic-v1'

    def __init__(self):
        self.handoffs = []

    def run(self, workspace, handoff):
        self.handoffs.append(handoff)
        path = Path(workspace) / 'src' / 'tool.py'
        path.write_text('def normalize(value):\n    return value.strip()\n')
        return EngineOutcome('succeeded', 0, UsageRecord(source='fake'),
                             {'simulated': True})


class RepositoryDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-r2-test-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def git(self, repository, *args):
        environment = dict(os.environ)
        environment.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                           GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@localhost',
                           GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@localhost')
        return subprocess.run(['git', '-C', str(repository), *args], env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True, timeout=10)

    def repository(self, name='source', *, empty_tests=False, external_import=False):
        repository = self.root / name
        repository.mkdir()
        self.git(repository, 'init', '-b', 'main')
        source = ('import requests\n\n' if external_import else '') + (
            'def normalize(value):\n    return value\n')
        test = ('import unittest\n\nfrom tool import normalize\n\n'
                'class NormalizeTest(unittest.TestCase):\n'
                '    def test_strips_edges(self):\n'
                '        self.assertEqual(normalize(" x "), "x")\n')
        if empty_tests:
            test = 'import unittest\n'
        files = {
            'README.md': '# Normalize library\n',
            'src/tool.py': source,
            'tests/test_tool.py': test,
            'scripts/check me.py': '#!/usr/bin/env python3\nprint("ok")\n',
            'docs/café.txt': 'Unicode path\n',
        }
        for relative, content in files.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        (repository / 'scripts/check me.py').chmod(0o755)
        self.git(repository, 'add', '--', *sorted(files))
        self.git(repository, 'commit', '-m', 'fixture')
        return repository

    def enrollment(self, repository, state_name='state', profile=None):
        registry = ProjectRegistry(self.root / state_name)
        return registry, registry.enroll(repository, profile or example_python_profile())

    @staticmethod
    def manifest(root):
        return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(Path(root).rglob('*')) if path.is_file() and not path.is_symlink()}

    @staticmethod
    def complete_login(workflow, task_id, provider):
        claim = workflow.store.claim_authentication_login(
            task_id, provider, owner_pid=12345, owner_nonce='fixture-owner',
            authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription',
            reason='authenticated', owner_nonce=claim['owner_nonce'],
            authority=workflow.store.authority)

    def test_import_reconstructs_bytes_modes_and_unicode_without_source_changes_or_links(self):
        source = self.repository()
        registry, record = self.enrollment(source)
        before = self.manifest(source)
        broker = GitBroker(self.root / 'managed')
        result = IndependentRepositoryImporter(registry, broker).import_project(
            record['project_id'], 'imported')
        imported = Path(result['managed_repository'])
        self.assertEqual(self.manifest(source), before)
        self.assertEqual((imported / 'docs/café.txt').read_text(), 'Unicode path\n')
        self.assertTrue((imported / 'scripts/check me.py').stat().st_mode & 0o100)
        self.assertNotEqual((source / 'src/tool.py').stat().st_ino,
                            (imported / 'src/tool.py').stat().st_ino)
        self.assertEqual(self.git(imported, 'remote').stdout, b'')
        self.assertFalse((imported / '.git/objects/info/alternates').exists())
        self.assertTrue(result['original_unchanged'])

    def test_import_rejects_stale_source_and_tracked_excluded_content(self):
        source = self.repository('stale')
        registry, record = self.enrollment(source, 'stale-state')
        (source / 'src/tool.py').write_text('changed\n')
        with self.assertRaisesRegex(RepositoryDeliveryError, 'no longer ready|stale'):
            IndependentRepositoryImporter(registry, GitBroker(self.root / 'stale-managed')).import_project(
                record['project_id'], 'imported')

        excluded = self.repository('excluded')
        (excluded / 'build').mkdir()
        (excluded / 'build/generated.py').write_text('value = 1\n')
        self.git(excluded, 'add', 'build/generated.py')
        self.git(excluded, 'commit', '-m', 'tracked excluded')
        registry, record = self.enrollment(excluded, 'excluded-state')
        with self.assertRaisesRegex(RepositoryDeliveryError, 'tracked excluded'):
            IndependentRepositoryImporter(registry, GitBroker(self.root / 'excluded-managed')).import_project(
                record['project_id'], 'imported')

    def test_prepared_environment_blocks_missing_dependency_without_install(self):
        source = self.repository('dependency', external_import=True)
        registry, record = self.enrollment(source, 'dependency-state')
        prepared = validate_prepared_environment(record['profile'], source)
        self.assertEqual(prepared.status, 'environment_required')
        self.assertEqual(prepared.missing_dependencies, ('requests',))
        self.assertFalse(prepared.to_dict()['install_during_run'])
        self.assertEqual(prepared.to_dict()['network'], 'none')

    def test_prepared_environment_uses_selected_interpreter_stdlib_extensions(self):
        source = self.repository('stdlib-extension')
        (source / 'src/tool.py').write_text('import math\n\ndef normalize(value):\n    return value.strip()\n')
        self.git(source, 'add', 'src/tool.py')
        self.git(source, 'commit', '-m', 'use extension stdlib')
        registry, record = self.enrollment(source, 'stdlib-extension-state')
        prepared = validate_prepared_environment(record['profile'], source)
        self.assertEqual(prepared.status, 'ready')
        self.assertNotIn('math', prepared.missing_dependencies)

    def test_request_resolution_is_grounded_and_conservative(self):
        source = self.repository('planning')
        registry, record = self.enrollment(source, 'planning-state')
        supported = resolve_repository_task(record, 'Fix normalize whitespace handling')
        self.assertEqual(supported['status'], 'ready')
        self.assertIn('src/tool.py', supported['allowed_paths'])
        unmatched = resolve_repository_task(record, 'Add a CSV export endpoint')
        self.assertEqual(unmatched['status'], 'clarification_required')
        negated = resolve_repository_task(record, 'Do not change normalize')
        self.assertEqual(negated['reason'], 'negated_requirement')
        contradictory = resolve_repository_task(
            record, 'Enable normalize and do not enable normalize')
        self.assertEqual(contradictory['reason'], 'contradictory_request')

    def test_verifier_catches_defect_empty_tests_mutation_and_stale_candidate(self):
        for name, empty in (('defect', False), ('empty', True)):
            with self.subTest(name=name):
                source = self.repository(name, empty_tests=empty)
                registry, record = self.enrollment(source, name + '-state')
                broker = GitBroker(self.root / (name + '-managed'))
                imported = IndependentRepositoryImporter(registry, broker).import_project(
                    record['project_id'], 'repository')
                repository = Path(imported['managed_repository'])
                _, worktree, head = broker.create_task_worktree(repository, name, imported['managed_base_revision'])
                prepared = validate_prepared_environment(record['profile'], worktree)
                protected = ('import unittest\nfrom tool import normalize\n\n'
                             'class Acceptance(unittest.TestCase):\n'
                             '    def test_edges(self): self.assertEqual(normalize(" y "), "y")\n')
                result = FixtureRepositoryVerifier(broker).run(
                    repository, worktree, head, prepared, protected)
                self.assertEqual(result.status, 'failed')
                if empty:
                    self.assertEqual(result.details['checks'][0]['collection_count'], 0)

        source = self.repository('mutation')
        registry, record = self.enrollment(source, 'mutation-state')
        broker = GitBroker(self.root / 'mutation-managed')
        imported = IndependentRepositoryImporter(registry, broker).import_project(record['project_id'], 'repository')
        repository = Path(imported['managed_repository'])
        _, worktree, head = broker.create_task_worktree(repository, 'mutation', imported['managed_base_revision'])
        prepared = validate_prepared_environment(record['profile'], worktree)
        mutation = ('import unittest\nfrom pathlib import Path\n\nclass Mutation(unittest.TestCase):\n'
                    '    def test_mutates(self):\n'
                    '        Path("README.md").write_text("tampered")\n')
        result = FixtureRepositoryVerifier(broker).run(repository, worktree, head, prepared, mutation)
        self.assertEqual(result.status, 'failed')
        self.assertFalse(result.details['candidate_unchanged'])

        (worktree / 'README.md').write_text('dirty\n')
        constrained = RepositoryVerifier(
            broker, self.root / 'controller', self.root / 'evidence',
            capability_check=lambda: Capability('verified', 'fixture'))
        result = constrained.run(repository, worktree, head, prepared, 'unused')
        self.assertEqual(result.details['error_class'], 'candidate_identity')

    def test_task_to_package_uses_structured_handoff_and_preserves_original(self):
        source = self.repository('workflow')
        registry, record = self.enrollment(source, 'workflow-state')
        original = self.manifest(source)
        implementer = FixNormalizeImplementer()
        root = self.root / 'workflow-run'
        # The workflow owns the broker, so bind the verifier after construction.
        workflow = RepositoryDeliveryWorkflow.__new__(RepositoryDeliveryWorkflow)
        # Construct normally with a temporary placeholder, then replace before execution.
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow.__init__(root, registry, record['project_id'], implementer,
                          DeterministicReviewer(), placeholder, execution_authorized=True)
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\n\n'
                     'class Acceptance(unittest.TestCase):\n'
                     '    def test_edges(self): self.assertEqual(normalize(" y "), "y")\n')
        result = workflow.run('normalize-task', 'Fix normalize so it strips surrounding whitespace.', protected)
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval', result['snapshot'])
        package = result['approval_package']
        self.assertEqual(package['head_revision'], result['task']['head_revision'])
        self.assertFalse(package['approval']['recorded'])
        self.assertEqual(len(package['resources']['executions']), 3)
        self.assertEqual(package['resources']['billing'],
                         'unknown; provider billing is not reported by this workflow')
        self.assertEqual(self.manifest(source), original)
        self.assertEqual(len(implementer.handoffs), 1)
        handoff = implementer.handoffs[0]
        self.assertEqual(handoff['starting_revision'], package['managed_base_revision'])
        self.assertFalse(handoff['authority']['publication'])
        self.assertNotIn('expected_patch', json.dumps(handoff))
        self.assertNotIn('return value.strip()', json.dumps(handoff))
        self.assertNotIn('test_edges', json.dumps(handoff))

    def test_live_implementer_uses_owned_code_adapter_contract(self):
        source = self.repository('live-contract')
        registry, record = self.enrollment(source, 'live-contract-state')
        captured = {}

        def transport(request, output, boundary, *, policy, cancel_event=None):
            captured.update(request=request, output=output, boundary=boundary, policy=policy)
            (Path(request.cwd) / 'src/tool.py').write_text(
                'def normalize(value):\n    return value.strip()\n')
            return ExecutionResult(request.engine, request.task_id, 'succeeded', None, 0, .01,
                                   usage=UsageObservation(source='fixture'))

        implementer = LiveImplementer('codex', model='account-default')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            self.root / 'live-contract-run', registry, record['project_id'], implementer,
            DeterministicReviewer(), placeholder, execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with mock.patch('agentkit.delivery.execute_owned_code', side_effect=transport):
            result = workflow.run('live-contract-task', 'Fix normalize whitespace handling.', protected)
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(captured['request'].mode, 'owned-code')
        self.assertEqual(captured['request'].capability_profile, 'code-implementation')
        self.assertEqual(captured['request'].model, 'account-default')
        self.assertTrue(captured['policy'].subscription_smoke_authorized)
        self.assertIn(str(workflow.controller_root), captured['boundary'].denied_read_paths)

    def test_authentication_failure_creates_revision_bound_checkpoint(self):
        source = self.repository('auth-checkpoint')
        registry, record = self.enrollment(source, 'auth-checkpoint-state')

        def authentication_failure(request, output, boundary, *, policy, cancel_event=None):
            return ExecutionResult(
                request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                usage=UsageObservation(source='unavailable'),
                provider_details={'authentication_failure': 'expired'})

        implementer = LiveImplementer('codex')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            self.root / 'auth-checkpoint-run', registry, record['project_id'], implementer,
            DeterministicReviewer(), placeholder, execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        with mock.patch('agentkit.delivery.execute_owned_code', side_effect=authentication_failure):
            result = workflow.run(
                'auth-checkpoint-task', 'Fix normalize whitespace handling.',
                'import unittest\nclass A(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        self.assertEqual(result['task']['state'], 'authentication_required')
        checkpoint = workflow.store.authentication_checkpoint('auth-checkpoint-task')
        self.assertEqual(checkpoint['provider'], 'codex')
        self.assertEqual(checkpoint['interrupted_state'], 'implementing')
        self.assertEqual(checkpoint['candidate_revision'], result['task']['head_revision'])
        self.assertTrue(checkpoint['candidate_identity']['clean'])

    def test_reviewer_authentication_checkpoint_preserves_verification(self):
        source = self.repository('review-auth')
        registry, record = self.enrollment(source, 'review-auth-state')

        def authentication_failure(request, output, *, policy, cancel_event=None):
            return ExecutionResult(
                request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                usage=UsageObservation(source='unavailable'),
                provider_details={'authentication_failure': 'expired'})

        reviewer = LiveReviewer('claude')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            self.root / 'review-auth-run', registry, record['project_id'],
            FixNormalizeImplementer(), reviewer, placeholder, execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with mock.patch('agentkit.delivery.execute', side_effect=authentication_failure):
            result = workflow.run('review-auth-task', 'Fix normalize whitespace handling.', protected)
        self.assertEqual(result['task']['state'], 'authentication_required')
        checkpoint = workflow.store.authentication_checkpoint('review-auth-task')
        self.assertEqual(checkpoint['provider'], 'claude')
        self.assertEqual(checkpoint['interrupted_state'], 'reviewing')
        self.assertEqual(checkpoint['evidence_refs'], ['verification-0'])
        evidence = {item['evidence_id']: item for item in result['snapshot']['evidence']}
        self.assertEqual(evidence['verification-0']['status'], 'passed')
        self.assertFalse(evidence['verification-0']['stale'])

    def test_reopen_and_resume_only_authenticated_implementation_stage(self):
        source = self.repository('resume-implementation')
        registry, record = self.enrollment(source, 'resume-implementation-state')
        calls = []

        def transport(request, output, boundary, *, policy, cancel_event=None):
            calls.append(request.task_id)
            if len(calls) == 1:
                return ExecutionResult(
                    request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                    usage=UsageObservation(source='unavailable'),
                    provider_details={'authentication_failure': 'expired'})
            (Path(request.cwd) / 'src/tool.py').write_text(
                'def normalize(value):\n    return value.strip()\n')
            return ExecutionResult(request.engine, request.task_id, 'succeeded', None, 0, .01,
                                   usage=UsageObservation(source='fixture'))

        implementer = LiveImplementer('codex')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        root = self.root / 'resume-implementation-run'
        workflow = RepositoryDeliveryWorkflow(
            root, registry, record['project_id'], implementer, DeterministicReviewer(),
            placeholder, execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with mock.patch('agentkit.delivery.execute_owned_code', side_effect=transport):
            paused = workflow.run(
                'resume-implementation-task', 'Fix normalize whitespace handling.', protected)
            self.assertEqual(paused['task']['state'], 'authentication_required')
            self.complete_login(workflow, 'resume-implementation-task', 'codex')
            reopened = RepositoryDeliveryWorkflow.open(
                root, registry, record['project_id'], implementer, DeterministicReviewer(),
                FixtureRepositoryVerifier(workflow.broker), execution_authorized=True,
                live_policy=LivePolicy(True, 'fixture authorization'))
            reopened.verifier = FixtureRepositoryVerifier(reopened.broker)
            completed = reopened.resume_after_authentication('resume-implementation-task')
        self.assertEqual(completed['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(len(calls), 2)
        roles = [item['role'] for item in completed['snapshot']['executions']]
        self.assertEqual(roles, ['implementer', 'implementer', 'verification', 'reviewer'])

    def test_reopen_reviewer_resume_preserves_completed_implementation_and_verification(self):
        source = self.repository('resume-review')
        registry, record = self.enrollment(source, 'resume-review-state')
        calls = []

        def transport(request, output, *, policy, cancel_event=None):
            calls.append(request.task_id)
            if len(calls) == 1:
                return ExecutionResult(
                    request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                    usage=UsageObservation(source='unavailable'),
                    provider_details={'authentication_failure': 'expired'})
            return ExecutionResult(
                request.engine, request.task_id, 'succeeded', None, 0, .01,
                structured_output={'verdict': 'no_findings', 'findings': []},
                usage=UsageObservation(source='fixture'))

        reviewer = LiveReviewer('claude')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        root = self.root / 'resume-review-run'
        workflow = RepositoryDeliveryWorkflow(
            root, registry, record['project_id'], FixNormalizeImplementer(), reviewer,
            placeholder, execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with mock.patch('agentkit.delivery.execute', side_effect=transport):
            paused = workflow.run(
                'resume-review-task', 'Fix normalize whitespace handling.', protected)
            before = [item['role'] for item in paused['snapshot']['executions']]
            self.assertEqual(before, ['implementer', 'verification', 'reviewer'])
            self.complete_login(workflow, 'resume-review-task', 'claude')
            reopened = RepositoryDeliveryWorkflow.open(
                root, registry, record['project_id'], FixNormalizeImplementer(), reviewer,
                FixtureRepositoryVerifier(workflow.broker), execution_authorized=True,
                live_policy=LivePolicy(True, 'fixture authorization'))
            reopened.verifier = FixtureRepositoryVerifier(reopened.broker)
            completed = reopened.resume_after_authentication('resume-review-task')
        self.assertEqual(completed['task']['state'], 'awaiting_pr_approval')
        roles = [item['role'] for item in completed['snapshot']['executions']]
        self.assertEqual(roles, ['implementer', 'verification', 'reviewer', 'reviewer'])
        self.assertEqual(len(calls), 2)
        evidence = [item['evidence_id'] for item in completed['snapshot']['evidence']]
        self.assertEqual(evidence.count('verification-0'), 1)

    def test_reopen_resume_rejects_changed_actual_candidate(self):
        source = self.repository('resume-stale')
        registry, record = self.enrollment(source, 'resume-stale-state')

        def authentication_failure(request, output, boundary, *, policy, cancel_event=None):
            return ExecutionResult(
                request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                usage=UsageObservation(source='unavailable'),
                provider_details={'authentication_failure': 'expired'})

        implementer = LiveImplementer('codex')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        root = self.root / 'resume-stale-run'
        workflow = RepositoryDeliveryWorkflow(
            root, registry, record['project_id'], implementer, DeterministicReviewer(),
            placeholder, execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        with mock.patch('agentkit.delivery.execute_owned_code', side_effect=authentication_failure):
            workflow.run('resume-stale-task', 'Fix normalize whitespace handling.',
                         'import unittest\nclass A(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        self.complete_login(workflow, 'resume-stale-task', 'codex')
        task = workflow.store.task('resume-stale-task')
        (Path(task['worktree']) / 'README.md').write_text('changed after login\n')
        reopened = RepositoryDeliveryWorkflow.open(
            root, registry, record['project_id'], implementer, DeterministicReviewer(),
            FixtureRepositoryVerifier(workflow.broker), execution_authorized=True,
            live_policy=LivePolicy(True, 'fixture authorization'))
        with self.assertRaisesRegex(StaleEvidence, 'candidate repository identity'):
            reopened.resume_after_authentication('resume-stale-task')
        self.assertEqual(reopened.store.task('resume-stale-task')['state'],
                         'authentication_required')

    def test_sequential_provider_logins_resume_without_repeating_completed_work(self):
        source = self.repository('sequential-auth')
        registry, record = self.enrollment(source, 'sequential-auth-state')
        implementation_calls = []
        review_calls = []

        def implementation_transport(request, output, boundary, *, policy, cancel_event=None):
            implementation_calls.append(request.task_id)
            if len(implementation_calls) == 1:
                return ExecutionResult(
                    request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                    usage=UsageObservation(source='unavailable'),
                    provider_details={'authentication_failure': 'expired'})
            (Path(request.cwd) / 'src/tool.py').write_text(
                'def normalize(value):\n    return value.strip()\n')
            return ExecutionResult(request.engine, request.task_id, 'succeeded', None, 0, .01,
                                   usage=UsageObservation(source='fixture'))

        def review_transport(request, output, *, policy, cancel_event=None):
            review_calls.append(request.task_id)
            if len(review_calls) == 1:
                return ExecutionResult(
                    request.engine, request.task_id, 'failed', 'authentication', 1, .01,
                    usage=UsageObservation(source='unavailable'),
                    provider_details={'authentication_failure': 'expired'})
            return ExecutionResult(
                request.engine, request.task_id, 'succeeded', None, 0, .01,
                structured_output={'verdict': 'no_findings', 'findings': []},
                usage=UsageObservation(source='fixture'))

        implementer = LiveImplementer('codex')
        reviewer = LiveReviewer('claude')
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        root = self.root / 'sequential-auth-run'
        workflow = RepositoryDeliveryWorkflow(
            root, registry, record['project_id'], implementer, reviewer, placeholder,
            execution_authorized=True, live_policy=LivePolicy(True, 'fixture authorization'))
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with mock.patch('agentkit.delivery.execute_owned_code', side_effect=implementation_transport), \
                mock.patch('agentkit.delivery.execute', side_effect=review_transport):
            first = workflow.run(
                'sequential-auth-task', 'Fix normalize whitespace handling.', protected)
            self.assertEqual(first['task']['state'], 'authentication_required')
            self.complete_login(workflow, 'sequential-auth-task', 'codex')
            reopened = RepositoryDeliveryWorkflow.open(
                root, registry, record['project_id'], implementer, reviewer,
                FixtureRepositoryVerifier(workflow.broker), execution_authorized=True,
                live_policy=LivePolicy(True, 'fixture authorization'))
            reopened.verifier = FixtureRepositoryVerifier(reopened.broker)
            second = reopened.resume_after_authentication('sequential-auth-task')
            self.assertEqual(second['task']['state'], 'authentication_required')
            self.assertEqual(second['snapshot']['evidence'][0]['evidence_id'], 'verification-0')
            self.complete_login(reopened, 'sequential-auth-task', 'claude')
            final = RepositoryDeliveryWorkflow.open(
                root, registry, record['project_id'], implementer, reviewer,
                FixtureRepositoryVerifier(reopened.broker), execution_authorized=True,
                live_policy=LivePolicy(True, 'fixture authorization'))
            final.verifier = FixtureRepositoryVerifier(final.broker)
            completed = final.resume_after_authentication('sequential-auth-task')
        self.assertEqual(completed['task']['state'], 'awaiting_pr_approval')
        self.assertEqual(len(implementation_calls), 2)
        self.assertEqual(len(review_calls), 2)
        self.assertEqual(len(final.store.authentication_checkpoint_history(
            'sequential-auth-task')), 2)
        roles = [item['role'] for item in completed['snapshot']['executions']]
        self.assertEqual(roles, ['implementer', 'implementer', 'verification',
                                 'reviewer', 'reviewer'])

    def test_cross_provider_review_policy_rejects_same_provider(self):
        source = self.repository('cross-provider')
        profile = example_python_profile()
        profile['required_review'] = 'cross-provider'
        registry, record = self.enrollment(source, 'cross-provider-state', profile)
        implementer = FixNormalizeImplementer()
        implementer.engine = 'codex'
        reviewer = DeterministicReviewer()
        reviewer.engine = 'codex'
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            self.root / 'cross-provider-run', registry, record['project_id'],
            implementer, reviewer, placeholder, execution_authorized=True)
        with self.assertRaisesRegex(RepositoryDeliveryError, 'cross-provider'):
            workflow.run('cross-provider-task', 'Fix normalize whitespace handling.', 'unused')
        with self.assertRaisesRegex(ControllerError, 'unknown task'):
            workflow.store.snapshot('cross-provider-task')

    def test_candidate_change_during_review_prevents_packaging(self):
        source = self.repository('stale-package')
        registry, record = self.enrollment(source, 'stale-package-state')
        holder = {}

        case = self

        class MutatingReviewer(DeterministicReviewer):
            def run(self, snapshot, context):
                workflow = holder['workflow']
                task = workflow.store.task('stale-package-task')
                path = Path(task['worktree']) / 'src/tool.py'
                path.write_text(path.read_text() + '\n# changed during review\n')
                case.git(Path(task['worktree']), 'add', '--', 'src/tool.py')
                case.git(Path(task['worktree']), 'commit', '-m', 'stale candidate')
                return super().run(snapshot, context)

        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            self.root / 'stale-package-run', registry, record['project_id'],
            FixNormalizeImplementer(), MutatingReviewer(), placeholder, execution_authorized=True)
        holder['workflow'] = workflow
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with self.assertRaisesRegex(RepositoryDeliveryError, 'candidate repository'):
            workflow.run('stale-package-task', 'Fix normalize whitespace handling.', protected)
        self.assertFalse((workflow.approval_root / 'approval-package.json').exists())

    def test_native_verifier_places_candidate_outside_denied_home(self):
        source = self.repository('candidate-location')
        registry, record = self.enrollment(source, 'candidate-location-state')
        broker = GitBroker(self.root / 'candidate-location-managed')
        imported = IndependentRepositoryImporter(registry, broker).import_project(
            record['project_id'], 'repository')
        repository = Path(imported['managed_repository'])
        _, worktree, head = broker.create_task_worktree(
            repository, 'candidate-location-task', imported['managed_base_revision'])
        observed = []

        def runner(argv, *, cwd, env, **kwargs):
            observed.append(Path(cwd).resolve())
            return ProcessOutcome(b'', b'Ran 1 test in 0.001s\nOK\n', 0, .01, None,
                                  CancellationStatus(process_group_gone=True))

        verifier = RepositoryVerifier(
            broker, self.root / 'controller', self.root / 'evidence',
            capability_check=lambda: Capability('verified', 'fixture'), process_runner=runner)
        result = verifier.run(
            repository, worktree, head,
            validate_prepared_environment(record['profile'], worktree),
            'import unittest\nclass A(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        self.assertEqual(result.status, 'succeeded', result.details)
        self.assertTrue(observed)
        self.assertTrue(all(str(path).startswith('/private/tmp/agentkit-r2-verify-')
                            for path in observed))
        self.assertTrue(all(not str(path).startswith(str(Path.home().resolve()))
                            for path in observed))

    def test_external_review_snapshot_root_must_be_private_temporary_storage(self):
        broker = GitBroker(self.root / 'external-root-managed')
        repository, head = broker.create_repository('repository', {'source.py': 'value = 1\n'})
        (self.root / 'outside').mkdir(mode=0o700)
        with self.assertRaisesRegex(Exception, 'under /private/tmp'):
            broker.export_snapshot(repository, head, self.root / 'outside' / 'snapshot',
                                   review=True, controlled_root=self.root / 'outside')

    def test_write_scope_rejects_worker_change_outside_declared_paths(self):
        source = self.repository('scope')
        registry, record = self.enrollment(source, 'scope-state')

        class Unsafe(FixNormalizeImplementer):
            def run(self, workspace, handoff):
                result = super().run(workspace, handoff)
                (Path(workspace) / 'README.md').write_text('unauthorized\n')
                return result

        root = self.root / 'scope-run'
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(root, registry, record['project_id'], Unsafe(),
                                              DeterministicReviewer(), placeholder, execution_authorized=True)
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        with self.assertRaisesRegex(Exception, 'protected path'):
            workflow.run('scope-task', 'Fix normalize whitespace.',
                         'import unittest\nclass A(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')

    def test_repository_execution_requires_separate_controller_authorization(self):
        source = self.repository('authorization')
        registry, record = self.enrollment(source, 'authorization-state')
        placeholder = type('Placeholder', (), {'engine': 'fixture', 'model': 'fixture'})()
        with self.assertRaisesRegex(RepositoryDeliveryError, 'explicit controller-side'):
            RepositoryDeliveryWorkflow(self.root / 'unauthorized', registry,
                                       record['project_id'], FixNormalizeImplementer(),
                                       DeterministicReviewer(), placeholder)

    def test_worker_mode_changes_are_rejected(self):
        broker = GitBroker(self.root / 'mode-managed')
        repository, base = broker.create_repository('repository', {'source.py': 'value = 1\n'})
        _, worktree, _ = broker.create_task_worktree(repository, 'mode-task', base)
        worker = broker.export_snapshot(repository, base, broker.worker_copies / 'mode-task')
        (worker / 'source.py').chmod(0o755)
        with self.assertRaisesRegex(Exception, 'file mode'):
            broker.apply_worker_changes(repository, worktree, worker,
                                        ('source.py',), 'unsupported mode change')

    def test_reviewer_mode_mutation_blocks_packaging(self):
        source = self.repository('review-mode')
        registry, record = self.enrollment(source, 'review-mode-state')

        class ModeMutatingReviewer(DeterministicReviewer):
            def run(self, snapshot, context):
                (Path(snapshot) / 'src/tool.py').chmod(0o755)
                return super().run(snapshot, context)

        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            self.root / 'review-mode-run', registry, record['project_id'],
            FixNormalizeImplementer(), ModeMutatingReviewer(), placeholder,
            execution_authorized=True)
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        protected = ('import unittest\nfrom tool import normalize\n\n'
                     'class A(unittest.TestCase):\n'
                     ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n')
        with self.assertRaisesRegex(RepositoryDeliveryError, 'reviewer changed'):
            workflow.run('review-mode-task', 'Fix normalize whitespace handling.', protected)
        self.assertFalse((workflow.approval_root / 'approval-package.json').exists())

    def test_native_verifier_denies_source_controller_home_and_fake_environment_secret(self):
        capability = native_sandbox_capability()
        if capability.state != 'verified':
            self.skipTest(capability.evidence)
        source = self.repository('native')
        registry, record = self.enrollment(source, 'native-state')
        broker = GitBroker(self.root / 'native-managed')
        imported = IndependentRepositoryImporter(registry, broker).import_project(
            record['project_id'], 'repository')
        repository = Path(imported['managed_repository'])
        _, worktree, base = broker.create_task_worktree(
            repository, 'native-task', imported['managed_base_revision'])
        worker = broker.export_snapshot(repository, base, broker.worker_copies / 'native-task')
        (worker / 'src/tool.py').write_text('def normalize(value):\n    return value.strip()\n')
        head, _ = broker.apply_worker_changes(repository, worktree, worker,
                                              ('src/tool.py',), 'fix fixture')
        controller = self.root / 'native-controller'
        evidence = self.root / 'native-evidence'
        controller.mkdir()
        evidence.mkdir()
        canary = controller / 'state-canary'
        canary.write_text('CONTROLLER-ONLY')
        protected = (
            'import os, unittest\nfrom pathlib import Path\nfrom tool import normalize\n\n'
            'class Acceptance(unittest.TestCase):\n'
            '    def test_boundaries(self):\n'
            '        self.assertEqual(normalize(" z "), "z")\n'
            '        self.assertIsNone(os.environ.get("AGENTKIT_FAKE_SECRET"))\n'
            '        for value in ' + repr([str(source / 'src/tool.py'), str(canary)]) + ':\n'
            '            with self.assertRaises(OSError): Path(value).read_text()\n')
        verifier = RepositoryVerifier(broker, controller, evidence,
                                      capability_check=lambda: capability)
        prepared = validate_prepared_environment(record['profile'], worktree)
        from unittest import mock
        with mock.patch.dict(os.environ, {'AGENTKIT_FAKE_SECRET': 'SYNTHETIC-ONLY'}):
            result = verifier.run(repository, worktree, head, prepared, protected,
                                  denied_paths=(source, registry.root))
        self.assertEqual(result.status, 'succeeded', result.details)
        self.assertTrue(result.details['candidate_unchanged'])


if __name__ == '__main__':
    unittest.main()
