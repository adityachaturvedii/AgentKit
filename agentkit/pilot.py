"""Offline, authority-free records for the exploratory P14 matched pilot."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import tempfile

from .integrations.openharness.fs import atomic_private_write
from .validation import read_json


SCHEMA_VERSION = 1
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REVISION = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
OUTCOMES = {"completed", "failed", "blocked", "cancelled", "withdrawn", "timed_out",
            "authentication_required", "not_run"}
TERMINAL_REASONS = {"none", "authentication", "quota", "network", "permission",
                    "execution", "verification", "timeout", "cancellation",
                    "environment", "participant_withdrew", "not_started", "other"}
ACCEPTANCE = {"passed", "failed", "not_assessed"}
ATTEMPT_STATUS = {"completed", "failed", "blocked", "cancelled", "authentication_required"}
CHECK_KINDS = {"existing_project", "agent_authored", "protected_acceptance", "human_observation"}
CHECK_STATUS = {"passed", "failed", "omitted", "manual", "empty"}


class PilotError(ValueError):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _object(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise PilotError(where + " fields do not match schema")


def _identifier(value, where):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise PilotError(where + " is not a valid identifier")
    return value


def _text(value, where, maximum=256):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > maximum:
        raise PilotError(where + " must be bounded nonempty text")
    return value


def _sha(value, where, *, revision=False, nullable=False):
    if nullable and value is None:
        return value
    pattern = REVISION if revision else SHA256
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise PilotError(where + " is not a valid hash")
    return value


def _integer(value, where, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise PilotError(where + " must be an integer >= " + str(minimum))
    return value


def _number(value, where, *, nullable=False):
    if nullable and value is None:
        return value
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise PilotError(where + " must be a finite nonnegative number or null")
    return value


def _utc_timestamp(value, where, *, nullable=False):
    if nullable and value is None:
        return None
    _text(value, where, 32)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PilotError(where + " must use UTC YYYY-MM-DDTHH:MM:SSZ") from exc
    return parsed.replace(tzinfo=timezone.utc)


def _enum(value, allowed, where):
    if value not in allowed or not isinstance(value, str):
        raise PilotError(where + " has an unknown value")
    return value


def _unique(values, where):
    if len(values) != len(set(values)):
        raise PilotError(where + " contains duplicates")


def _validate_protocol(value):
    _object(value, ("schema_version", "pilot_id", "title", "randomization_seed",
                    "consent_version", "provider_disclosure_sha256",
                    "retention_policy_sha256", "conditions", "participants", "tasks"),
            "protocol")
    if value["schema_version"] != SCHEMA_VERSION or type(value["schema_version"]) is not int:
        raise PilotError("unsupported protocol schema")
    _identifier(value["pilot_id"], "pilot_id")
    _text(value["title"], "title")
    _text(value["randomization_seed"], "randomization_seed", 512)
    _identifier(value["consent_version"], "consent_version")
    _sha(value["provider_disclosure_sha256"], "provider_disclosure_sha256")
    _sha(value["retention_policy_sha256"], "retention_policy_sha256")
    if not isinstance(value["conditions"], list) or len(value["conditions"]) != 2:
        raise PilotError("protocol requires exactly two conditions")
    condition_fields = ("condition_id", "mode", "provider", "model", "effort",
                        "execution_profile", "call_limit", "time_limit_seconds")
    conditions = {}
    for condition in value["conditions"]:
        _object(condition, condition_fields, "condition")
        condition_id = _identifier(condition["condition_id"], "condition_id")
        mode = _enum(condition["mode"], {"direct_cli", "agentkit"}, "condition mode")
        if condition_id != mode:
            raise PilotError("condition_id must equal its condition mode")
        for field in ("provider", "model", "effort", "execution_profile"):
            _text(condition[field], "condition " + field)
        _integer(condition["call_limit"], "condition call_limit", minimum=1)
        _number(condition["time_limit_seconds"], "condition time_limit_seconds")
        if condition["time_limit_seconds"] <= 0:
            raise PilotError("condition time_limit_seconds must be positive")
        conditions[mode] = condition
    if set(conditions) != {"direct_cli", "agentkit"}:
        raise PilotError("protocol requires direct_cli and agentkit conditions")
    matched = ("provider", "model", "effort", "execution_profile", "call_limit",
               "time_limit_seconds")
    if any(conditions["direct_cli"][field] != conditions["agentkit"][field]
           for field in matched):
        raise PilotError("pilot condition configuration is not matched")
    participants = value["participants"]
    if not isinstance(participants, list) or len(participants) < 2:
        raise PilotError("pilot requires at least two participants")
    participant_ids = []
    for participant in participants:
        _object(participant, ("participant_id", "local_evaluation_consent",
                              "artifact_sharing_consent"), "participant")
        participant_ids.append(_identifier(participant["participant_id"], "participant_id"))
        if participant["local_evaluation_consent"] is not True:
            raise PilotError("every participant must opt in to local evaluation")
        if type(participant["artifact_sharing_consent"]) is not bool:
            raise PilotError("artifact sharing consent must be boolean")
    _unique(participant_ids, "participant identifiers")
    tasks = value["tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise PilotError("pilot requires at least one task")
    task_ids = []
    for task in tasks:
        _object(task, ("task_id", "project_id", "base_revision", "task_contract_sha256",
                       "acceptance_sha256", "stratum", "follow_up_days"), "task")
        task_ids.append(_identifier(task["task_id"], "task_id"))
        _identifier(task["project_id"], "project_id")
        _sha(task["base_revision"], "base_revision", revision=True)
        _sha(task["task_contract_sha256"], "task_contract_sha256")
        _sha(task["acceptance_sha256"], "acceptance_sha256")
        _identifier(task["stratum"], "stratum")
        _integer(task["follow_up_days"], "follow_up_days", minimum=1)
    _unique(task_ids, "task identifiers")
    return json.loads(_json(value))


def _assignments(protocol, protocol_sha256):
    participants = [item["participant_id"] for item in protocol["participants"]]
    by_stratum = {}
    for task in protocol["tasks"]:
        by_stratum.setdefault(task["stratum"], []).append(task)
    result = []
    for stratum in sorted(by_stratum):
        tasks = sorted(by_stratum[stratum], key=lambda item: item["task_id"])
        seed = hashlib.sha256((protocol["randomization_seed"] + "\0" + stratum).encode()).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        order = list(participants)
        rng.shuffle(order)
        first_mode = rng.randrange(2)
        for index, task in enumerate(tasks):
            first = order[index % len(order)]
            second = order[(index + 1) % len(order)]
            modes = ("direct_cli", "agentkit") if (index + first_mode) % 2 == 0 else (
                "agentkit", "direct_cli")
            for sequence, (mode, participant_id) in enumerate(zip(modes, (first, second)), 1):
                assignment = {
                    "schema_version": SCHEMA_VERSION,
                    "assignment_id": "assignment-" + hashlib.sha256(
                        (protocol["pilot_id"] + "\0" + task["task_id"] + "\0" + mode).encode()
                    ).hexdigest()[:20],
                    "protocol_sha256": protocol_sha256,
                    "task_id": task["task_id"],
                    "participant_id": participant_id,
                    "condition_id": mode,
                    "order_in_task": sequence,
                }
                assignment["assignment_sha256"] = _hash(assignment)
                result.append(assignment)
    return sorted(result, key=lambda item: item["assignment_id"])


def _requested_root(root, *, fresh=False):
    path = Path(root).expanduser()
    if path.exists() or path.is_symlink():
        if fresh:
            raise PilotError("pilot root must be fresh")
        if path.is_symlink() or not path.is_dir():
            raise PilotError("pilot root must be a real directory")
    elif not fresh:
        raise PilotError("pilot root does not exist")
    return path.absolute()


def _read(root, relative):
    target = root / relative
    if target.is_symlink() or not target.is_file():
        raise PilotError(relative + " is missing or invalid")
    try:
        return read_json(target)
    except (OSError, ValueError) as exc:
        raise PilotError(relative + " is malformed") from exc


def _load(root):
    root = _requested_root(root)
    protocol_record = _read(root, "protocol.json")
    _object(protocol_record, ("schema_version", "frozen", "protocol_sha256", "protocol"),
            "stored protocol")
    protocol = _validate_protocol(protocol_record["protocol"])
    if (protocol_record["schema_version"] != SCHEMA_VERSION or protocol_record["frozen"] is not True or
            protocol_record["protocol_sha256"] != _hash(protocol)):
        raise PilotError("stored protocol integrity check failed")
    manifest = _read(root, "assignments.json")
    _object(manifest, ("schema_version", "protocol_sha256", "assignments"),
            "assignment manifest")
    expected = _assignments(protocol, protocol_record["protocol_sha256"])
    if (manifest["schema_version"] != SCHEMA_VERSION or
            manifest["protocol_sha256"] != protocol_record["protocol_sha256"] or
            manifest["assignments"] != expected):
        raise PilotError("assignment manifest integrity check failed")
    return root, protocol, protocol_record["protocol_sha256"], expected


def initialize_pilot(root, protocol):
    """Validate and atomically install one frozen, deterministically assigned pilot."""
    target = _requested_root(root, fresh=True)
    protocol = _validate_protocol(protocol)
    protocol_sha256 = _hash(protocol)
    assignments = _assignments(protocol, protocol_sha256)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.parent.is_symlink():
        raise PilotError("pilot parent cannot be a symlink")
    temporary = Path(tempfile.mkdtemp(prefix="." + target.name + ".", dir=str(target.parent)))
    os.chmod(temporary, 0o700)
    try:
        atomic_private_write(temporary / "protocol.json", _json({
            "schema_version": SCHEMA_VERSION, "frozen": True,
            "protocol_sha256": protocol_sha256, "protocol": protocol,
        }) + "\n")
        atomic_private_write(temporary / "assignments.json", _json({
            "schema_version": SCHEMA_VERSION, "protocol_sha256": protocol_sha256,
            "assignments": assignments,
        }) + "\n")
        (temporary / "observations").mkdir(mode=0o700)
        (temporary / "feedback").mkdir(mode=0o700)
        os.rename(temporary, target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return pilot_status(target)


def _assignment_map(assignments):
    return {item["assignment_id"]: item for item in assignments}


def _record_file(root, directory, identifier, value):
    folder = root / directory
    if folder.is_symlink() or not folder.is_dir():
        raise PilotError(directory + " directory is invalid")
    target = folder / (identifier + ".json")
    if target.exists() or target.is_symlink():
        raise PilotError(directory[:-1] + " record already exists")
    payload = (_json(value) + "\n").encode("utf-8")
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise PilotError(directory[:-1] + " record already exists") from exc


def _nullable_text(value, where):
    if value is None:
        return value
    return _text(value, where)


def _validate_observation(value, protocol, protocol_sha256, assignments):
    fields = ("schema_version", "observation_id", "assignment_id", "assignment_sha256",
              "protocol_sha256", "terminal_outcome", "terminal_reason", "first_pass_acceptance",
              "final_acceptance", "acceptance_at_utc", "follow_up_observed_at_utc",
              "merge_status", "wall_seconds",
              "wall_seconds_unavailable_reason", "human_minutes", "intervention_count",
              "attempts", "checks", "evidence", "quality")
    _object(value, fields, "observation")
    if value["schema_version"] != SCHEMA_VERSION or type(value["schema_version"]) is not int:
        raise PilotError("unsupported observation schema")
    _identifier(value["observation_id"], "observation_id")
    assignment_id = _identifier(value["assignment_id"], "assignment_id")
    assignment = _assignment_map(assignments).get(assignment_id)
    if not assignment or value["assignment_sha256"] != assignment["assignment_sha256"]:
        raise PilotError("observation assignment binding is stale or invalid")
    if value["protocol_sha256"] != protocol_sha256:
        raise PilotError("observation protocol binding is stale")
    outcome = _enum(value["terminal_outcome"], OUTCOMES, "terminal_outcome")
    reason = _enum(value["terminal_reason"], TERMINAL_REASONS, "terminal_reason")
    if (outcome == "completed") != (reason == "none"):
        raise PilotError("only completed outcomes use terminal reason none")
    required_reasons = {
        "authentication_required": "authentication", "timed_out": "timeout",
        "cancelled": "cancellation", "withdrawn": "participant_withdrew",
    }
    if outcome in required_reasons and reason != required_reasons[outcome]:
        raise PilotError("terminal reason does not match terminal outcome")
    first = _enum(value["first_pass_acceptance"], ACCEPTANCE, "first_pass_acceptance")
    final = _enum(value["final_acceptance"], ACCEPTANCE, "final_acceptance")
    accepted_at = _utc_timestamp(value["acceptance_at_utc"], "acceptance_at_utc", nullable=True)
    follow_up_at = _utc_timestamp(
        value["follow_up_observed_at_utc"], "follow_up_observed_at_utc", nullable=True)
    if (final == "passed") != (accepted_at is not None):
        raise PilotError("passed final acceptance requires its UTC observation time")
    if first == "passed" and final != "passed":
        raise PilotError("first-pass acceptance cannot exceed final acceptance")
    _enum(value["merge_status"], {"merged", "not_merged", "not_applicable", "unknown"},
          "merge_status")
    _number(value["wall_seconds"], "wall_seconds", nullable=True)
    _nullable_text(value["wall_seconds_unavailable_reason"], "wall_seconds_unavailable_reason")
    if (value["wall_seconds"] is None) == (value["wall_seconds_unavailable_reason"] is None):
        raise PilotError("wall time requires exactly one value or unavailable reason")
    if outcome != "completed" and (first != "not_assessed" or final == "passed"):
        raise PilotError("non-completed outcomes cannot claim assessed first pass or final success")
    minutes = value["human_minutes"]
    _object(minutes, ("setup", "operator_intervention", "review", "source_edit"),
            "human_minutes")
    for name, amount in minutes.items():
        _number(amount, "human_minutes." + name, nullable=True)
    if first == "passed" and minutes["source_edit"] != 0:
        raise PilotError("first-pass acceptance requires observed zero human source-edit minutes")
    _integer(value["intervention_count"], "intervention_count")
    if not isinstance(value["attempts"], list):
        raise PilotError("attempts must be an array")
    attempt_ids = []
    condition = next(item for item in protocol["conditions"]
                     if item["condition_id"] == assignment["condition_id"])
    for attempt in value["attempts"]:
        _object(attempt, ("attempt_id", "status", "requested", "reported", "elapsed_seconds",
                          "usage", "estimated_cost_usd", "billed_cost_usd", "cost_source"),
                "attempt")
        attempt_ids.append(_identifier(attempt["attempt_id"], "attempt_id"))
        _enum(attempt["status"], ATTEMPT_STATUS, "attempt status")
        _object(attempt["requested"], ("provider", "model", "effort"), "requested settings")
        for name in ("provider", "model", "effort"):
            _text(attempt["requested"][name], "requested " + name)
            if attempt["requested"][name] != condition[name]:
                raise PilotError("attempt requested settings do not match frozen condition")
        _object(attempt["reported"], ("provider", "model", "effort"), "reported settings")
        for name in ("provider", "model", "effort"):
            _nullable_text(attempt["reported"][name], "reported " + name)
        _number(attempt["elapsed_seconds"], "attempt elapsed_seconds", nullable=True)
        usage = attempt["usage"]
        _object(usage, ("input_tokens", "output_tokens", "cached_input_tokens",
                        "cache_creation_tokens", "reasoning_tokens"), "usage")
        for name, amount in usage.items():
            if amount is not None:
                _integer(amount, "usage." + name)
        _number(attempt["estimated_cost_usd"], "estimated_cost_usd", nullable=True)
        _number(attempt["billed_cost_usd"], "billed_cost_usd", nullable=True)
        if attempt["estimated_cost_usd"] is None and attempt["billed_cost_usd"] is None:
            if attempt["cost_source"] is not None:
                raise PilotError("unknown costs require a null cost_source")
        else:
            _text(attempt["cost_source"], "cost_source")
    _unique(attempt_ids, "attempt identifiers")
    if outcome in {"completed", "failed"} and not value["attempts"]:
        raise PilotError("completed and failed observations require an attempt")
    if not isinstance(value["checks"], list):
        raise PilotError("checks must be an array")
    check_ids = []
    for check in value["checks"]:
        _object(check, ("check_id", "kind", "status", "identity_sha256"), "check")
        check_ids.append(_identifier(check["check_id"], "check_id"))
        _enum(check["kind"], CHECK_KINDS, "check kind")
        _enum(check["status"], CHECK_STATUS, "check status")
        _sha(check["identity_sha256"], "check identity", nullable=True)
    _unique(check_ids, "check identifiers")
    evidence = value["evidence"]
    evidence_fields = ("runtime_sha256", "policy_sha256", "skills_sha256",
                       "acceptance_sha256", "candidate_sha256", "package_sha256")
    _object(evidence, evidence_fields, "evidence")
    for name in evidence_fields:
        _sha(evidence[name], "evidence." + name, nullable=name != "acceptance_sha256")
    task = next(item for item in protocol["tasks"] if item["task_id"] == assignment["task_id"])
    if evidence["acceptance_sha256"] != task["acceptance_sha256"]:
        raise PilotError("observation acceptance identity does not match the task")
    protected_pass = any(
        check["kind"] == "protected_acceptance" and check["status"] == "passed" and
        check["identity_sha256"] == task["acceptance_sha256"]
        for check in value["checks"])
    if (first == "passed" or final == "passed") and not protected_pass:
        raise PilotError("passed acceptance requires a passing task-bound protected check")
    quality = value["quality"]
    _object(quality, ("follow_up_complete", "escaped_defects", "findings",
                      "unnecessary_repairs", "repair_cycles"), "quality")
    if type(quality["follow_up_complete"]) is not bool:
        raise PilotError("follow_up_complete must be boolean")
    if quality["follow_up_complete"]:
        if outcome != "completed" or final != "passed" or accepted_at is None or follow_up_at is None:
            raise PilotError("completed follow-up requires an accepted completed candidate")
        if (follow_up_at - accepted_at).total_seconds() < task["follow_up_days"] * 86400:
            raise PilotError("follow-up observation predates the frozen observation window")
        if quality["escaped_defects"] is None:
            raise PilotError("completed follow-up requires escaped-defect count")
        _integer(quality["escaped_defects"], "escaped_defects")
    elif quality["escaped_defects"] is not None or follow_up_at is not None:
        raise PilotError("incomplete follow-up must leave time and escaped defects unknown")
    _object(quality["findings"], ("true_positive", "false_positive", "unresolved"), "findings")
    for name, count in quality["findings"].items():
        _integer(count, "findings." + name)
    _integer(quality["unnecessary_repairs"], "unnecessary_repairs")
    _integer(quality["repair_cycles"], "repair_cycles")
    return json.loads(_json(value))


def record_observation(root, observation):
    root, protocol, protocol_sha256, assignments = _load(root)
    value = _validate_observation(observation, protocol, protocol_sha256, assignments)
    assignment_id = value["assignment_id"]
    value["record_sha256"] = _hash(value)
    _record_file(root, "observations", assignment_id, value)
    return value


def _validate_feedback(value, protocol_sha256, assignments):
    _object(value, ("schema_version", "feedback_id", "assignment_id", "assignment_sha256",
                    "protocol_sha256", "evidence_usefulness", "evidence_understandable",
                    "limitations_understood", "review_confidence", "would_use_again"), "feedback")
    if value["schema_version"] != SCHEMA_VERSION or type(value["schema_version"]) is not int:
        raise PilotError("unsupported feedback schema")
    _identifier(value["feedback_id"], "feedback_id")
    assignment = _assignment_map(assignments).get(value["assignment_id"])
    if not assignment or value["assignment_sha256"] != assignment["assignment_sha256"]:
        raise PilotError("feedback assignment binding is stale or invalid")
    if value["protocol_sha256"] != protocol_sha256:
        raise PilotError("feedback protocol binding is stale")
    _enum(value["evidence_usefulness"],
          {"very_unhelpful", "unhelpful", "neutral", "helpful", "very_helpful"},
          "evidence_usefulness")
    for name in ("evidence_understandable", "limitations_understood"):
        if type(value[name]) is not bool:
            raise PilotError(name + " must be boolean")
    _enum(value["review_confidence"], {"lower", "same", "higher"}, "review_confidence")
    _enum(value["would_use_again"], {"yes", "no", "unsure"}, "would_use_again")
    return json.loads(_json(value))


def record_feedback(root, feedback):
    root, _, protocol_sha256, assignments = _load(root)
    value = _validate_feedback(feedback, protocol_sha256, assignments)
    value["record_sha256"] = _hash(value)
    _record_file(root, "feedback", value["assignment_id"], value)
    return value


def _records(root, directory, validator=None):
    folder = root / directory
    if folder.is_symlink() or not folder.is_dir():
        raise PilotError(directory + " directory is invalid")
    result = []
    for path in sorted(folder.iterdir()):
        if path.is_symlink() or not path.is_file() or path.suffix != ".json" or not ID.fullmatch(path.stem):
            raise PilotError(directory + " contains an invalid record")
        value = _read(root, directory + "/" + path.name)
        if value.get("assignment_id") != path.stem:
            raise PilotError(directory + " record filename does not match its assignment")
        digest = value.pop("record_sha256", None)
        if digest != _hash(value):
            raise PilotError(directory + " record integrity check failed")
        if validator is not None and validator(value) != value:
            raise PilotError(directory + " record normalization mismatch")
        value["record_sha256"] = digest
        result.append(value)
    return result


def pilot_status(root):
    root, protocol, protocol_sha256, assignments = _load(root)
    observations = _records(
        root, "observations",
        lambda value: _validate_observation(value, protocol, protocol_sha256, assignments))
    feedback = _records(
        root, "feedback", lambda value: _validate_feedback(value, protocol_sha256, assignments))
    assignment_by_id = _assignment_map(assignments)
    conditions = {item["condition_id"]: item for item in protocol["conditions"]}
    reported_deviation_count = 0
    total_deviation_count = 0
    for observation in observations:
        condition = conditions[assignment_by_id[observation["assignment_id"]]["condition_id"]]
        known_elapsed = sum(attempt["elapsed_seconds"] for attempt in observation["attempts"]
                            if attempt["elapsed_seconds"] is not None)
        reported_deviation = any(
            attempt["reported"][field] is not None and
            attempt["reported"][field] != condition[field]
            for attempt in observation["attempts"]
            for field in ("provider", "model", "effort"))
        reported_deviation_count += int(reported_deviation)
        total_deviation_count += int(
            reported_deviation or len(observation["attempts"]) > condition["call_limit"] or
            known_elapsed > condition["time_limit_seconds"])
    return {
        "schema_version": SCHEMA_VERSION, "pilot_id": protocol["pilot_id"],
        "protocol_sha256": protocol_sha256, "state": "frozen_collecting",
        "assignment_count": len(assignments), "observation_count": len(observations),
        "missing_observation_count": len(assignments) - len(observations),
        "feedback_count": len(feedback),
        "observations_with_reported_setting_deviation": reported_deviation_count,
        "observations_with_matching_or_resource_deviation": total_deviation_count,
        "execution_authority": False,
    }


def _distribution(values):
    if not values:
        return {"count": 0, "median": None, "minimum": None, "maximum": None}
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = (ordered[middle] if len(ordered) % 2 else
              (ordered[middle - 1] + ordered[middle]) / 2)
    return {"count": len(values), "median": median,
            "minimum": ordered[0], "maximum": ordered[-1]}


def _rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def build_report(root):
    root, protocol, protocol_sha256, assignments = _load(root)
    observations = _records(
        root, "observations",
        lambda value: _validate_observation(value, protocol, protocol_sha256, assignments))
    feedback = _records(
        root, "feedback", lambda value: _validate_feedback(value, protocol_sha256, assignments))
    by_assignment = {item["assignment_id"]: item for item in observations}
    conditions = {}
    deviating_assignments = set()
    for mode in ("direct_cli", "agentkit"):
        cells = [item for item in assignments if item["condition_id"] == mode]
        observed = [by_assignment[item["assignment_id"]] for item in cells
                    if item["assignment_id"] in by_assignment]
        outcomes = Counter(item["terminal_outcome"] for item in observed)
        reasons = Counter(item["terminal_reason"] for item in observed)
        first = Counter(item["first_pass_acceptance"] for item in observed)
        final = Counter(item["final_acceptance"] for item in observed)
        attempts = [attempt for item in observed for attempt in item["attempts"]]
        frozen_condition = next(item for item in protocol["conditions"]
                                if item["condition_id"] == mode)
        deviation_fields = Counter()
        unknown_fields = Counter()
        deviating_attempts = set()
        deviating_observations = set()
        for item in observed:
            for attempt in item["attempts"]:
                for field in ("provider", "model", "effort"):
                    reported = attempt["reported"][field]
                    if reported is None:
                        unknown_fields[field] += 1
                    elif reported != frozen_condition[field]:
                        deviation_fields[field] += 1
                        deviating_attempts.add((item["assignment_id"], attempt["attempt_id"]))
                        deviating_observations.add(item["assignment_id"])
        resource_deviation_observations = set()
        call_limit_observations = 0
        time_limit_observations = 0
        for item in observed:
            over_calls = len(item["attempts"]) > frozen_condition["call_limit"]
            known_elapsed = sum(attempt["elapsed_seconds"] for attempt in item["attempts"]
                                if attempt["elapsed_seconds"] is not None)
            over_time = known_elapsed > frozen_condition["time_limit_seconds"]
            call_limit_observations += int(over_calls)
            time_limit_observations += int(over_time)
            if over_calls or over_time:
                resource_deviation_observations.add(item["assignment_id"])
        for item in observed:
            if (item["assignment_id"] in deviating_observations or
                    item["assignment_id"] in resource_deviation_observations):
                deviating_assignments.add(item["assignment_id"])
        human_totals = [sum(item["human_minutes"].values()) for item in observed
                        if all(value is not None for value in item["human_minutes"].values())]
        human_effort = {}
        for name in ("setup", "operator_intervention", "review", "source_edit"):
            known = [item["human_minutes"][name] for item in observed
                     if item["human_minutes"][name] is not None]
            human_effort[name] = {"distribution": _distribution(known),
                                  "unknown_observations": len(observed) - len(known)}
        usage = {}
        for name in ("input_tokens", "output_tokens", "cached_input_tokens",
                     "cache_creation_tokens", "reasoning_tokens"):
            known = [attempt["usage"][name] for attempt in attempts
                     if attempt["usage"][name] is not None]
            usage[name] = {"total_known": sum(known), "known_attempts": len(known),
                           "unknown_attempts": len(attempts) - len(known)}
        costs = {}
        for name in ("estimated_cost_usd", "billed_cost_usd"):
            known = [attempt[name] for attempt in attempts if attempt[name] is not None]
            costs[name] = {"total_known": sum(known), "known_attempts": len(known),
                           "unknown_attempts": len(attempts) - len(known)}
        follow_up = [item["quality"]["escaped_defects"] for item in observed
                     if item["quality"]["follow_up_complete"]]
        conditions[mode] = {
            "assigned_denominator": len(cells), "observed": len(observed),
            "missing": len(cells) - len(observed),
            "terminal_outcomes": {name: outcomes[name] for name in sorted(OUTCOMES)},
            "terminal_reasons": {name: reasons[name] for name in sorted(TERMINAL_REASONS)},
            "rates": {
                "completion": _rate(outcomes["completed"], len(cells)),
                "first_pass_acceptance": _rate(first["passed"], len(cells)),
                "final_acceptance": _rate(final["passed"], len(cells)),
            },
            "first_pass_acceptance": {name: first[name] for name in sorted(ACCEPTANCE)},
            "final_acceptance": {name: final[name] for name in sorted(ACCEPTANCE)},
            "wall_seconds": _distribution([item["wall_seconds"] for item in observed
                                             if item["wall_seconds"] is not None]),
            "human_minutes": human_effort,
            "total_human_minutes": {"distribution": _distribution(human_totals),
                                    "unknown_observations": len(observed) - len(human_totals)},
            "operator_interventions": sum(item["intervention_count"] for item in observed),
            "provider_attempts": len(attempts), "usage": usage, "costs": costs,
            "reported_setting_deviations": {
                "observations": len(deviating_observations),
                "attempts": len(deviating_attempts),
                "by_field": {name: deviation_fields[name]
                             for name in ("provider", "model", "effort")},
                "unknown_by_field": {name: unknown_fields[name]
                                     for name in ("provider", "model", "effort")},
            },
            "matching_resource_deviations": {
                "observations": len(deviating_observations | resource_deviation_observations),
                "reported_setting_observations": len(deviating_observations),
                "attempts_over_call_limit_observations": call_limit_observations,
                "known_elapsed_over_time_limit_observations": time_limit_observations,
                "unknown_elapsed_attempts": sum(
                    attempt["elapsed_seconds"] is None for attempt in attempts),
            },
            "escaped_defects": {"total_known": sum(follow_up),
                                "known_observations": len(follow_up),
                                "unknown_observations": len(observed) - len(follow_up)},
            "findings": {name: sum(item["quality"]["findings"][name] for item in observed)
                         for name in ("true_positive", "false_positive", "unresolved")},
            "unnecessary_repairs": sum(item["quality"]["unnecessary_repairs"]
                                        for item in observed),
            "repair_cycles": sum(item["quality"]["repair_cycles"] for item in observed),
        }
    feedback_counts = {
        "records": len(feedback),
        "evidence_usefulness": dict(sorted(Counter(
            item["evidence_usefulness"] for item in feedback).items())),
        "limitations_understood_true": sum(item["limitations_understood"] for item in feedback),
        "would_use_again": dict(sorted(Counter(item["would_use_again"]
                                                for item in feedback).items())),
    }
    complete_pairs = 0
    deviating_pairs = 0
    for task in protocol["tasks"]:
        pair = [item for item in assignments if item["task_id"] == task["task_id"]]
        if all(item["assignment_id"] in by_assignment for item in pair):
            complete_pairs += 1
            deviating_pairs += int(any(item["assignment_id"] in deviating_assignments
                                        for item in pair))
    return {
        "schema_version": SCHEMA_VERSION, "pilot_id": protocol["pilot_id"],
        "protocol_sha256": protocol_sha256, "exploratory": True,
        "descriptive_only": True, "significance_tested": False,
        "superiority_claim": False, "conditions": conditions,
        "matched_pairs": {"task_denominator": len(protocol["tasks"]),
                          "complete_observation_pairs": complete_pairs,
                          "eligible_pairs": complete_pairs - deviating_pairs,
                          "deviating_pairs": deviating_pairs,
                          "incomplete_pairs": len(protocol["tasks"]) - complete_pairs},
        "feedback": feedback_counts,
        "limitations": ["Missing assignments remain in every condition denominator.",
                        "This exploratory pilot does not establish statistical superiority."],
    }
