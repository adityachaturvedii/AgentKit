import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentkit.product import planning_context
from agentkit.__main__ import main
from agentkit.refinement import (AcceptanceCheck, AcceptanceSpec, DesignBrief,
                                 RecoveryDecision, guided_intake, refinement_decision,
                                 run_view)


H = 'a' * 64
R = 'b' * 40


class RefinementContractTests(unittest.TestCase):
    def test_guided_intake_preserves_request_scope_and_material_ambiguity(self):
        intent = guided_intake(
            'Add pagination to the existing Python results view. Keep its current API.',
            {'paths': ['agentkit/results.py', 'tests/test_results.py']},
            workflow_kind='repository')
        self.assertIn('pagination', intent.objective)
        self.assertEqual(intent.allowed_paths,
                         ('agentkit/results.py', 'tests/test_results.py'))
        self.assertIsNone(intent.material_question)
        self.assertNotIn('budget', intent.to_dict())
        self.assertNotIn('permissions', intent.to_dict())

        conflicted = guided_intake(
            'Add acceptance coverage but do not test the behavior.',
            {'paths': ['app.js']}, workflow_kind='static-product')
        self.assertIn('conflicting', conflicted.material_question)

    def test_guided_intake_rejects_inventory_scope_escape(self):
        for path in ('../secret', '/private/tmp/x', '.git/config', 'controller/state.db'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'scope path'):
                guided_intake('Make the requested change.', {'paths': [path]},
                              workflow_kind='repository')

    def test_design_brief_is_hash_bound(self):
        brief = DesignBrief(
            'Operator can understand the candidate quickly.', ('inspect result',),
            'calm technical', 'Prioritize evidence and action.',
            ('space-2=8px',), ('status-card',), ('usable at 360px',),
            ('visible focus',), (), (), ('no dashboard',), ('acceptance-1',))
        changed = DesignBrief(**{**brief.__dict__, 'direction': 'editorial'})
        self.assertRegex(brief.digest(), r'^[0-9a-f]{64}$')
        self.assertNotEqual(brief.digest(), changed.digest())

    def test_acceptance_spec_is_frozen_strict_and_uses_controlled_commands(self):
        check = AcceptanceCheck('unit', 'requirement-1', 'protected-independent',
                                'test exits zero', 'controller', ('python3', '-m', 'unittest'))
        spec = AcceptanceSpec((check,), 'macos-read-only', 1, H,
                              ('known-good passes',), ('known-bad fails',), ())
        self.assertRegex(spec.digest(), r'^[0-9a-f]{64}$')
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            AcceptanceCheck('shell', 'requirement-1', 'protected-independent',
                            'runs', 'controller', ('sh', '-c', 'true'))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            AcceptanceSpec((check, check), 'macos-read-only', 1, H,
                           ('positive',), ('negative',), ())
        with self.assertRaisesRegex(ValueError, 'cannot embed'):
            AcceptanceCheck('browser', 'requirement-1', 'browser', 'visible',
                            'controller', ('node', 'check.js'))

    def test_run_view_uses_authoritative_counts_and_unknown_usage(self):
        status = {
            'task_id': 'task-1', 'state': 'implementing',
            'assignments': {'active': [{'node_id': 'implement-a'}]},
            'verification': [
                {'status': 'passed', 'stale': False},
                {'status': 'failed', 'stale': True},
            ],
            'budget': {'usage_reporting': {'completeness': 'unknown'}},
            'next_action': 'wait for the supervised worker',
        }
        task = {'task_id': 'task-1', 'objective': 'Change one fixture.',
                'head_revision': R}
        view = run_view(status, task, workflow_kind='fixture')
        self.assertEqual(view.active_assignments, ('implement-a',))
        self.assertEqual(view.acceptance_coverage,
                         {'passed': 1, 'failed': 0, 'unknown': 1})
        self.assertEqual(view.usage['completeness'], 'unknown')
        self.assertFalse(hasattr(view, 'percent_complete'))

    def test_refinement_invalidates_quality_without_expanding_authority(self):
        decision = refinement_decision(
            prior_revision=R, current_revision=R, requested_paths=['app.js'],
            allowed_paths=['app.js', 'styles.css'], remaining_repairs=1)
        self.assertIn('review', decision['invalidates'])
        self.assertFalse(decision['approval_recorded'])
        with self.assertRaisesRegex(ValueError, 'path authority'):
            refinement_decision(prior_revision=R, current_revision=R,
                                requested_paths=['other.js'], allowed_paths=['app.js'],
                                remaining_repairs=1)

    def test_recovery_is_narrow_candidate_bound_and_does_not_repeat_implementation(self):
        decision = RecoveryDecision(
            'task-1', 'failure-1', 'verification', 'blocked', R, H,
            'confirmed_ended', 'oracle', 'c' * 64, 1, 30.0,
            ('verification-old', 'review-old'))
        result = decision.authorize(actual_revision=R, actual_manifest_sha256=H,
                                    current_state='blocked')
        self.assertEqual(result['resume_stage'], 'verification')
        self.assertFalse(result['implementation_reexecution'])
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            decision.authorize(actual_revision=R, actual_manifest_sha256='d' * 64,
                               current_state='blocked')
        with self.assertRaisesRegex(ValueError, 'active claimant'):
            decision.authorize(actual_revision=R, actual_manifest_sha256=H,
                               current_state='blocked', competing_claim=True)

    def test_product_planning_context_contains_selected_skills_with_verified_hashes(self):
        context = planning_context(Path(__file__).parents[1])
        paths = {item['path'] for item in context['items']}
        self.assertIn('skills/product-shaping/SKILL.md', paths)
        self.assertIn('skills/interaction-design/SKILL.md', paths)
        self.assertIn('skills/visual-design/SKILL.md', paths)
        self.assertNotIn('skills/acceptance-design/SKILL.md', paths)
        for item in context['items']:
            self.assertEqual(item['sha256'], hashlib.sha256(
                item['content'].encode('utf-8')).hexdigest())

    def test_guided_intake_cli_accepts_plain_brief_and_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'brief.txt').write_text('Improve the existing result summary.')
            (root / 'inventory.json').write_text(json.dumps(
                {'paths': ['agentkit/results.py', 'tests/test_results.py']}))
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['refine', 'intake', '--request-file', str(root / 'brief.txt'),
                             '--inventory', str(root / 'inventory.json'),
                             '--kind', 'repository'])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result['workflow_kind'], 'repository')
            self.assertFalse(set(result) & {'approval', 'permissions', 'budget'})


if __name__ == '__main__':
    unittest.main()
