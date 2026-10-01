"""Thin deterministic controller backend for the R0 OpenHarness reuse slice."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from ...orchestration import Phase4Workflow
from .context import discover_context, render_context
from .fs import atomic_private_write
from .profiles import PublicProviderProfile, resolve_profile
from .protocol import BackendEvent, FrontendRequest, TaskSnapshot, event_stream, safe_ui_state


DEFAULT_PROFILE = PublicProviderProfile(
    "r0-deterministic", "codex", capability_profile="code-implementation")


class ReuseBackend:
    """Allowlisted UI facade over one controller-owned deterministic workflow."""

    def __init__(self, root, task_id="r0-demo"):
        self.root = Path(root).resolve()
        self.task_id = task_id
        self.workflow = None

    def handle(self, request):
        if not isinstance(request, FrontendRequest):
            raise ValueError("backend requires a validated frontend request")
        if request.type == "run_demo":
            return self._run()
        if request.type == "snapshot":
            self._require_task(request.task_id)
            return tuple(self._snapshot_events())
        if request.type == "cancel":
            self._require_task(request.task_id)
            status = self.workflow.cancel(self.task_id)
            return (BackendEvent("state_snapshot", state=safe_ui_state(status)),)
        if request.type == "shutdown":
            return (BackendEvent("shutdown", message="frontend session closed; no execution launched"),)
        raise ValueError("unsupported frontend request")

    def _require_task(self, task_id):
        if self.workflow is None or task_id != self.task_id:
            raise ValueError("frontend request does not identify the active deterministic task")

    def _run(self):
        if self.workflow is not None:
            raise ValueError("deterministic demo can run only once")
        if self.root.exists() or self.root.is_symlink():
            raise ValueError("R0 demo output must be a fresh path")
        self.workflow = Phase4Workflow.submit(
            self.root, self.task_id, "Correct total arithmetic.", "calculator",
            max_calls=5, max_provider_calls=2, max_concurrency=1, max_repairs=0,
            max_escalations=0,
        )
        initial = self.workflow.status(self.task_id)
        events = [BackendEvent(
            "ready", state=safe_ui_state(initial),
            task=self._task_snapshot(initial),
            item={"role": "system", "text": "Deterministic controller task accepted."},
        )]
        result = self.workflow.start(self.task_id)
        status = result["status"]
        events.extend((
            BackendEvent("transcript_item", item={
                "role": "status", "text": "Implementation, verification, and review completed offline."}),
            BackendEvent("state_snapshot", state=safe_ui_state(status),
                         task=self._task_snapshot(status)),
            BackendEvent("package_ready", package={
                "head_revision": result["approval_package"]["head_revision"],
                "verification_count": len(result["approval_package"]["verification"]),
                "findings_count": len(result["approval_package"]["review_findings"]),
                "approval_recorded": result["approval_package"]["approval"]["recorded"],
            }, message="Local approval package is ready; publication is not authorized."),
        ))
        return tuple(events)

    def _task_snapshot(self, status):
        task = self.workflow.store.task(self.task_id)
        return TaskSnapshot(self.task_id, task["state"], task["objective"], task["next_action"],
                            task["head_revision"])

    def _snapshot_events(self):
        status = self.workflow.status(self.task_id)
        yield BackendEvent("state_snapshot", state=safe_ui_state(status),
                           task=self._task_snapshot(status))


def _render_with_adapted_terminal(stream_path):
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("R0 adapted terminal requires Node.js; no runtime install is attempted")
    renderer = (Path(__file__).resolve().parents[3] / "frontend" / "agentkit-terminal" /
                "src" / "render-events.mjs")
    process = subprocess.run(
        [node, str(renderer), str(stream_path)], cwd=str(renderer.parent),
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"}, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=10, check=False,
    )
    if process.returncode:
        raise RuntimeError("adapted terminal failed: " + process.stderr.decode("utf-8", "replace")[:1000])
    return process.stdout.decode("utf-8", "replace")


def _request_from_adapted_terminal():
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("R0 adapted terminal requires Node.js; no runtime install is attempted")
    frontend = (Path(__file__).resolve().parents[3] / "frontend" / "agentkit-terminal" /
                "src" / "request-demo.mjs")
    process = subprocess.run(
        [node, str(frontend)], cwd=str(frontend.parent),
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"}, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=5, check=False,
    )
    if process.returncode or len(process.stdout) > 65536:
        raise RuntimeError("adapted terminal request failed")
    return FrontendRequest.parse(process.stdout.strip())


def run_deterministic_demo(output):
    """Run one no-inference workflow through the strict backend and terminal seam."""
    started = time.monotonic()
    output = Path(output).resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("R0 demonstration output must be a fresh path")
    backend = ReuseBackend(output / "workflow")
    profile = resolve_profile(DEFAULT_PROFILE, expected_sha256=DEFAULT_PROFILE.sha256)
    toolkit_root = Path(__file__).resolve().parents[3]
    sources = discover_context(toolkit_root, toolkit_root, max_files=4)
    events = backend.handle(_request_from_adapted_terminal())
    output.mkdir(mode=0o700, exist_ok=True)
    stream_path = output / "frontend-events.jsonl"
    atomic_private_write(stream_path, event_stream(events))
    rendered = _render_with_adapted_terminal(stream_path)
    atomic_private_write(output / "terminal.txt", rendered)
    metadata = {
        "schema_version": 1,
        "deterministic": True,
        "provider_inference": False,
        "profile": profile,
        "context_sources": [{"path": item.relative_path, "sha256": item.sha256,
                             "characters": item.characters, "advisory": item.advisory}
                            for item in sources],
        "context_sha256": hashlib.sha256((render_context(sources) or "").encode()).hexdigest(),
        "event_stream_sha256": hashlib.sha256(stream_path.read_bytes()).hexdigest(),
        "terminal_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "final_state": backend.workflow.store.task(backend.task_id)["state"],
        "elapsed_seconds": time.monotonic() - started,
        "approval_recorded": False,
    }
    atomic_private_write(output / "r0-demo.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return {"output": str(output), "terminal": rendered, "metadata": metadata}
