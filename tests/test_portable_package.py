from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from agentkit.controller import UsageRecord
from agentkit.__main__ import main
from agentkit.delivery import EngineOutcome
from agentkit.portable_package import PortablePackageError, export_package, verify_package
from agentkit.projects import ProjectRegistry, example_python_profile
from agentkit.repository_delivery import (DeterministicReviewer, FixtureRepositoryVerifier,
                                          RepositoryDeliveryWorkflow)


class Implementer:
    engine = 'fake-implementer'
    model = 'deterministic-v1'

    def run(self, workspace, handoff):
        (Path(workspace) / 'src/tool.py').write_text(
            'def normalize(value):\n    return value.strip()\n')
        return EngineOutcome('succeeded', 0, UsageRecord(source='fake'), {'simulated': True})


class PortablePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-package-test-')
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

    def rehash(self, package, relative):
        payload = (package / relative).read_bytes()
        manifest_path = package / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'][relative] = {
            'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}
        manifest_path.write_text(json.dumps(manifest))

    def completed_workflow(self, request='Fix normalize whitespace handling.'):
        source = self.root / 'source'
        source.mkdir()
        self.git(source, 'init', '-b', 'main')
        files = {
            'README.md': '# Fixture\n',
            'src/tool.py': 'def normalize(value):\n    return value\n',
            'tests/test_tool.py': ('import unittest\nfrom tool import normalize\n'
                                   'class T(unittest.TestCase):\n'
                                   ' def test_edges(self): self.assertEqual(normalize(" x "), "x")\n'),
        }
        for relative, content in files.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.git(source, 'add', '--', *sorted(files))
        self.git(source, 'commit', '-m', 'fixture')
        registry = ProjectRegistry(self.root / 'registry')
        record = registry.enroll(source, example_python_profile())
        workflow_root = self.root / 'workflow'
        placeholder = type('Placeholder', (), {'engine': 'fixture-local', 'model': 'placeholder'})()
        workflow = RepositoryDeliveryWorkflow(
            workflow_root, registry, record['project_id'], Implementer(),
            DeterministicReviewer(), placeholder, execution_authorized=True)
        workflow.verifier = FixtureRepositoryVerifier(workflow.broker)
        result = workflow.run(
            'package-task', request,
            'import unittest\nfrom tool import normalize\nclass A(unittest.TestCase):\n'
            ' def test_edges(self): self.assertEqual(normalize(" y "), "y")\n')
        self.assertEqual(result['task']['state'], 'awaiting_pr_approval')
        return workflow_root, workflow

    def test_export_redacts_secret_like_summary_content(self):
        workflow_root, _ = self.completed_workflow(
            'Fix normalize whitespace handling for owner@example.test.')
        package = self.root / 'review-package'
        export_package(workflow_root, 'package-task', package)
        content = ''.join(path.read_text(errors='replace') for path in package.rglob('*')
                          if path.is_file())
        self.assertNotIn('owner@example.test', content)
        self.assertIn('[REDACTED_EMAIL]', content)

    def test_export_and_offline_verify_complete_package(self):
        workflow_root, _ = self.completed_workflow()
        package = self.root / 'review-package'
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['package', 'export', '--workflow', str(workflow_root),
                                   '--task-id', 'package-task', '--output', str(package)]), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result['valid'])
        self.assertFalse(result['execution_performed'])
        approval = json.loads((package / 'approval-package.json').read_text())
        self.assertNotIn('managed_repository', json.dumps(approval))
        all_text = ''.join(path.read_text(errors='replace') for path in package.rglob('*')
                           if path.is_file())
        self.assertNotIn(str(self.root), all_text)
        self.assertFalse(approval['approval']['recorded'])
        with mock.patch('subprocess.Popen', side_effect=AssertionError('must not execute')):
            checked = verify_package(package)
        self.assertEqual(checked['head_revision'], approval['head_revision'])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['package', 'verify', str(package)]), 0)
        self.assertTrue(json.loads(output.getvalue())['valid'])
        self.assertEqual(checked['authority'], 'none')

    def test_tamper_extra_file_and_symlink_fail_closed(self):
        workflow_root, _ = self.completed_workflow()
        package = self.root / 'review-package'
        export_package(workflow_root, 'package-task', package)
        (package / 'candidate.diff').write_text('tampered\n')
        with self.assertRaisesRegex(PortablePackageError, 'integrity'):
            verify_package(package)

    def test_malformed_internal_json_and_requirement_matrix_fail_closed(self):
        workflow_root, _ = self.completed_workflow()
        package = self.root / 'review-package'
        export_package(workflow_root, 'package-task', package)
        matrix = package / 'requirement-matrix.json'
        matrix.write_text('{')
        self.rehash(package, 'requirement-matrix.json')
        with self.assertRaises(PortablePackageError):
            verify_package(package)

        package = self.root / 'second-package'
        export_package(workflow_root, 'package-task', package)
        approval_path = package / 'approval-package.json'
        approval = json.loads(approval_path.read_text())
        approval['requirements'][0]['expected'] = 'changed after export'
        approval_path.write_text(json.dumps(approval))
        self.rehash(package, 'approval-package.json')
        with self.assertRaises(PortablePackageError):
            verify_package(package)

        second = self.root / 'extra-package'
        export_package(workflow_root, 'package-task', second)
        (second / 'extra').write_text('undeclared')
        with self.assertRaisesRegex(PortablePackageError, 'undeclared'):
            verify_package(second)

        third = self.root / 'symlink-package'
        export_package(workflow_root, 'package-task', third)
        (third / 'link').symlink_to(third / 'candidate.diff')
        with self.assertRaisesRegex(PortablePackageError, 'symlink'):
            verify_package(third)

    def test_export_rejects_stale_or_missing_required_evidence(self):
        workflow_root, workflow = self.completed_workflow()
        with workflow.store.transaction() as db:
            db.execute("UPDATE evidence SET stale=1 WHERE evidence_id='verification-0'")
        with self.assertRaisesRegex(PortablePackageError, 'absent, stale'):
            export_package(workflow_root, 'package-task', self.root / 'stale-package')

        with workflow.store.transaction() as db:
            db.execute("UPDATE evidence SET stale=0 WHERE evidence_id='verification-0'")
            db.execute("DELETE FROM evidence WHERE evidence_id='review-0'")
        with self.assertRaisesRegex(PortablePackageError, 'absent, stale'):
            export_package(workflow_root, 'package-task', self.root / 'missing-package')

    def test_export_rejects_missing_source_artifact(self):
        workflow_root, workflow = self.completed_workflow()
        review = next(item for item in workflow.store.snapshot('package-task')['evidence']
                      if item['evidence_id'] == 'review-0')
        artifact = (workflow.store.artifact_root / review['artifact_sha256'][:2] /
                    review['artifact_sha256'])
        artifact.unlink()
        with self.assertRaisesRegex(PortablePackageError, 'absent, stale'):
            export_package(workflow_root, 'package-task', self.root / 'missing-artifact')

    def test_export_rejects_approval_without_required_verification(self):
        workflow_root, _ = self.completed_workflow()
        approval_path = workflow_root / 'approval' / 'approval-package.json'
        approval = json.loads(approval_path.read_text())
        approval['verification_evidence'] = []
        approval_path.write_text(json.dumps(approval))
        with self.assertRaisesRegex(PortablePackageError, 'no required verification'):
            export_package(workflow_root, 'package-task', self.root / 'missing-verification')

    def test_manifest_path_escape_is_rejected_without_file_access(self):
        workflow_root, _ = self.completed_workflow()
        package = self.root / 'review-package'
        export_package(workflow_root, 'package-task', package)
        manifest = json.loads((package / 'manifest.json').read_text())
        manifest['files']['../escape'] = {'sha256': '0' * 64, 'bytes': 0}
        (package / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(PortablePackageError):
            verify_package(package)

        alias = self.root / 'package-alias'
        alias.symlink_to(package, target_is_directory=True)
        with self.assertRaisesRegex(PortablePackageError, 'real directory'):
            verify_package(alias)


if __name__ == '__main__':
    unittest.main()
