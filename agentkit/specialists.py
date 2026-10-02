"""Strict specialist and hash-bound skill context contracts.

Specialization refines an existing Phase 4 role.  It never creates execution,
filesystem, budget, approval, or publication authority; those remain owned by
the controller contracts that select and dispatch a specialist.
"""

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Mapping, Tuple

from .phase4_contracts import ModelRegistry, ROLE_CONTRACTS
from .resource_policy import CAPABILITY_PROFILES


SPECIALIST_SCHEMA_VERSION = 1
MAX_SPECIALIST_CONTEXT_BYTES = 32768
MAX_SKILL_BYTES = 8192
MAX_REFERENCE_BYTES = 8192
MAX_REFERENCES = 16

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[-_.:][a-z0-9]+)*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_AUTHORITY_TEXT = re.compile(
    r"(?:\$\(|`|\b(?:sudo|subprocess|shell|argv|command)\b|"
    r"\b(?:grant|record|exercise)\s+(?:approval|authority)\b|"
    r"\b(?:increase|extend|reset)\s+(?:budget|allocation)\b|"
    r"\b(?:publish|push|merge|deploy)\b)", re.IGNORECASE)


def _bounded_text(value, name, maximum=1024, *, authority_safe=False):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > maximum:
        raise ValueError(name + " must be a nonempty bounded string")
    value = value.strip()
    if authority_safe and _AUTHORITY_TEXT.search(value):
        raise ValueError(name + " embeds command or controller authority")
    return value


def _identifier(value, name):
    value = _bounded_text(value, name, 128)
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(name + " must be a normalized identifier")
    return value


def _identifier_tuple(value, name, *, allow_empty=False):
    if not isinstance(value, (tuple, list)) or (not value and not allow_empty):
        raise ValueError(name + " must be a bounded identifier sequence")
    if len(value) > 32:
        raise ValueError(name + " has too many entries")
    result = tuple(_identifier(item, name) for item in value)
    if len(set(result)) != len(result):
        raise ValueError(name + " contains duplicates")
    return result


def _positive_version(value, name):
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError(name + " must be a positive integer")
    return value


def _relative_path(value, name):
    value = _bounded_text(value, name, 512)
    if "\\" in value or "\x00" in value:
        raise ValueError(name + " must use a safe POSIX relative path")
    path = PurePosixPath(value)
    if (path.is_absolute() or value in (".", "") or ".." in path.parts or
            any(part in ("", ".") for part in path.parts) or
            path.parts[0] in (".git", "controller")):
        raise ValueError(name + " escapes the bundled context root")
    return value


@dataclass(frozen=True)
class ContextPolicy:
    max_total_bytes: int = 16384
    max_skill_bytes: int = MAX_SKILL_BYTES
    max_reference_bytes: int = MAX_REFERENCE_BYTES
    max_references: int = 8

    def __post_init__(self):
        values = (self.max_total_bytes, self.max_skill_bytes,
                  self.max_reference_bytes, self.max_references)
        if any(type(value) is not int for value in values):
            raise ValueError("context policy bounds must be integers")
        if not 1 <= self.max_total_bytes <= MAX_SPECIALIST_CONTEXT_BYTES:
            raise ValueError("specialist context exceeds the controller ceiling")
        if not 1 <= self.max_skill_bytes <= min(MAX_SKILL_BYTES, self.max_total_bytes):
            raise ValueError("invalid per-skill context bound")
        if not 1 <= self.max_reference_bytes <= min(MAX_REFERENCE_BYTES, self.max_total_bytes):
            raise ValueError("invalid per-reference context bound")
        if not 0 <= self.max_references <= MAX_REFERENCES:
            raise ValueError("invalid loaded-reference count")

    @classmethod
    def from_dict(cls, value):
        fields = {"max_total_bytes", "max_skill_bytes", "max_reference_bytes", "max_references"}
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("invalid specialist context policy")
        return cls(**value)


