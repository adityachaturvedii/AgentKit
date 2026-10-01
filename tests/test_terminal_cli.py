import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from agentkit.__main__ import main
from agentkit.orchestration import Phase4Workflow


class TerminalCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agentkit-terminal-cli-')
        self.root = Path(self.tmp.name) / 'workflow'
        self.task_id = 'terminal-demo'
        Phase4Workflow.submit(
            self.root, self.task_id, 'Correct total arithmetic.', 'calculator',
            max_calls=5, max_provider_calls=2, max_concurrency=1,
            max_repairs=0, max_escalations=0)
        self.addCleanup(self.tmp.cleanup)

    def run_cli(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = ['workflow', *arguments, '--root', str(self.root), '--task-id', self.task_id]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_status_plain_reports_authoritative_state_and_next_action(self):
        code, output, error = self.run_cli('status')
        self.assertEqual(code, 0, error)
        self.assertIn('task: terminal-demo', output)
        self.assertIn('state: contracted', output)
        self.assertIn('next action:', output)
        self.assertIn('usage: unknown', output)

    def test_json_and_event_formats_expose_the_same_protocol_snapshot(self):
        code, output, error = self.run_cli('status', '--format', 'json')
        self.assertEqual(code, 0, error)
        value = json.loads(output)
        self.assertEqual(value['events'][-1]['type'], 'state_snapshot')
        self.assertEqual(value['events'][-1]['task']['task_id'], self.task_id)

        code, output, error = self.run_cli('status', '--format', 'events')
        self.assertEqual(code, 0, error)
        events = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(events, value['events'])

    def test_start_then_package_use_existing_workflow(self):
        code, output, error = self.run_cli('start', '--format', 'json')
        self.assertEqual(code, 0, error)
        events = json.loads(output)['events']
        snapshot = next(event for event in events if event['type'] == 'state_snapshot')
        self.assertEqual(snapshot['state']['stage'], 'awaiting_pr_approval')

        code, output, error = self.run_cli('package')
        self.assertEqual(code, 0, error)
        self.assertIn('candidate:', output)
        self.assertIn('approval recorded: no', output)

    def test_cancel_preserves_controller_lifecycle(self):
        code, output, error = self.run_cli('cancel')
        self.assertEqual(code, 0, error)
        self.assertIn('state: cancelled', output)

    def test_live_execution_requires_both_construction_flags(self):
        code, output, error = self.run_cli('start', '--live')
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('requires explicit subscription authorization', error)
        self.assertEqual(Phase4Workflow(self.root).status(self.task_id)['state'], 'contracted')

        code, output, error = self.run_cli('start', '--authorize-subscription-smoke')
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('valid only with --live', error)
        self.assertEqual(Phase4Workflow(self.root).status(self.task_id)['state'], 'contracted')

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for terminal rendering')
    def test_terminal_format_uses_the_dependency_free_renderer(self):
        code, output, error = self.run_cli('status', '--format', 'terminal')
        self.assertEqual(code, 0, error)
        self.assertIn('AgentKit', output)
        self.assertIn('task: terminal-demo', output)
        self.assertIn('stage: contracted', output)
        self.assertIn('next action:', output)


if __name__ == '__main__':
    unittest.main()
