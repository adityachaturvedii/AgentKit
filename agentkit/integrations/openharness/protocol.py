"""Strict controller UI protocol adapted from OpenHarness ``ui/protocol.py``.

The original generic assistant protocol exposed prompt, permission, tool, and
session commands. R0 intentionally exposes only read/status, deterministic
fixture start, cancellation, and shutdown. There is no approval command.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 65536
REQUEST_TYPES = frozenset(("snapshot", "run_demo", "cancel", "shutdown"))
EVENT_TYPES = frozenset((
    "ready", "state_snapshot", "transcript_item", "package_ready", "error", "shutdown",
))


def _text(value, name, limit=512, *, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > limit:
        raise ValueError("invalid " + name)
    return value


@dataclass(frozen=True)
class FrontendRequest:
    type: str
    task_id: str | None = None
    version: int = PROTOCOL_VERSION

    def __post_init__(self):
        if self.version != PROTOCOL_VERSION or self.type not in REQUEST_TYPES:
            raise ValueError("unsupported frontend request")
        if self.type in ("snapshot", "cancel"):
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
        if not isinstance(value, dict) or set(value) - {"version", "type", "task_id"}:
            raise ValueError("invalid frontend request shape")
        return cls(**value)


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    state: str
    objective: str
    next_action: str | None
    head_revision: str | None


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
        if self.version != PROTOCOL_VERSION or self.type not in EVENT_TYPES:
            raise ValueError("unsupported backend event")
        if self.message is not None:
            _text(self.message, "event message", 4096, required=False)
        if self.item is not None:
            if not isinstance(self.item, dict) or set(self.item) != {"role", "text"}:
                raise ValueError("invalid transcript item")
            if self.item["role"] not in ("system", "status", "assistant", "log"):
                raise ValueError("invalid transcript role")
            _text(self.item["text"], "transcript text", 8192, required=False)

    def to_dict(self):
        value = asdict(self)
        return {key: item for key, item in value.items() if item is not None}

    def to_line(self):
        line = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("backend event exceeds byte bound")
        return line


def safe_ui_state(status):
    """Map authoritative status to display-only fields without hidden defaults."""
    if not isinstance(status, dict):
        raise ValueError("status must be an object")
    budget = status.get("budget") or {}
    usage = budget.get("token_usage") or {}
    assignments = status.get("assignments") or {}
    task_state = status.get("state", "unknown")
    blocker = status.get("blocker") or status.get("blocked_reason")
    return {
        "stage": task_state,
        "ready": len(assignments.get("ready", ())),
        "active": len(assignments.get("active", ())),
        "waiting": len(assignments.get("waiting", ())),
        "completed": len(assignments.get("completed", ())),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "usage_known": bool(usage) and all(value is not None for value in usage.values()),
        "authentication_required": task_state == "authentication_required",
        "candidate_stale": bool(status.get("candidate_stale")),
        "cancelled": task_state == "cancelled",
        "blocker": blocker,
        "approval_recorded": False,
    }


def event_stream(events):
    return "\n".join(event.to_line() for event in events) + "\n"