@dataclass(frozen=True)
class SpecialistProfile:
    profile_id: str
    profile_version: int
    base_role: str
    specialization: str
    activation_criteria: Tuple[str, ...]
    required_capabilities: Tuple[str, ...]
    output_schema_id: str
    output_schema_version: int
    eligible_model_profiles: Tuple[str, ...]
    default_skill_ids: Tuple[str, ...]
    context_policy: ContextPolicy
    completion_criteria: Tuple[str, ...]
    escalation_rules: Tuple[str, ...]
    schema_version: int = SPECIALIST_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SPECIALIST_SCHEMA_VERSION:
            raise ValueError("unsupported specialist profile schema")
        object.__setattr__(self, "profile_id", _identifier(self.profile_id, "profile id"))
        _positive_version(self.profile_version, "profile version")
        if self.base_role not in ROLE_CONTRACTS:
            raise ValueError("specialist must extend an existing base role")
        object.__setattr__(self, "specialization",
                           _identifier(self.specialization, "specialization"))
        object.__setattr__(self, "activation_criteria",
                           _identifier_tuple(self.activation_criteria, "activation criteria"))
        capabilities = _identifier_tuple(self.required_capabilities, "required capabilities")
        for capability in capabilities:
            if capability not in CAPABILITY_PROFILES:
                raise ValueError("specialist references an unknown capability profile")
            if capability not in ROLE_CONTRACTS[self.base_role].allowed_tools:
                raise ValueError("specialist capability escalates its base role")
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "output_schema_id",
                           _identifier(self.output_schema_id, "output schema id"))
        _positive_version(self.output_schema_version, "output schema version")
        object.__setattr__(self, "eligible_model_profiles",
                           _identifier_tuple(self.eligible_model_profiles,
                                             "eligible model profiles"))
        object.__setattr__(self, "default_skill_ids",
                           _identifier_tuple(self.default_skill_ids, "default skill ids",
                                             allow_empty=True))
        if not isinstance(self.context_policy, ContextPolicy):
            raise ValueError("specialist context policy must be validated")
        object.__setattr__(self, "completion_criteria",
                           _identifier_tuple(self.completion_criteria, "completion criteria"))
        object.__setattr__(self, "escalation_rules",
                           _identifier_tuple(self.escalation_rules, "escalation rules"))

    @classmethod
    def from_dict(cls, value):
        fields = {
            "profile_id", "profile_version", "base_role", "specialization",
            "activation_criteria", "required_capabilities", "output_schema_id",
            "output_schema_version", "eligible_model_profiles", "default_skill_ids",
            "context_policy", "completion_criteria", "escalation_rules", "schema_version",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("invalid or authority-bearing specialist profile fields")
        converted = dict(value)
        converted["context_policy"] = ContextPolicy.from_dict(value["context_policy"])
        for name in ("activation_criteria", "required_capabilities", "eligible_model_profiles",
                     "default_skill_ids", "completion_criteria", "escalation_rules"):
            converted[name] = tuple(value[name]) if isinstance(value[name], list) else value[name]
        return cls(**converted)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SkillReference:
    relative_path: str
    sha256: str
    encoded_byte_count: int

    def __post_init__(self):
        object.__setattr__(self, "relative_path",
                           _relative_path(self.relative_path, "skill reference path"))
        if not isinstance(self.sha256, str) or not _HASH.fullmatch(self.sha256):
            raise ValueError("skill reference hash must be lowercase SHA-256")
        if type(self.encoded_byte_count) is not int or not 0 < self.encoded_byte_count <= MAX_REFERENCE_BYTES:
            raise ValueError("invalid skill reference byte count")

    @classmethod
    def from_dict(cls, value):
        fields = {"relative_path", "sha256", "encoded_byte_count"}
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("invalid skill reference fields")
        return cls(**value)


@dataclass(frozen=True)
class SkillBinding:
    skill_id: str
    skill_version: int
    relative_source_path: str
    sha256: str
    source_reference: str
    license_reference: str
    selected_role: str
    selection_reason: str
    loaded_references: Tuple[SkillReference, ...]
    encoded_byte_count: int
    schema_version: int = SPECIALIST_SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SPECIALIST_SCHEMA_VERSION:
            raise ValueError("unsupported skill binding schema")
        object.__setattr__(self, "skill_id", _identifier(self.skill_id, "skill id"))
        _positive_version(self.skill_version, "skill version")
        object.__setattr__(self, "relative_source_path",
                           _relative_path(self.relative_source_path, "skill source path"))
        if not isinstance(self.sha256, str) or not _HASH.fullmatch(self.sha256):
            raise ValueError("skill source hash must be lowercase SHA-256")
        _bounded_text(self.source_reference, "skill source reference", 1024,
                      authority_safe=True)
        _bounded_text(self.license_reference, "skill license reference", 1024,
                      authority_safe=True)
        if self.selected_role not in ROLE_CONTRACTS:
            raise ValueError("skill binding role is unknown")
        object.__setattr__(self, "selection_reason",
                           _bounded_text(self.selection_reason, "skill selection reason", 1024,
                                         authority_safe=True))
        if (not isinstance(self.loaded_references, tuple) or
                any(not isinstance(item, SkillReference) for item in self.loaded_references) or
                len(self.loaded_references) > MAX_REFERENCES):
            raise ValueError("skill loaded references are invalid")
        paths = [item.relative_path for item in self.loaded_references]
        if len(paths) != len(set(paths)) or self.relative_source_path in paths:
            raise ValueError("skill binding contains duplicate content paths")
        if type(self.encoded_byte_count) is not int or not 0 < self.encoded_byte_count <= MAX_SPECIALIST_CONTEXT_BYTES:
            raise ValueError("invalid skill binding byte count")
        # The exact source size is checked at bind/dispatch, where source bytes
        # are available.  Even an empty source is invalid, so the total must be
        # strictly larger than the references alone.
        if self.encoded_byte_count <= sum(item.encoded_byte_count
                                          for item in self.loaded_references):
            raise ValueError("skill binding byte count is inconsistent")

    @classmethod
    def from_dict(cls, value):
        fields = {
            "skill_id", "skill_version", "relative_source_path", "sha256",
            "source_reference", "license_reference", "selected_role", "selection_reason",
            "loaded_references", "encoded_byte_count", "schema_version",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("invalid or authority-bearing skill binding fields")
        converted = dict(value)
        if not isinstance(value["loaded_references"], (list, tuple)):
            raise ValueError("loaded references must be a sequence")
        converted["loaded_references"] = tuple(
            SkillReference.from_dict(item) for item in value["loaded_references"])
        return cls(**converted)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SpecialistSelection:
    profile: SpecialistProfile
    model_profile_id: str
    authorized_capabilities: Tuple[str, ...]
    selected_skill_ids: Tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.profile, SpecialistProfile):
            raise ValueError("selection requires a validated specialist profile")
        _identifier(self.model_profile_id, "selected model profile")
        object.__setattr__(self, "authorized_capabilities",
                           _identifier_tuple(self.authorized_capabilities,
                                             "authorized capabilities"))
        object.__setattr__(self, "selected_skill_ids",
                           _identifier_tuple(self.selected_skill_ids, "selected skill ids",
                                             allow_empty=True))
        if not set(self.profile.required_capabilities) <= set(self.authorized_capabilities):
            raise ValueError("specialist selection expands capability authority")


def _model_is_compatible(profile, model_profile):
    required_modes = {CAPABILITY_PROFILES[item].mode for item in profile.required_capabilities}
    return (profile.base_role in model_profile.roles and
            required_modes <= set(model_profile.capabilities))


def _model_is_eligible(profile, model_profile):
    return (_model_is_compatible(profile, model_profile) and model_profile.enabled and
            model_profile.availability == "verified")


def validate_profile_compatibility(profile, model_registry):
    if not isinstance(profile, SpecialistProfile) or not isinstance(model_registry, ModelRegistry):
        raise ValueError("profile compatibility requires validated contracts")
    for profile_id in profile.eligible_model_profiles:
        model = model_registry.profiles.get(profile_id)
        if model is None or not _model_is_compatible(profile, model):
            raise ValueError("specialist names an ineligible role or model profile")
    return profile


def select_specialist(profiles, *, base_role, activation_criteria, required_capabilities,
                      model_registry, available_skill_ids, authorized_capabilities=None):
    """Choose the deterministic minimum profile inside controller authority."""
    if base_role not in ROLE_CONTRACTS:
        raise ValueError("unknown specialist base role")
    activated = set(_identifier_tuple(activation_criteria, "active criteria", allow_empty=True))
    required = set(_identifier_tuple(required_capabilities, "required capabilities"))
    authorized = set(_identifier_tuple(
        authorized_capabilities if authorized_capabilities is not None else required_capabilities,
        "authorized capabilities"))
    if not required <= authorized:
        raise ValueError("required capability exceeds controller authorization")
    for capability in authorized:
        if capability not in CAPABILITY_PROFILES or capability not in ROLE_CONTRACTS[base_role].allowed_tools:
            raise ValueError("authorized capability is incompatible with the base role")
    skills = set(_identifier_tuple(available_skill_ids, "available skill ids", allow_empty=True))
    candidates = []
    for profile in profiles:
        validate_profile_compatibility(profile, model_registry)
        profile_caps = set(profile.required_capabilities)
        if (profile.base_role != base_role or not required <= profile_caps <= authorized or
                not set(profile.activation_criteria) <= activated or
                not set(profile.default_skill_ids) <= skills):
            continue
        eligible_models = sorted(
            profile_id for profile_id in profile.eligible_model_profiles
            if _model_is_eligible(profile, model_registry.profiles[profile_id]))
        if eligible_models:
            score = (len(profile_caps), len(profile.default_skill_ids), profile.profile_id,
                     profile.profile_version, eligible_models[0])
            candidates.append((score, profile, eligible_models[0]))
    if not candidates:
        raise ValueError("no specialist satisfies activation, capability, skill, and model policy")
    _, profile, model_profile_id = min(candidates, key=lambda item: item[0])
    return SpecialistSelection(profile, model_profile_id, tuple(sorted(authorized)),
                               profile.default_skill_ids)


def _read_regular(root, relative, name):
    root = Path(root).resolve()
    relative = _relative_path(relative, name)
    target = root
    for part in PurePosixPath(relative).parts:
        target = target / part
        if target.is_symlink():
            raise ValueError(name + " must not contain a symlink")
    resolved = target.resolve()
    if resolved == root or root not in resolved.parents or not resolved.is_file():
        raise ValueError(name + " is not a regular contained file")
    content = resolved.read_bytes()
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(name + " must be UTF-8") from exc
    return content


def bind_skill(root, *, skill_id, skill_version, relative_source_path, source_reference,
               license_reference, selected_role, selection_reason, reference_paths=(),
               expected_sha256=None, expected_reference_hashes=None):
    """Create a binding only after validating the complete on-disk bundle."""
    source = _read_regular(root, relative_source_path, "skill source path")
    source_hash = hashlib.sha256(source).hexdigest()
    if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or not _HASH.fullmatch(expected_sha256)):
        raise ValueError("expected skill source hash must be lowercase SHA-256")
    if expected_sha256 is not None and expected_sha256 != source_hash:
        raise ValueError("skill source content changed before binding")
    if len(source) > MAX_SKILL_BYTES:
        raise ValueError("skill source exceeds the binding ceiling")
    if not isinstance(reference_paths, (tuple, list)) or len(reference_paths) > MAX_REFERENCES:
        raise ValueError("invalid skill reference paths")
    normalized_references = tuple(
        _relative_path(relative, "skill reference path") for relative in reference_paths)
    if len(normalized_references) != len(set(normalized_references)):
        raise ValueError("skill reference paths contain duplicates")
    if expected_reference_hashes is not None and not isinstance(expected_reference_hashes, Mapping):
        raise ValueError("expected reference hashes must be a mapping")
    expected = {} if expected_reference_hashes is None else dict(expected_reference_hashes)
    if expected_reference_hashes is not None and any(
            not isinstance(value, str) or not _HASH.fullmatch(value)
            for value in expected.values()):
        raise ValueError("expected skill reference hashes must be lowercase SHA-256")
    references = []
    for relative in sorted(normalized_references):
        content = _read_regular(root, relative, "skill reference path")
        if len(content) > MAX_REFERENCE_BYTES:
            raise ValueError("skill reference exceeds the binding ceiling")
        digest = hashlib.sha256(content).hexdigest()
        if expected_reference_hashes is not None and expected.get(relative) != digest:
            raise ValueError("skill reference content changed before binding")
        references.append(SkillReference(relative, digest, len(content)))
    if expected_reference_hashes is not None and set(expected) != set(normalized_references):
        raise ValueError("expected reference set does not match loaded references")
    total = len(source) + sum(item.encoded_byte_count for item in references)
    return SkillBinding(
        skill_id, skill_version, relative_source_path, source_hash,
        source_reference, license_reference, selected_role, selection_reason,
        tuple(references), total)


