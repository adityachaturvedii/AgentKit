"""Offline integrity helpers for static-web preview and browser evidence.

This module prepares plain-file preview snapshots and validates evidence produced
by a separately controlled browser operator or driver.  It does not launch or
control a browser and does not treat a report as proof of browser isolation.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import tempfile


MAX_FILES = 128
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
MAX_REPORT_BYTES = 256 * 1024
MAX_ACCEPTANCE_CHECKS = 32
MAX_SCREENSHOTS = 16
MAX_SCREENSHOT_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 8192
MAX_PATH_BYTES = 512

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SESSION = re.compile(r"^[0-9a-f]{32}$")
_VIEWPORT = re.compile(r"^([1-9][0-9]{1,4})x([1-9][0-9]{1,4})$")


class WebAcceptanceError(ValueError):
    """A preview snapshot or browser report crossed its bounded contract."""


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _bounded_text(value, name, maximum=MAX_TEXT_BYTES):
    if (not isinstance(value, str) or not value.strip() or
            len(value.encode("utf-8")) > maximum):
        raise WebAcceptanceError(name + " must be a nonempty bounded string")
    return value.strip()


def _hex(value, pattern, name):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise WebAcceptanceError(name + " is invalid")
    return value


def _relative(value, name):
    value = _bounded_text(value, name, MAX_PATH_BYTES)
    if "\\" in value:
        raise WebAcceptanceError(name + " must use portable forward slashes")
    path = PurePosixPath(value)
    if (path.is_absolute() or value != path.as_posix() or
            any(part in ("", ".", "..") for part in path.parts) or
            any(part.lower() == ".git" for part in path.parts)):
        raise WebAcceptanceError(name + " is unsafe")
    return path


def _regular_bytes(root, relative, *, maximum, name):
    """Read one bounded regular file while rejecting symlinks in its path."""
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise WebAcceptanceError(name + " is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise WebAcceptanceError(name + " traverses a symlink or non-directory")
    target = root.joinpath(*relative.parts)
    try:
        metadata = target.lstat()
    except OSError as exc:
        raise WebAcceptanceError(name + " is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise WebAcceptanceError(name + " must be a regular non-symlink file")
    if metadata.st_size > maximum:
        raise WebAcceptanceError(name + " exceeds its byte bound")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(target), flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise WebAcceptanceError(name + " changed type while being read")
            data = stream.read(maximum + 1)
    except OSError as exc:
        raise WebAcceptanceError(name + " could not be read safely") from exc
    if len(data) > maximum:
        raise WebAcceptanceError(name + " exceeds its byte bound")
    return data, "100755" if opened.st_mode & 0o111 else "100644"


def create_preview_snapshot(source, destination, tracked_manifest, candidate_revision):
    """Copy an explicit tracked manifest into a fresh private plain-file tree.

    ``tracked_manifest`` is a mapping of portable relative paths to expected
    SHA-256 values. Extra source files are ignored. The returned session ID is
    random; both digests are deterministic for the same revision and content.
    """
    candidate_revision = _hex(candidate_revision, _REVISION, "candidate revision")
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or not source.is_dir():
        raise WebAcceptanceError("preview source must be a regular directory")
    source = source.resolve()
    if (not isinstance(tracked_manifest, dict) or not tracked_manifest or
            len(tracked_manifest) > MAX_FILES):
        raise WebAcceptanceError("tracked manifest must be a bounded nonempty object")
    if destination.exists() or destination.is_symlink():
        raise WebAcceptanceError("preview destination must be fresh")
    parent = destination.parent.resolve()
    if not parent.is_dir() or parent.is_symlink():
        raise WebAcceptanceError("preview destination parent is unavailable")

    entries = []
    total = 0
    seen = set()
    prepared = []
    for raw_path, expected in tracked_manifest.items():
        relative = _relative(raw_path, "tracked path")
        canonical = relative.as_posix()
        if canonical in seen:
            raise WebAcceptanceError("tracked manifest contains duplicate paths")
        seen.add(canonical)
        expected = _hex(expected, _SHA256, "tracked file sha256")
        data, mode = _regular_bytes(source, relative, maximum=MAX_FILE_BYTES,
                                    name="tracked file")
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise WebAcceptanceError("tracked file does not match its manifest")
        total += len(data)
        if total > MAX_SNAPSHOT_BYTES:
            raise WebAcceptanceError("preview snapshot exceeds its byte bound")
        entry = {"path": canonical, "sha256": actual, "bytes": len(data), "mode": mode}
        entries.append(entry)
        prepared.append((relative, data, mode))
    entries.sort(key=lambda item: item["path"])
    prepared.sort(key=lambda item: item[0].as_posix())
    manifest_sha256 = _digest(entries)
    snapshot_sha256 = _digest({"candidate_revision": candidate_revision,
                               "manifest_sha256": manifest_sha256})

    temporary = Path(tempfile.mkdtemp(prefix=".agentkit-preview-", dir=str(parent)))
    temporary.chmod(0o700)
    try:
        for relative, data, mode in prepared:
            target = temporary.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(data)
            target.chmod(0o700 if mode == "100755" else 0o600)
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "schema_version": 1,
        "candidate_revision": candidate_revision,
        "session_id": secrets.token_hex(16),
        "snapshot_root": str(destination.resolve()),
        "manifest": entries,
        "manifest_sha256": manifest_sha256,
        "snapshot_sha256": snapshot_sha256,
    }


def _strict_object(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WebAcceptanceError(name + " has an unsupported shape")
    return value


def _bounded_unique_strings(values, name, maximum):
    if not isinstance(values, list) or not values or len(values) > maximum:
        raise WebAcceptanceError(name + " must be a bounded nonempty list")
    normalized = [_bounded_text(value, name + " entry", 256) for value in values]
    if len(set(normalized)) != len(normalized):
        raise WebAcceptanceError(name + " contains duplicates")
    return normalized


def validate_browser_report(report, *, acceptance, candidate_revision, preview_receipt,
                            evidence_root, implementation_authors):
    """Validate and normalize an externally produced browser observation report.

    Passing validation establishes internal consistency and file integrity only.
    It does not establish that a browser ran or that its process, credentials, or
    network were isolated.
    """
    candidate_revision = _hex(candidate_revision, _REVISION, "candidate revision")
    try:
        encoded = _json_bytes(report)
    except (TypeError, ValueError) as exc:
        raise WebAcceptanceError("browser report must be finite JSON data") from exc
    if len(encoded) > MAX_REPORT_BYTES:
        raise WebAcceptanceError("browser report exceeds its byte bound")
    _strict_object(report, (
        "schema_version", "candidate_revision", "session_id", "snapshot_sha256",
        "browser", "verifier", "implementation_authors", "checks", "screenshots",
        "visual_judgment"), "browser report")
    if type(report["schema_version"]) is not int or report["schema_version"] != 1:
        raise WebAcceptanceError("unsupported browser report schema")

    _strict_object(preview_receipt, (
        "schema_version", "candidate_revision", "session_id", "snapshot_sha256",
        "status", "cleanup_confirmed"), "preview receipt")
    if (type(preview_receipt["schema_version"]) is not int or
            preview_receipt["schema_version"] != 1 or
            preview_receipt["status"] != "stopped" or
            preview_receipt["cleanup_confirmed"] is not True):
        raise WebAcceptanceError("preview receipt does not confirm cleanup")
    receipt_revision = _hex(preview_receipt["candidate_revision"], _REVISION,
                            "preview candidate revision")
    receipt_session = _hex(preview_receipt["session_id"], _SESSION, "preview session ID")
    receipt_snapshot = _hex(preview_receipt["snapshot_sha256"], _SHA256,
                            "preview snapshot sha256")
    report_revision = _hex(report["candidate_revision"], _REVISION,
                           "report candidate revision")
    report_session = _hex(report["session_id"], _SESSION, "report session ID")
    report_snapshot = _hex(report["snapshot_sha256"], _SHA256,
                            "report snapshot sha256")
    if (receipt_revision != candidate_revision or report_revision != candidate_revision or
            report_session != receipt_session or report_snapshot != receipt_snapshot):
        raise WebAcceptanceError("browser report is bound to another preview or candidate")

    browser = _strict_object(report["browser"], ("name", "version"), "browser identity")
    normalized_browser = {
        "name": _bounded_text(browser["name"], "browser name", 256),
        "version": _bounded_text(browser["version"], "browser version", 256),
    }
    verifier = _strict_object(report["verifier"], ("id", "type"), "verifier identity")
    verifier_id = _bounded_text(verifier["id"], "verifier ID", 256)
    if verifier["type"] not in ("human", "external-driver"):
        raise WebAcceptanceError("verifier type is unsupported")

    expected_authors = _bounded_unique_strings(
        list(implementation_authors) if isinstance(implementation_authors, (list, tuple)) else None,
        "implementation authors", 32)
    reported_authors = _bounded_unique_strings(report["implementation_authors"],
                                                "implementation authors", 32)
    if reported_authors != expected_authors:
        raise WebAcceptanceError("implementation author metadata changed")
    if verifier_id in expected_authors:
        raise WebAcceptanceError("browser verifier is not independent")

    if (not isinstance(acceptance, list) or not acceptance or
            len(acceptance) > MAX_ACCEPTANCE_CHECKS):
        raise WebAcceptanceError("acceptance must be a bounded nonempty list")
    expected = {}
    for item in acceptance:
        _strict_object(item, ("id", "expected"), "acceptance record")
        identity = _bounded_text(item["id"], "acceptance ID", 256)
        expectation = _bounded_text(item["expected"], "acceptance expectation")
        if identity in expected:
            raise WebAcceptanceError("acceptance IDs must be unique")
        expected[identity] = expectation

    checks = report["checks"]
    if (not isinstance(checks, list) or len(checks) != len(expected) or
            len(checks) > MAX_ACCEPTANCE_CHECKS):
        raise WebAcceptanceError("browser checks do not cover bounded acceptance")
    normalized_checks = []
    seen = set()
    for item in checks:
        _strict_object(item, ("id", "status", "action", "assertion", "observation"),
                       "browser check")
        identity = _bounded_text(item["id"], "browser check ID", 256)
        if identity not in expected or identity in seen:
            raise WebAcceptanceError("browser checks contain unknown or duplicate IDs")
        seen.add(identity)
        if item["status"] not in ("passed", "failed"):
            raise WebAcceptanceError("browser check status is unsupported")
        normalized_checks.append({
            "id": identity,
            "expected": expected[identity],
            "status": item["status"],
            "action": _bounded_text(item["action"], "browser action"),
            "assertion": _bounded_text(item["assertion"], "browser assertion"),
            "observation": _bounded_text(item["observation"], "browser observation"),
        })
    if seen != set(expected):
        raise WebAcceptanceError("browser checks omit acceptance IDs")

    evidence_root = Path(evidence_root)
    if evidence_root.is_symlink() or not evidence_root.is_dir():
        raise WebAcceptanceError("evidence root must be a regular directory")
    evidence_root = evidence_root.resolve()
    screenshots = report["screenshots"]
    if not isinstance(screenshots, list) or len(screenshots) > MAX_SCREENSHOTS:
        raise WebAcceptanceError("browser screenshots exceed their count bound")
    normalized_screenshots = []
    screenshot_paths = set()
    for item in screenshots:
        _strict_object(item, ("path", "sha256", "viewport"), "browser screenshot")
        relative = _relative(item["path"], "screenshot path")
        canonical = relative.as_posix()
        if canonical in screenshot_paths:
            raise WebAcceptanceError("browser screenshots contain duplicate paths")
        screenshot_paths.add(canonical)
        expected_hash = _hex(item["sha256"], _SHA256, "screenshot sha256")
        viewport = _bounded_text(item["viewport"], "screenshot viewport", 32)
        match = _VIEWPORT.fullmatch(viewport)
        if not match or int(match.group(1)) > 16384 or int(match.group(2)) > 16384:
            raise WebAcceptanceError("screenshot viewport is invalid")
        data, _ = _regular_bytes(evidence_root, relative, maximum=MAX_SCREENSHOT_BYTES,
                                 name="browser screenshot")
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise WebAcceptanceError("browser screenshot changed")
        normalized_screenshots.append({"path": canonical, "sha256": expected_hash,
                                       "viewport": viewport})

    judgment = _strict_object(report["visual_judgment"], ("status", "observation"),
                              "visual judgment")
    if judgment["status"] not in ("passed", "failed"):
        raise WebAcceptanceError("visual judgment status is unsupported")
    normalized_judgment = {
        "status": judgment["status"],
        "observation": _bounded_text(judgment["observation"], "visual observation"),
    }
    passed = (all(item["status"] == "passed" for item in normalized_checks) and
              normalized_judgment["status"] == "passed")
    return {
        "schema_version": 1,
        "candidate_revision": candidate_revision,
        "session_id": receipt_session,
        "snapshot_sha256": receipt_snapshot,
        "browser": normalized_browser,
        "verifier": {"id": verifier_id, "type": verifier["type"]},
        "implementation_authors": expected_authors,
        "checks": normalized_checks,
        "screenshots": normalized_screenshots,
        "visual_judgment": normalized_judgment,
        "status": "passed" if passed else "failed",
        "limitations": [
            "The report is externally supplied evidence; this validator does not run a browser.",
            "Browser credentials, egress, process containment, and visual accuracy are not established.",
        ],
    }
