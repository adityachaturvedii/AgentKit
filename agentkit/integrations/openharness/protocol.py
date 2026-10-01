"""Strict controller UI protocol adapted from OpenHarness ``ui/protocol.py``.

The original generic assistant protocol exposed prompt, permission, tool, and
session commands. R0 intentionally exposes only read/status, deterministic
fixture start, cancellation, and shutdown. There is no approval command.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re


PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 65536
REQUEST_TYPES = frozenset((
    "snapshot", "status", "start", "resume", "cancel", "package_summary",
    "run_demo", "shutdown",
))
EVENT_TYPES = frozenset((
    "ready", "state_snapshot", "transcript_item", "package_ready", "error", "shutdown",
))
STATE_KEYS = frozenset((
    "stage", "ready", "active", "waiting", "completed", "input_tokens", "output_tokens",
    "usage_known", "authentication_required", "candidate_stale", "cancelled", "blocker",
    "next_action", "attention", "routing", "approval_recorded", "candidate",
))
PACKAGE_KEYS = frozenset((
    "task_id", "status", "branch", "base_revision", "head_revision",
    "verification_count", "findings_count", "approval_recorded",
))


def _text(value, name, limit=512, *, required=True):
    if value is None and not required:
        return None
    if (not isinstance(value, str) or (required and not value.strip()) or len(value) > limit or
            re.search(r'[\x00-\x08\x0b-\x1f\x7f]', value)):
        raise ValueError("invalid " + name)
    return value


def _count(value, name, *, optional=True):
    if optional and value is None:
        return
    if type(value) is not int or value < 0:
        raise ValueError("invalid " + name)


def _validate_state(state):
    if not isinstance(state, dict) or set(state) - STATE_KEYS:
        raise ValueError("invalid workflow state")
    if state.get("approval_recorded") not in (None, False):
        raise ValueError("authority-expanding backend event")
    for key in ("stage", "blocker", "next_action", "attention"):
        if state.get(key) is not None:
            _text(state[key], "workflow " + key.replace("_", " "), 2048, required=False)
    for key in ("usage_known", "authentication_required", "candidate_stale", "cancelled"):
        if state.get(key) is not None and type(state[key]) is not bool:
            raise ValueError("invalid " + key)
    for key in ("ready", "active", "waiting", "completed", "input_tokens", "output_tokens"):
        _count(state.get(key), key)
    if state.get("usage_known") is True and (
            state.get("input_tokens") is None or state.get("output_tokens") is None):
        raise ValueError("known usage requires token counts")
    routes = state.get("routing") or ()
    if not isinstance(routes, (list, tuple)) or len(routes) > 16:
        raise ValueError("invalid routing summary")
    for route in routes:
        if not isinstance(route, dict) or set(route) != {"role", "provider", "reason"}:
            raise ValueError("invalid routing summary")
        _text(route["role"], "routing role", 128)
        _text(route["provider"], "routing provider", 128)
        _text(route["reason"], "routing reason", 1024)
    candidate = state.get("candidate")
    if candidate is not None:
        if (not isinstance(candidate, dict) or
                set(candidate) != {"branch", "base_revision", "head_revision"}):
            raise ValueError("invalid candidate summary")
        for key, value in candidate.items():
            _text(value, "candidate " + key, 512)


def _validate_package(package):
    if not isinstance(package, dict) or set(package) - PACKAGE_KEYS:
        raise ValueError("invalid package summary")
    if package.get("approval_recorded") is not False:
        raise ValueError("authority-expanding backend event")
    for key in ("task_id", "status", "branch", "base_revision", "head_revision"):
        if package.get(key) is not None:
            _text(package[key], "package " + key, 512)
    _count(package.get("verification_count"), "verification_count", optional=False)
    _count(package.get("findings_count"), "findings_count", optional=False)


@dataclass(frozen=True)
class FrontendRequest:
    type: str
    task_id: str | None = None
    version: int = PROTOCOL_VERSION

    def __post_init__(self):
        if (type(self.version) is not int or self.version != PROTOCOL_VERSION or
                self.type not in REQUEST_TYPES):
            raise ValueError("unsupported frontend request")
        if self.type in ("snapshot", "status", "start", "resume", "cancel", "package_summary"):
            _text(self.task_id, "task_id", 128)
        elif self.task_id is not None:
            _text(self.task_id, "task_id", 128)

    @classmethod
    def parse(cls, raw):
        if isinstance(raw, bytes):
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ValueError("frontend request exceeds byte bound")
            raw = raw.decode("utf-8")
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("frontend request exceeds byte bound")
        value = json.loads(raw)
        if (not isinstance(value, dict) or not {"version", "type"}.issubset(value) or
                set(value) - {"version", "type", "task_id"}):
            raise ValueError("invalid frontend request shape")
        return cls(**value)


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    state: str
    objective: str
    next_action: str | None
    head_revision: str | None

    def __post_init__(self):
        _text(self.task_id, "snapshot task_id", 128)
        _text(self.state, "snapshot state", 128)
        _text(self.objective, "snapshot objective", 4096)
        if self.next_action is not None:
            _text(self.next_action, "snapshot next action", 2048, required=False)
        if self.head_revision is not None:
            _text(self.head_revision, "snapshot head revision", 512, required=False)


@dataclass(frozen=True)
class BackendEvent:
    type: str
    state: dict | None = None
    task: TaskSnapshot | None = None
    item: dict | None = None
    package: dict | None = None
    message: str | None = None
    version: int = PROTOCOL_VERSION

    def __post_init__(self):
        if (type(self.version) is not int or self.version != PROTOCOL_VERSION or
                self.type not in EVENT_TYPES):
            raise ValueError("unsupported backend event")
        if self.message is not None:
            _text(self.message, "event message", 4096, required=False)
        if self.state is not None:
            _validate_state(self.state)
        if self.task is not None and not isinstance(self.task, TaskSnapshot):
            raise ValueError("invalid task snapshot")
        if self.item is not None:
            if not isinstance(self.item, dict) or set(self.item) != {"role", "text"}:
                raise ValueError("invalid transcript item")
            if self.item["role"] not in ("system", "status", "assistant", "log"):
                raise ValueError("invalid transcript role")
            _text(self.item["text"], "transcript text", 8192, required=False)
        if self.package is not None:
            _validate_package(self.package)

    def to_dict(self):
        value = asdict(self)
        return {key: item for key, item in value.items() if item is not None}

    def to_line(self):
        line = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("backend event exceeds byte bound")
        return line


def safe_ui_state(status, task=None):
    """Map authoritative status to display-only fields without hidden defaults."""
    if not isinstance(status, dict):
        raise ValueError("status must be an object")
    if task is not None and not isinstance(task, dict):
        raise ValueError("task must be an object")
    budget = status.get("budget") or {}
    usage = budget.get("token_usage") or {}
    assignments = status.get("assignments") or {}
    if not isinstance(assignments, dict):
        raise ValueError("invalid assignment summary")
    counts = {}
    for name in ("ready", "active", "waiting", "completed"):
        values = assignments.get(name, ())
        if not isinstance(values, (list, tuple)) or len(values) > 1024:
            raise ValueError("invalid assignment summary")
        counts[name] = len(values)
    task_state = status.get("state", "unknown")
    blocker = status.get("blocker") or status.get("blocked_reason")
    next_action = status.get("next_action")
    attention = status.get("attention")
    for value, name, limit in ((task_state, "stage", 128), (blocker, "blocker", 2048),
                               (next_action, "next action", 2048),
                               (attention, "attention", 2048)):
        if value is not None:
            _text(value, name, limit, required=False)
    routing = []
    routes = status.get("routing") or ()
    if not isinstance(routes, (list, tuple)) or len(routes) > 16:
        raise ValueError("invalid routing summary")
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("invalid routing summary")
        item = {"role": route.get("role"), "provider": route.get("provider"),
                "reason": route.get("reason")}
        _text(item["role"], "routing role", 128)
        _text(item["provider"], "routing provider", 128)
        _text(item["reason"], "routing reason", 1024)
        routing.append(item)
    state = {
        "stage": task_state,
        "ready": counts["ready"],
        "active": counts["active"],
        "waiting": counts["waiting"],
        "completed": counts["completed"],
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "usage_known": bool(usage) and all(value is not None for value in usage.values()),
        "authentication_required": task_state == "authentication_required",
        "candidate_stale": bool(status.get("candidate_stale")),
        "cancelled": task_state == "cancelled",
        "blocker": blocker,
        "next_action": next_action,
        "attention": attention,
        "routing": routing,
        "approval_recorded": False,
    }
    if task and task.get("head_revision") is not None:
        candidate = {"branch": task.get("branch"), "base_revision": task.get("base_revision"),
                     "head_revision": task.get("head_revision")}
        for key, value in candidate.items():
            _text(value, "candidate " + key, 512)
        state["candidate"] = candidate
    return state


def event_stream(events):
    return "\n".join(event.to_line() for event in events) + "\n"