def verify_skill_binding(root, binding, policy):
    """Rehash one bound bundle immediately before dispatch or supported resume."""
    if not isinstance(binding, SkillBinding) or not isinstance(policy, ContextPolicy):
        raise ValueError("dispatch requires validated skill binding and context policy")
    source = _read_regular(root, binding.relative_source_path, "skill source path")
    if len(source) > policy.max_skill_bytes or hashlib.sha256(source).hexdigest() != binding.sha256:
        raise ValueError("skill source changed or exceeds context policy at dispatch")
    if len(binding.loaded_references) > policy.max_references:
        raise ValueError("skill binding has too many references for context policy")
    references = []
    for record in binding.loaded_references:
        content = _read_regular(root, record.relative_path, "skill reference path")
        if (len(content) > policy.max_reference_bytes or len(content) != record.encoded_byte_count or
                hashlib.sha256(content).hexdigest() != record.sha256):
            raise ValueError("skill reference changed or exceeds context policy at dispatch")
        references.append({"relative_path": record.relative_path, "sha256": record.sha256,
                           "content": content.decode("utf-8")})
    total = len(source) + sum(len(item["content"].encode("utf-8")) for item in references)
    if total != binding.encoded_byte_count or total > policy.max_total_bytes:
        raise ValueError("skill binding changed or exceeds total context policy")
    return {"schema_version": SPECIALIST_SCHEMA_VERSION, "skill_id": binding.skill_id,
            "skill_version": binding.skill_version, "relative_source_path": binding.relative_source_path,
            "sha256": binding.sha256, "encoded_byte_count": total,
            "content": source.decode("utf-8"), "loaded_references": references}


