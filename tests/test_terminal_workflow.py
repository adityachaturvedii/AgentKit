import json
from pathlib import Path
import tempfile
import unittest

from agentkit.integrations.openharness.protocol import FrontendRequest
from agentkit.controller import UsageRecord
from agentkit.delivery import EngineOutcome
from agentkit.orchestration import Phase4Workflow
from agentkit.phase4_fixtures import CALCULATOR
from agentkit.terminal_workflow import TerminalWorkflow


class AuthenticationOnceSpecialist:
    engine = "codex"
    model = None

    def __init__(self):
        self.calls = 0

    def run_assignment(self, workspace, assignment, output, boundary, prompt, policy):
        self.calls += 1
        if self.calls == 1:
            return EngineOutcome(
                "failed", .001, UsageRecord(source="unavailable"),
                {"error_class": "authentication", "authentication_failure": "expired"},
            )
        (Path(workspace) / "calculator.py").write_text(CALCULATOR.final_files["calculator.py"])
        return EngineOutcome("succeeded", .001, UsageRecord(source="fake"), {"simulated": True})


class TerminalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentkit-terminal-workflow-")
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def submit(self, task_id="terminal-task"):
        return Phase4Workflow.submit(
            self.root / task_id, task_id, "Correct total arithmetic.", "calculator",
            max_calls=6, max_provider_calls=3, max_concurrency=1, max_repairs=0,
            max_escalations=0,
        )

    def request(self, action, task_id="terminal-task"):
        return FrontendRequest.parse(json.dumps({
            "version": 1, "type": action, "task_id": task_id,
        }))

    def test_protocol_requires_only_version_type_and_bound_task_id(self):
        for action in ("snapshot", "status", "start", "resume", "cancel", "package_summary"):
            with self.subTest(action=action):
                self.assertEqual(self.request(action).type, action)
        for payload in (
                {"type": "status", "task_id": "terminal-task"},
                {"version": 1, "type": "start"},
                {"version": 1, "type": "start", "task_id": "terminal-task", "live": True},
                {"version": 1, "type": "approve", "task_id": "terminal-task"},
                {"version": True, "type": "status", "task_id": "terminal-task"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                FrontendRequest.parse(json.dumps(payload))

    def test_snapshot_and_status_are_read_only_and_never_relaunch(self):
        submitted = self.submit()
        before = submitted.store.snapshot("terminal-task")
        terminal = TerminalWorkflow(submitted.root, "terminal-task")
        first = terminal.handle(self.request("snapshot"))[0].to_dict()
        second = terminal.handle(self.request("status"))[0].to_dict()
        after = submitted.store.snapshot("terminal-task")

        self.assertEqual(first, second)
        self.assertEqual(first["state"]["stage"], "contracted")
        self.assertEqual(first["state"]["next_action"], "review proposed execution plan")
        self.assertFalse(first["state"]["usage_known"])
        self.assertFalse(first["state"]["approval_recorded"])
        self.assertIsNone(first["task"]["head_revision"])
        self.assertLessEqual(len(first["state"]["routing"]), 16)
        self.assertTrue(all(set(item) == {"role", "provider", "reason"}
                            for item in first["state"]["routing"]))
        self.assertEqual(before["task"]["state"], after["task"]["state"])
        self.assertEqual(before["executions"], after["executions"])
        self.assertEqual(before["events"], after["events"])

    def test_start_projects_candidate_and_unapproved_package(self):
        submitted = self.submit()
        terminal = TerminalWorkflow(submitted.root, "terminal-task")
        events = terminal.handle(self.request("start"))

        self.assertEqual([event.type for event in events], ["state_snapshot", "package_ready"])
        state = events[0].state
        package = events[1].package
        task = submitted.store.task("terminal-task")
        self.assertEqual(state["stage"], "awaiting_pr_approval")
        self.assertEqual(package["head_revision"], task["head_revision"])
        self.assertEqual(package["base_revision"], task["base_revision"])
        self.assertEqual(package["branch"], task["branch"])
        self.assertEqual(package["task_id"], "terminal-task")
        self.assertEqual(events[0].task.head_revision, task["head_revision"])
        self.assertEqual(state["candidate"]["head_revision"], task["head_revision"])
        self.assertFalse(package["approval_recorded"])
        self.assertNotIn("repository", package)
        self.assertNotIn("diff", package)
        self.assertNotIn("worktree", json.dumps([event.to_dict() for event in events]))

        summary = terminal.handle(self.request("package_summary"))
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0].package, package)
        self.assertEqual(submitted.store.task("terminal-task")["state"], "awaiting_pr_approval")

    def test_cancel_is_bound_to_constructor_task(self):
        submitted = self.submit()
        terminal = TerminalWorkflow(submitted.root, "terminal-task")
        with self.assertRaisesRegex(ValueError, "bound task"):
            terminal.handle(self.request("cancel", "another-task"))
        event = terminal.handle(self.request("cancel"))[0]
        self.assertEqual(event.state["stage"], "cancelled")
        self.assertTrue(event.state["cancelled"])
        self.assertEqual(submitted.store.snapshot("terminal-task")["executions"], [])

    def test_resume_uses_persisted_authentication_checkpoint(self):
        submitted = self.submit()
        specialist = AuthenticationOnceSpecialist()
        submitted.specialist_factory = lambda provider, fixture: specialist
        terminal = TerminalWorkflow(
            submitted.root, "terminal-task",
            workflow_factory=lambda root, *, live, authorized: submitted,
        )
        paused = terminal.handle(self.request("start"))
        self.assertEqual(paused[0].state["stage"], "authentication_required")
        self.assertTrue(paused[0].state["authentication_required"])
        self.assertIn("authentication required", paused[0].state["blocker"])

        claim = submitted.store.claim_authentication_login(
            "terminal-task", "codex", authority=submitted.store.authority)
        submitted.store.finish_authentication_login(
            claim["session_id"], "succeeded", auth_mode="subscription",
            reason="authenticated", owner_nonce=claim["owner_nonce"],
            authority=submitted.store.authority,
        )
        resumed = terminal.handle(self.request("resume"))
        self.assertEqual([event.type for event in resumed], ["state_snapshot", "package_ready"])
        self.assertEqual(resumed[0].state["stage"], "awaiting_pr_approval")
        self.assertEqual(specialist.calls, 2)

    def test_constructor_policy_is_not_frontend_controlled(self):
        submitted = self.submit()
        captured = []

        def factory(root, *, live, authorized):
            captured.append((root, live, authorized))
            return Phase4Workflow(root, live=live, authorized=authorized)

        terminal = TerminalWorkflow(
            submitted.root, "terminal-task", live=True, authorized=True,
            workflow_factory=factory,
        )
        terminal.handle(self.request("status"))
        self.assertEqual(captured, [(submitted.root, True, True)])
        with self.assertRaises(ValueError):
            FrontendRequest.parse(json.dumps({
                "version": 1, "type": "status", "task_id": "terminal-task",
                "authorized": True,
            }))
        from agentkit.integrations.openharness.protocol import BackendEvent
        with self.assertRaisesRegex(ValueError, "authority-expanding"):
            BackendEvent("state_snapshot", state={"approval_recorded": True})
        with self.assertRaisesRegex(ValueError, "authority-expanding"):
            BackendEvent("package_ready", package={"approval_recorded": True,
                                                    "verification_count": 1,
                                                    "findings_count": 0})
        with self.assertRaisesRegex(ValueError, "usage_known"):
            BackendEvent("state_snapshot", state={"usage_known": "yes"})
        with self.assertRaisesRegex(ValueError, "event message"):
            BackendEvent("error", message="\x1b[2Jforged status")

    def test_package_summary_before_completion_does_not_start_task(self):
        submitted = self.submit()
        terminal = TerminalWorkflow(submitted.root, "terminal-task")
        with self.assertRaisesRegex(ValueError, "no approval package"):
            terminal.handle(self.request("package_summary"))
        self.assertEqual(submitted.store.task("terminal-task")["state"], "contracted")
        self.assertEqual(submitted.store.snapshot("terminal-task")["executions"], [])


if __name__ == "__main__":
    unittest.main()
