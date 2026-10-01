"""Public provider-profile resolution adapted from OpenHarness settings.

The upstream settings model mixes UI/profile data with authentication, base
URLs, provider defaults, hooks, tools, and runtime policy. This adapter keeps
only display/routing inputs and rejects fields that could alter authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json


_PROVIDERS = frozenset(("codex", "claude"))
_CAPABILITIES = frozenset((
    "structured-planning", "code-implementation", "independent-review",
    "web-product-implementation", "smoke-model-only",
))
_FIELDS = frozenset(("profile_id", "provider", "model", "effort", "capability_profile"))
_FORBIDDEN = frozenset((
    "api_key", "auth_source", "base_url", "credential_slot", "environment",
    "max_tokens", "max_turns", "retries", "timeout", "tools", "permissions",
))


@dataclass(frozen=True)
class PublicProviderProfile:
    profile_id: str
    provider: str
    model: str | None = None
    effort: str | None = None
    capability_profile: str = "structured-planning"

    def __post_init__(self):
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile_id is required")
        if self.provider not in _PROVIDERS:
            raise ValueError("unsupported profile provider")
        if self.model is not None and (not isinstance(self.model, str) or not self.model.strip()):
            raise ValueError("model must be a non-empty string or null")
        if self.effort is not None and (not isinstance(self.effort, str) or not self.effort.strip()):
            raise ValueError("effort must be a non-empty string or null")
        if self.capability_profile not in _CAPABILITIES:
            raise ValueError("unsupported capability profile")

    def to_dict(self):
        return asdict(self)

    @property
    def sha256(self):
        return hashlib.sha256(_canonical(self.to_dict())).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse_profile(value):
    if not isinstance(value, dict):
        raise ValueError("provider profile must be an object")
    forbidden = sorted(set(value) & _FORBIDDEN)
    if forbidden:
        raise ValueError("provider profile contains authority-bearing fields: " + ", ".join(forbidden))
    unknown = sorted(set(value) - _FIELDS)
    if unknown:
        raise ValueError("unknown provider profile fields: " + ", ".join(unknown))
    missing = sorted(("profile_id", "provider") - set(value))
    if missing:
        raise ValueError("missing provider profile fields: " + ", ".join(missing))
    return PublicProviderProfile(**value)


def resolve_profile(base, *, role_policy=None, task_override=None, expected_sha256=None):
    """Resolve public routing fields with task > role > base precedence.

    The expected hash binds the base profile selected by a trusted controller.
    Overrides cannot change provider, profile identity, or capability profile.
    """
    profile = parse_profile(base) if isinstance(base, dict) else base
    if not isinstance(profile, PublicProviderProfile):
        raise ValueError("invalid base provider profile")
    if expected_sha256 is not None and profile.sha256 != expected_sha256:
        raise ValueError("provider profile content changed after enrollment")
    provenance = {key: "profile" for key in ("provider", "model", "effort", "capability_profile")}
    for source, override in (("role-policy", role_policy), ("task-override", task_override)):
        if override is None:
            continue
        if not isinstance(override, dict) or set(override) - {"model", "effort"}:
            raise ValueError(source + " may override only model and effort")
        for key, value in override.items():
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(source + " values must be non-empty strings or null")
            profile = replace(profile, **{key: value})
            provenance[key] = source
    return {"profile": profile.to_dict(), "base_sha256": profile_sha256(base),
            "resolved_sha256": profile.sha256, "provenance": provenance}


def profile_sha256(value):
    profile = parse_profile(value) if isinstance(value, dict) else value
    if not isinstance(profile, PublicProviderProfile):
        raise ValueError("invalid provider profile")
    return profile.sha256