def assemble_specialist_context(root, selection, bindings, *, capability_profile_id,
                                model_profile_id):
    """Build bounded provider context without serializing controller authority."""
    if not isinstance(selection, SpecialistSelection):
        raise ValueError("specialist dispatch requires a validated selection")
    profile = selection.profile
    if (capability_profile_id not in profile.required_capabilities or
            capability_profile_id not in selection.authorized_capabilities):
        raise ValueError("dispatch capability would elevate or mismatch the specialist")
    if model_profile_id != selection.model_profile_id:
        raise ValueError("dispatch model is not the selected eligible model")
    by_id = {}
    for binding in bindings:
        if not isinstance(binding, SkillBinding) or binding.skill_id in by_id:
            raise ValueError("dispatch skill bindings are invalid or duplicated")
        by_id[binding.skill_id] = binding
    items = []
    total = 0
    for skill_id in selection.selected_skill_ids:
        binding = by_id.get(skill_id)
        if binding is None or binding.selected_role != profile.base_role:
            raise ValueError("selected skill is missing or incompatible with specialist role")
        item = verify_skill_binding(root, binding, profile.context_policy)
        total += item["encoded_byte_count"]
        if total > profile.context_policy.max_total_bytes:
            raise ValueError("specialist context exceeds its total bound")
        items.append(item)
    return {
        "schema_version": SPECIALIST_SCHEMA_VERSION,
        "profile": {"id": profile.profile_id, "version": profile.profile_version,
                    "base_role": profile.base_role, "specialization": profile.specialization},
        "output_contract": {"id": profile.output_schema_id,
                            "version": profile.output_schema_version},
        "model_profile_id": model_profile_id,
        "capability_profile_id": capability_profile_id,
        "encoded_byte_count": total,
        "skills": items,
    }
