from pathlib import Path
import tempfile
import unittest

from agentkit.controller import UsageRecord
from agentkit.delivery import EngineOutcome
from agentkit.failure_reporting import FailureReportingError, RecoveryAction
from agentkit.orchestration import Phase4Workflow
from agentkit.phase4_fixtures import CALCULATOR


class AlwaysBrokenSpecialist:
    engine = 'codex'
    model = None

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        content = CALCULATOR.final_files['calculator.py'].replace(
            'return left + right', 'return left * right')
        (Path(workspace) / 'calculator.py').write_text(content)
        return EngineOutcome('succeeded', .001, UsageRecord(source='fake'), {'simulated': True})


class AuthenticationSpecialist:
    engine = 'codex'
    model = None

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        return EngineOutcome('failed', .001, UsageRecord(source='unavailable'), {
            'error_class': 'authentication', 'authentication_failure': 'expired'})


class FailureReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-failure-reporting-')
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def submit(self, task_id, **kwargs):
        return Phase4Workflow.submit(
            self.root / task_id, task_id, 'Correct total arithmetic.', 'calculator',
            max_calls=4, max_provider_calls=2, max_concurrency=1,
            max_repairs=0, max_escalations=0, **kwargs)

    def failed_workflow(self, task_id='failure'):
        workflow = self.submit(task_id)
        workflow.specialist_factory = lambda provider, fixture: AlwaysBrokenSpecialist()
        result = workflow.start(task_id)
        self.assertEqual(result['task']['state'], 'blocked')
        return workflow

    def test_original_cause_survives_repair_exhaustion_in_actionable_status(self):
        workflow = self.failed_workflow()
        status = workflow.status('failure')

        failure = status['current_failure']
        self.assertEqual(failure['stage'], 'verification')
        self.assertEqual(failure['category'], 'verification_failure')
        self.assertIn('exit code', failure['summary'])
        self.assertEqual(failure['disposition'], 'repair_exhausted')
        self.assertEqual(failure['retryability'], 'blocked')
        self.assertEqual(failure['recovery_blocked_reason'], 'The repair budget is exhausted.')
        self.assertIn('FAILED', failure['diagnostic_tail'])
        self.assertIsNone(failure['recovery_action'])
        self.assertEqual(failure['candidate_revision'], workflow.store.task('failure')['head_revision'])
        self.assertEqual(len(failure['evidence_refs']), 1)
        self.assertEqual(len(failure['evidence_refs'][0]['artifact_sha256']), 64)

    def test_projection_identity_is_stable_and_history_is_immutable(self):
        workflow = self.failed_workflow('stable')
        before = workflow.store.snapshot('stable')
        first = workflow.status('stable')['failures']
        second = workflow.status('stable')['failures']
        after = workflow.store.snapshot('stable')

        self.assertEqual(first, second)
        self.assertIn('repair-exhausted', first[0]['occurrence_id'])
        self.assertEqual(before, after)

    def test_recovery_is_exposed_only_after_validated_authentication_prerequisite(self):
        workflow = self.submit('auth')
        workflow.specialist_factory = lambda provider, fixture: AuthenticationSpecialist()
        paused = workflow.start('auth')
        self.assertEqual(paused['task']['state'], 'authentication_required')
        waiting = workflow.status('auth')['current_failure']
        self.assertIsNone(waiting['recovery_action'])
        self.assertIn('Verified subscription login', waiting['recovery_blocked_reason'])

        claim = workflow.store.claim_authentication_login(
            'auth', 'codex', authority=workflow.store.authority)
        workflow.store.finish_authentication_login(
            claim['session_id'], 'succeeded', auth_mode='subscription', reason='authenticated',
            owner_nonce=claim['owner_nonce'], authority=workflow.store.authority)
        ready = workflow.status('auth')['current_failure']

        self.assertEqual(ready['occurrence_id'], waiting['occurrence_id'])
        self.assertIsNone(ready['recovery_blocked_reason'])
        self.assertEqual(ready['recovery_action']['operation'], 'resume_authentication')
        self.assertEqual(ready['recovery_action']['source_state'], 'authentication_required')
        self.assertEqual(ready['recovery_action']['target_state'], 'implementing')
        self.assertEqual(ready['recovery_action']['authority_prerequisite'], 'controller_authority')

    def test_invalid_or_generic_recovery_is_rejected(self):
        with self.assertRaisesRegex(FailureReportingError, 'unsupported recovery transition'):
            RecoveryAction('unblock', 'blocked', 'running', 'controller_authority', 'checkpoint')
        with self.assertRaisesRegex(FailureReportingError, 'unsupported recovery transition'):
            RecoveryAction('resume_authentication', 'authentication_required', 'implementing',
                           'operator_claim', 'checkpoint')


if __name__ == '__main__':
    unittest.main()
