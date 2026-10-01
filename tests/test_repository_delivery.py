import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from agentkit.controller import UsageRecord
from agentkit.delivery import EngineOutcome
from agentkit.git_broker import GitBroker
from agentkit.doctor import native_sandbox_capability
from agentkit.projects import ProjectRegistry, example_python_profile
from agentkit.repository_delivery import (
    DeterministicReviewer, FixtureRepositoryVerifier, IndependentRepositoryImporter,
    RepositoryDeliveryError, RepositoryDeliveryWorkflow, RepositoryVerifier,
    resolve_repository_task, validate_prepared_environment,
)
from agentkit.runtime_contracts import Capability


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

    def enrollment(self, repository, state_name='state'):
        registry = ProjectRegistry(self.root / state_name)
        return registry, registry.enroll(repository, example_python_profile())

    @staticmethod
    def manifest(root):
        return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(Path(root).rglob('*')) if path.is_file() and not path.is_symlink()}

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
                         'unknown; no live provider used in this workflow')
        self.assertEqual(self.manifest(source), original)
        self.assertEqual(len(implementer.handoffs), 1)
        handoff = implementer.handoffs[0]
        self.assertEqual(handoff['starting_revision'], package['managed_base_revision'])
        self.assertFalse(handoff['authority']['publication'])
        self.assertNotIn('expected_patch', json.dumps(handoff))
        self.assertNotIn('return value.strip()', json.dumps(handoff))
        self.assertNotIn('test_edges', json.dumps(handoff))

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
