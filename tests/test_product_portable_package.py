import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from agentkit.controller import ControllerStore
from agentkit.portable_package import PortablePackageError, export_package, verify_package


BASE = '1' * 40
HEAD = '2' * 40
TASK_ID = 'product-package'


class ProductPortablePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-product-package-test-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def completed_product(self, name):
        root = self.root / name
        (root / 'approval').mkdir(parents=True)
        store = ControllerStore(root / 'controller')
        store.create_task(TASK_ID, 'Build an accessible static counter.', max_repairs=0,
                          max_calls=4, max_elapsed_seconds=60, max_concurrency=1,
                          max_timeout_seconds=20, verification_reserve=1,
                          review_reserve=1, max_provider_calls=3, max_planning_calls=0)
        contract = {
            'objective': 'Build an accessible static counter.',
            'scope': ['game.js', 'index.html', 'styles.css'],
            'acceptance': [
                {'id': 'counter', 'expected': 'Increment and reset work in a browser.'},
            ],
        }
        store.set_contract(TASK_ID, contract, authority=store.authority)
        store.transition(TASK_ID, 'received', 'contracted', name + '-contracted',
                         authority=store.authority)
        store.set_workspace(TASK_ID, 'agentkit/product-package', str(root / 'worktree'), BASE,
                            authority=store.authority)
        store.set_head(TASK_ID, HEAD, authority=store.authority)
        for expected, target in (
                ('contracted', 'workspace_ready'), ('workspace_ready', 'implementing'),
                ('implementing', 'implemented'), ('implemented', 'verifying')):
            store.transition(TASK_ID, expected, target, name + '-' + target,
                             authority=store.authority)

        evidence = (
            ('phase4-verification-0', 'independent-check', {'checks': ['node mechanics']}),
            ('phase4-review-0', 'independent-review', {'findings': []}),
            ('product-browser-0', 'browser-check', {
                'candidate_revision': HEAD,
                'checks': [{'id': 'counter', 'status': 'passed', 'observation': 'observed'}],
                'preview_cleanup': True,
            }),
        )
        for evidence_id, kind, details in evidence:
            artifact = store.put_artifact(json.dumps(details, sort_keys=True))
            store.add_evidence(TASK_ID, evidence_id, HEAD, kind, 'passed', artifact, details,
                               authority=store.authority)
            if kind == 'independent-check':
                store.transition(TASK_ID, 'verifying', 'verified', name + '-verified',
                                 authority=store.authority)
                store.transition(TASK_ID, 'verified', 'reviewing', name + '-reviewing',
                                 authority=store.authority)
            elif kind == 'independent-review':
                store.transition(TASK_ID, 'reviewing', 'review_complete',
                                 name + '-review-complete', authority=store.authority)
        store.transition(TASK_ID, 'review_complete', 'packaging', name + '-packaging',
                         authority=store.authority)

        required = [
            {'id': 'phase4-verification-0', 'kind': 'independent-check'},
            {'id': 'phase4-review-0', 'kind': 'independent-review'},
            {'id': 'product-browser-0', 'kind': 'browser-check'},
            {'id': 'phase4-approval-package', 'kind': 'approval-package'},
        ]
        approval = {
            'schema_version': 1, 'task_id': TASK_ID, 'status': 'awaiting_pr_approval',
            'managed_base_revision': BASE, 'head_revision': HEAD,
            'diff': 'diff --git a/game.js b/game.js\n',
            'requirements': contract['acceptance'], 'required_evidence': required,
            'approval': {'recorded': False, 'bound_head': HEAD},
        }
        artifact = store.put_artifact(json.dumps(approval, sort_keys=True))
        store.add_evidence(TASK_ID, 'phase4-approval-package', HEAD, 'approval-package',
                           'passed', artifact,
                           {'base_revision': BASE, 'head_revision': HEAD},
                           authority=store.authority)
        approval['artifact_sha256'] = artifact
        (root / 'approval' / 'approval-package.json').write_text(
            json.dumps(approval, indent=2, sort_keys=True) + '\n')
        store.transition(TASK_ID, 'packaging', 'awaiting_pr_approval', name + '-awaiting',
                         authority=store.authority)
        return root, store

    def test_product_package_exports_and_verifies_all_required_evidence_without_execution(self):
        root, _ = self.completed_product('complete')
        output = self.root / 'portable'
        with mock.patch('subprocess.Popen', side_effect=AssertionError('must not execute')):
            result = export_package(root, TASK_ID, output)
            checked = verify_package(output)
        self.assertTrue(result['valid'])
        self.assertEqual(checked['head_revision'], HEAD)
        approval = json.loads((output / 'approval-package.json').read_text())
        self.assertEqual({item['kind'] for item in approval['required_evidence']}, {
            'independent-check', 'independent-review', 'browser-check', 'approval-package'})
        self.assertEqual(
            sorted(path.name for path in (output / 'evidence').iterdir()),
            ['phase4-approval-package.json', 'phase4-review-0.json',
             'phase4-verification-0.json', 'product-browser-0.json'])

    def test_product_export_rejects_missing_failed_stale_and_tampered_evidence(self):
        for case in ('missing', 'failed', 'stale', 'tampered'):
            with self.subTest(case=case):
                root, store = self.completed_product(case)
                if case == 'missing':
                    with store.transaction() as db:
                        db.execute("DELETE FROM evidence WHERE evidence_id='product-browser-0'")
                elif case == 'failed':
                    with store.transaction() as db:
                        db.execute("UPDATE evidence SET status='failed' "
                                   "WHERE evidence_id='product-browser-0'")
                elif case == 'stale':
                    with store.transaction() as db:
                        db.execute("UPDATE evidence SET stale=1 "
                                   "WHERE evidence_id='product-browser-0'")
                else:
                    record = next(item for item in store.snapshot(TASK_ID)['evidence']
                                  if item['evidence_id'] == 'product-browser-0')
                    artifact = (store.artifact_root / record['artifact_sha256'][:2] /
                                record['artifact_sha256'])
                    artifact.write_text('tampered')
                with self.assertRaisesRegex(PortablePackageError, 'absent, stale'):
                    export_package(root, TASK_ID, self.root / ('portable-' + case))

    def test_product_export_rejects_duplicate_and_unknown_evidence_declarations(self):
        for case in ('duplicate', 'unknown'):
            with self.subTest(case=case):
                root, _ = self.completed_product(case)
                path = root / 'approval' / 'approval-package.json'
                approval = json.loads(path.read_text())
                if case == 'duplicate':
                    approval['required_evidence'][2]['id'] = 'phase4-review-0'
                else:
                    approval['required_evidence'][2]['kind'] = 'browser-script'
                path.write_text(json.dumps(approval))
                with self.assertRaises(PortablePackageError):
                    export_package(root, TASK_ID, self.root / ('portable-' + case))

    def test_offline_verifier_rejects_unknown_or_tampered_product_evidence(self):
        root, _ = self.completed_product('offline')
        package = self.root / 'portable-offline'
        export_package(root, TASK_ID, package)
        browser = package / 'evidence' / 'product-browser-0.json'
        browser.write_text('tampered')
        with self.assertRaisesRegex(PortablePackageError, 'integrity'):
            verify_package(package)

        second = self.root / 'portable-unknown'
        export_package(root, TASK_ID, second)
        extra = second / 'evidence' / 'unknown.json'
        extra.write_text('{}')
        manifest_path = second / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        raw = extra.read_bytes()
        manifest['files']['evidence/unknown.json'] = {
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(PortablePackageError, 'unknown evidence'):
            verify_package(second)


if __name__ == '__main__':
    unittest.main()
