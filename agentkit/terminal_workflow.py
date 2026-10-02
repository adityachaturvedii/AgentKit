"""Bounded terminal facade over an existing controller-owned Phase 4 task."""

from pathlib import Path

from .integrations.openharness.protocol import BackendEvent, FrontendRequest, TaskSnapshot, safe_ui_state
from .orchestration import Phase4Workflow


class TerminalWorkflow:
    """Expose task lifecycle commands without accepting authority-bearing input."""

    def __init__(self, root, task_id, *, live=False, authorized=False,
                 workflow_factory=None, workflow_kind='fixture'):
        if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 128:
            raise ValueError("invalid terminal task id")
        if type(live) is not bool or type(authorized) is not bool:
            raise ValueError("terminal policy flags must be booleans")
        self.root = Path(root).resolve()
        self.task_id = task_id
        if workflow_kind not in ('fixture', 'static-product'):
            raise ValueError('unsupported terminal workflow kind')
        if workflow_factory is None:
            if workflow_kind == 'static-product':
                from .product import ProductWorkflow
                workflow_factory = ProductWorkflow
            else:
                workflow_factory = Phase4Workflow
        self.workflow_kind = workflow_kind
        self.workflow = workflow_factory(self.root, live=live, authorized=authorized)
        # Bind exactly the requested task. Never enumerate or infer another task.
        self.workflow.store.task(self.task_id)

    def handle(self, request):
        if not isinstance(request, FrontendRequest):
            raise ValueError("terminal workflow requires a validated frontend request")
        if request.task_id != self.task_id:
            raise ValueError("frontend request does not identify the bound task")
        if request.type in ("snapshot", "status"):
            return (self._snapshot_event(),)
        if request.type == "package_summary":
            package = self.workflow.result(self.task_id)["approval_package"]
            if package is None:
                raise ValueError("task has no approval package")
            return (self._package_event(package),)
        if request.type == "start":
            return self._result_events(self.workflow.start(self.task_id))
        if request.type == "resume":
            return self._result_events(self.workflow.resume(self.task_id))
        if request.type == "cancel":
            status = self.workflow.cancel(self.task_id)
            task = self.workflow.store.task(self.task_id)
            return (self._snapshot_event(status=status, task=task),)
        raise ValueError("unsupported terminal workflow request")

    def _result_events(self, result):
        if not isinstance(result, dict):
            raise ValueError("workflow returned an invalid result")
        task = result.get("task")
        status = result.get("status")
        events = [self._snapshot_event(status=status, task=task)]
        package = result.get("approval_package")
        if package is not None:
            events.append(self._package_event(package))
        return tuple(events)

    def _snapshot_event(self, *, status=None, task=None):
        status = self.workflow.status(self.task_id) if status is None else status
        task = self.workflow.store.task(self.task_id) if task is None else task
        if (not isinstance(status, dict) or status.get("task_id") != self.task_id or
                not isinstance(task, dict) or task.get("task_id") != self.task_id or
                status.get("state") != task.get("state")):
            raise ValueError("authoritative task status is inconsistent")
        snapshot = TaskSnapshot(
            self.task_id, task["state"], task["objective"], task.get("next_action"),
            task.get("head_revision"),
        )
        return BackendEvent("state_snapshot", state=safe_ui_state(status, task), task=snapshot)

    def _package_event(self, package):
        if not isinstance(package, dict) or package.get("task_id") != self.task_id:
            raise ValueError("approval package does not identify the bound task")
        task = self.workflow.store.task(self.task_id)
        head = package.get("head_revision")
        base = package.get("base_revision", package.get("managed_base_revision"))
        branch = package.get("branch")
        approval = package.get("approval")
        if (not isinstance(approval, dict) or approval.get("recorded") is not False or
                package.get("status") != "awaiting_pr_approval" or
                task.get("state") != "awaiting_pr_approval" or
                head != task.get("head_revision") or base != task.get("base_revision") or
                branch != task.get("branch")):
            raise ValueError("approval package is not an unapproved exact candidate")
        for value, name in ((head, "package head revision"), (base, "package base revision"),
                            (branch, "package branch")):
            if value is not None and (not isinstance(value, str) or len(value) > 512):
                raise ValueError("invalid " + name)
        verification = package.get("verification") or ()
        findings = package.get("review_findings") or ()
        if not isinstance(verification, (list, tuple)) or not isinstance(findings, (list, tuple)):
            raise ValueError("approval package summaries must be lists")
        summary = {
            "task_id": self.task_id, "status": package["status"], "branch": branch,
            "base_revision": base, "head_revision": head,
            "verification_count": len(verification),
            "findings_count": len(findings),
            "approval_recorded": False,
        }
        return BackendEvent(
            "package_ready", package=summary,
            message="Local package is ready for review; publication is not authorized.",
        )
