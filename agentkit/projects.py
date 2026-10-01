"""Read-only, bounded repository intake for explicitly selected local projects.

R1 inspects and enrolls metadata only. It never runs project code, hooks,
filters, dependency installers, provider CLIs, or repository-supplied commands.
"""

from dataclasses import dataclass
import fnmatch
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .integrations.openharness.fs import atomic_private_write
from .validation import read_json


SCHEMA_VERSION = 1
OID = re.compile(r"^[0-9a-f]{40}$")
PROFILE_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SECRET_NAMES = re.compile(
    r"(^|/)(\.env($|\.)|id_(rsa|dsa|ecdsa|ed25519)$|[^/]*\.(pem|p12|pfx|key)$|"
    r"credentials?([^/]*)$|secrets?([^/]*)$)", re.IGNORECASE)
FILTER_CONFIG = re.compile(r"(?im)^\s*\[\s*filter\s+\"")
INCLUDE_CONFIG = re.compile(r"(?im)^\s*\[\s*include(?:if)?\b")
UNSAFE_CONFIG = re.compile(
    r"(?im)^\s*(hooksPath|worktree|fsmonitor|sshCommand)\s*=|"
    r"^\s*\[\s*(submodule|url)\b")


class ProjectIntakeError(ValueError):
    pass


@dataclass(frozen=True)
class InspectionLimits:
    max_tracked_files: int = 2000
    max_tracked_bytes: int = 16 * 1024 * 1024
    max_file_bytes: int = 2 * 1024 * 1024
    max_untracked_files: int = 1000
    max_git_output_bytes: int = 4 * 1024 * 1024

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if type(value) is not int or value <= 0:
                raise ProjectIntakeError(name + " must be a positive integer")
        if self.max_file_bytes > self.max_tracked_bytes:
            raise ProjectIntakeError("per-file bound cannot exceed total tracked-byte bound")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha256(value: Any) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _relative(value: str, *, allow_dot: bool = True) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ProjectIntakeError("project paths must be nonempty portable relative paths")
    if any(ord(character) < 32 for character in value):
        raise ProjectIntakeError("project paths cannot contain control characters")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ProjectIntakeError("project path escapes the enrolled root")
    normalized = str(path)
    if normalized == "." and allow_dot:
        return normalized
    if normalized in ("", "."):
        raise ProjectIntakeError("project path must name a file or directory")
    return normalized


def _path_is_within(relative: str, prefixes: Iterable[str]) -> bool:
    path = PurePosixPath(relative)
    return any(prefix == "." or path == PurePosixPath(prefix) or
               PurePosixPath(prefix) in path.parents for prefix in prefixes)


def _profile_path_list(value: Any, name: str, *, allow_empty: bool = False) -> List[str]:
    if not isinstance(value, list) or (not value and not allow_empty) or len(value) > 64:
        raise ProjectIntakeError(name + " must be a bounded path list")
    result = [_relative(item) for item in value]
    if len(set(result)) != len(result):
        raise ProjectIntakeError(name + " contains duplicate paths")
    return result


def validate_project_profile(value: Any) -> Dict[str, Any]:
    """Validate a proposed profile without granting execution authority."""
    required = {
        "schema_version", "profile_id", "stack", "read_paths", "context_paths",
        "write_paths", "excludes", "checks", "environment", "network",
        "data_disclosure", "execution_profile", "required_review", "execution_enabled",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ProjectIntakeError("project profile fields do not match schema version 1")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ProjectIntakeError("unsupported project profile schema version")
    if not isinstance(value["profile_id"], str) or not PROFILE_ID.fullmatch(value["profile_id"]):
        raise ProjectIntakeError("invalid project profile identifier")
    if value["stack"] != "python-library":
        raise ProjectIntakeError("R1 supports only the proposed python-library stack")
    read_paths = _profile_path_list(value["read_paths"], "read_paths")
    context_paths = _profile_path_list(value["context_paths"], "context_paths",
                                       allow_empty=True)
    write_paths = _profile_path_list(value["write_paths"], "write_paths")
    excludes = _profile_path_list(value["excludes"], "excludes", allow_empty=True)
    if any(not _path_is_within(path, read_paths) for path in context_paths + write_paths):
        raise ProjectIntakeError("context and write paths must be within read_paths")
    if any(_path_is_within(path, excludes) for path in context_paths + write_paths):
        raise ProjectIntakeError("context or write path is excluded")

    checks = value["checks"]
    if not isinstance(checks, list) or not checks or len(checks) > 16:
        raise ProjectIntakeError("checks must contain 1..16 proposed recipes")
    check_ids = set()
    normalized_checks = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != {
                "id", "argv", "cwd", "timeout_seconds", "result"}:
            raise ProjectIntakeError("check recipe fields do not match schema")
        check_id = check["id"]
        if (not isinstance(check_id, str) or not PROFILE_ID.fullmatch(check_id) or
                check_id in check_ids):
            raise ProjectIntakeError("invalid or duplicate check identifier")
        argv = check["argv"]
        if (not isinstance(argv, list) or not 2 <= len(argv) <= 32 or
                any(not isinstance(item, str) or not item or len(item) > 256 or "\x00" in item
                    for item in argv)):
            raise ProjectIntakeError("check argv must be a bounded string vector")
        if argv[0] != "python3" or argv[1:3] not in (["-m", "unittest"], ["-m", "pytest"]):
            raise ProjectIntakeError("R1 check recipes support python3 unittest or pytest only")
        cwd = _relative(check["cwd"])
        if not _path_is_within(cwd, read_paths):
            raise ProjectIntakeError("check cwd must be within read_paths")
        timeout = check["timeout_seconds"]
        if (type(timeout) not in (int, float) or not math.isfinite(timeout) or
                timeout <= 0 or timeout > 3600):
            raise ProjectIntakeError("check timeout must be finite and within 1..3600 seconds")
        if check["result"] not in ("exit-zero", "unittest", "pytest"):
            raise ProjectIntakeError("unsupported check result interpretation")
        normalized_checks.append({**check, "cwd": cwd, "timeout_seconds": float(timeout)})
        check_ids.add(check_id)

    environment = value["environment"]
    if (not isinstance(environment, dict) or set(environment) != {
            "kind", "install_during_run"} or environment["kind"] != "prepared" or
            environment["install_during_run"] is not False):
        raise ProjectIntakeError("R1 requires a prepared environment with installation disabled")
    if value["network"] != "none":
        raise ProjectIntakeError("R1 project profiles cannot authorize network access")
    if value["data_disclosure"] != "selected-source-to-configured-provider":
        raise ProjectIntakeError("unsupported data-disclosure policy")
    if value["execution_profile"] != "trusted-disposable-macos-owned-code":
        raise ProjectIntakeError("unsupported execution profile")
    if value["required_review"] not in ("independent", "cross-provider"):
        raise ProjectIntakeError("unsupported review requirement")
    if value["execution_enabled"] is not False:
        raise ProjectIntakeError("R1 enrollment cannot enable repository execution")
    return {
        **value,
        "read_paths": read_paths,
        "context_paths": context_paths,
        "write_paths": write_paths,
        "excludes": excludes,
        "checks": normalized_checks,
        "environment": dict(environment),
    }


class RepositoryInspector:
    def __init__(self, limits: Optional[InspectionLimits] = None):
        self.limits = limits or InspectionLimits()
        self.commands: List[List[str]] = []

    def _git(self, root: Path, *arguments: str, allowed=(0,)) -> Tuple[int, bytes, bytes]:
        argv = [
            "git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
            "-c", "core.attributesFile=/dev/null", "-c", "core.excludesFile=/dev/null",
            "-C", str(root), *arguments,
        ]
        self.commands.append(argv[1:])
        env = {key: value for key, value in os.environ.items()
               if key in ("PATH", "LANG", "LC_ALL")}
        env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
                   GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", PAGER="cat")
        run = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=10, check=False)
        if len(run.stdout) > self.limits.max_git_output_bytes:
            raise ProjectIntakeError("Git metadata output exceeds inspection bound")
        if run.returncode not in allowed:
            message = run.stderr.decode("utf-8", "replace").strip()
            raise ProjectIntakeError("bounded Git metadata query failed: " + message[:500])
        return run.returncode, run.stdout, run.stderr

    def _preflight(self, requested: Path) -> Tuple[Path, Path, List[str], List[str], str]:
        if requested.is_symlink():
            raise ProjectIntakeError("project root cannot be a symlink")
        root = requested.resolve(strict=True)
        if not root.is_dir():
            raise ProjectIntakeError("project root must be a directory")
        git_dir = root / ".git"
        if git_dir.is_symlink() or not git_dir.is_dir():
            raise ProjectIntakeError("R1 supports only a standalone repository with a .git directory")
        blockers = []
        warnings = []
        config = git_dir / "config"
        if config.is_symlink() or not config.is_file():
            raise ProjectIntakeError("repository config must be a regular local file")
        raw_config = config.read_bytes()
        if len(raw_config) > 256 * 1024:
            raise ProjectIntakeError("repository config exceeds inspection bound")
        try:
            config_text = raw_config.decode("utf-8")
        except UnicodeDecodeError:
            blockers.append("non_utf8_git_configuration")
            config_text = ""
        if INCLUDE_CONFIG.search(config_text):
            blockers.append("git_config_include")
        if FILTER_CONFIG.search(config_text):
            blockers.append("git_filter_configuration")
        if UNSAFE_CONFIG.search(config_text):
            blockers.append("unsupported_git_configuration")
        for relative, reason in (
                ("commondir", "shared_git_metadata"),
                ("objects/info/alternates", "alternate_object_store"),
                ("shallow", "shallow_repository")):
            path = git_dir / relative
            if path.exists() or path.is_symlink():
                blockers.append(reason)
        metadata_entries = 0
        for directory, names, files in os.walk(git_dir, followlinks=False):
            for name in names + files:
                metadata_entries += 1
                if metadata_entries > 100000:
                    blockers.append("git_metadata_entry_limit")
                    break
                if (Path(directory) / name).is_symlink():
                    blockers.append("symlinked_git_metadata")
            if "git_metadata_entry_limit" in blockers:
                break
        exclude = git_dir / "info" / "exclude"
        if exclude.is_symlink():
            blockers.append("symlinked_git_exclude")
        return root, git_dir, sorted(set(blockers)), warnings, hashlib.sha256(raw_config).hexdigest()

    @staticmethod
    def _parse_index(payload: bytes) -> Dict[str, Dict[str, Any]]:
        result = {}
        for raw in payload.split(b"\0"):
            if not raw:
                continue
            try:
                metadata, name = raw.split(b"\t", 1)
                mode, oid, stage = metadata.decode("ascii").split()
                relative = name.decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ProjectIntakeError("unsupported Git index record") from exc
            relative = _relative(relative, allow_dot=False)
            if stage != "0" or relative in result or not OID.fullmatch(oid):
                raise ProjectIntakeError("conflicted, duplicate, or invalid Git index entry")
            result[relative] = {"mode": mode, "oid": oid}
        return result

    @staticmethod
    def _parse_tree(payload: bytes) -> Dict[str, Dict[str, Any]]:
        result = {}
        for raw in payload.split(b"\0"):
            if not raw:
                continue
            try:
                metadata, name = raw.split(b"\t", 1)
                mode, kind, oid = metadata.decode("ascii").split()
                relative = _relative(name.decode("utf-8"), allow_dot=False)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ProjectIntakeError("unsupported Git tree record") from exc
            if relative in result or not OID.fullmatch(oid):
                raise ProjectIntakeError("duplicate or invalid Git tree entry")
            result[relative] = {"mode": mode, "oid": oid, "kind": kind}
        return result

    @staticmethod
    def _blob_oid(payload: bytes) -> str:
        header = ("blob " + str(len(payload)) + "\0").encode("ascii")
        return hashlib.sha1(header + payload).hexdigest()

    @staticmethod
    def _read_tracked(root: Path, relative: str, maximum: int) -> Tuple[bytes, os.stat_result]:
        cursor = root
        for part in PurePosixPath(relative).parts[:-1]:
            cursor = cursor / part
            if cursor.is_symlink() or not cursor.is_dir():
                raise ProjectIntakeError("tracked path has a non-directory or symlink parent")
        target = root / relative
        before = target.lstat()
        if stat.S_ISLNK(before.st_mode):
            payload = os.readlink(target).encode("utf-8")
        elif stat.S_ISREG(before.st_mode):
            if before.st_size > maximum:
                raise ProjectIntakeError("tracked file exceeds per-file inspection bound: " + relative)
            payload = target.read_bytes()
        else:
            raise ProjectIntakeError("tracked path is not a regular file: " + relative)
        after = target.lstat()
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns,
                                 stat.S_IFMT(item.st_mode))
        if identity(before) != identity(after):
            raise ProjectIntakeError("tracked file changed during inspection: " + relative)
        return payload, after

    def inspect(self, project_root: os.PathLike) -> Dict[str, Any]:
        self.commands = []
        requested = Path(project_root).expanduser()
        root, git_dir, blockers, warnings, config_sha256 = self._preflight(requested)
        preflight_blockers = list(blockers)
        if blockers and any(item in blockers for item in (
                "git_config_include", "shared_git_metadata", "alternate_object_store",
                "symlinked_git_metadata", "git_metadata_entry_limit",
                "non_utf8_git_configuration")):
            return self._partial(root, blockers, warnings)

        _, format_raw, _ = self._git(root, "rev-parse", "--show-object-format")
        object_format = format_raw.decode("ascii", "strict").strip()
        if object_format != "sha1":
            blockers.append("unsupported_object_format")
        _, head_raw, _ = self._git(root, "rev-parse", "--verify", "HEAD^{commit}")
        head = head_raw.decode("ascii", "strict").strip()
        if not OID.fullmatch(head):
            raise ProjectIntakeError("invalid repository HEAD")
        branch_code, branch_raw, _ = self._git(
            root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1))
        branch = branch_raw.decode("utf-8", "strict").strip() if branch_code == 0 else None
        if branch is None:
            blockers.append("detached_head")

        _, index_raw, _ = self._git(root, "ls-files", "--stage", "-z")
        _, tree_raw, _ = self._git(root, "ls-tree", "-r", "-z", "HEAD")
        index = self._parse_index(index_raw)
        tree = self._parse_tree(tree_raw)
        if len(index) > self.limits.max_tracked_files:
            raise ProjectIntakeError("tracked file count exceeds inspection bound")
        staged = sorted(path for path in set(index) | set(tree)
                        if index.get(path) != {key: value for key, value in tree.get(path, {}).items()
                                               if key in ("mode", "oid")})
        modified, deleted, entries = [], [], []
        worktree_fingerprints = {}
        gitignore_sources = []
        total_bytes = 0
        for relative, item in sorted(index.items()):
            mode = item["mode"]
            if mode == "160000":
                blockers.append("git_submodule")
                entries.append({"path": relative, "mode": mode, "oid": item["oid"],
                                "size": None, "binary": None, "secret_like_path": False})
                continue
            if mode == "120000":
                blockers.append("tracked_symlink")
            elif mode not in ("100644", "100755"):
                blockers.append("unsupported_file_mode")
            try:
                payload, file_stat = self._read_tracked(
                    root, relative, self.limits.max_file_bytes)
            except FileNotFoundError:
                deleted.append(relative)
                entries.append({"path": relative, "mode": mode, "oid": item["oid"],
                                "size": None, "binary": None,
                                "secret_like_path": bool(SECRET_NAMES.search(relative))})
                continue
            total_bytes += len(payload)
            worktree_fingerprints[relative] = (
                file_stat.st_dev, file_stat.st_ino, file_stat.st_size,
                file_stat.st_mtime_ns, stat.S_IFMT(file_stat.st_mode))
            if total_bytes > self.limits.max_tracked_bytes:
                raise ProjectIntakeError("tracked content exceeds total inspection bound")
            raw_oid = self._blob_oid(payload)
            executable = bool(file_stat.st_mode & stat.S_IXUSR)
            if file_stat.st_nlink > 1:
                blockers.append("multiply_linked_tracked_file")
            mode_changed = mode in ("100644", "100755") and executable != (mode == "100755")
            if raw_oid != item["oid"] or mode_changed:
                modified.append(relative)
            secret_like = bool(SECRET_NAMES.search(relative))
            if secret_like:
                warnings.append("secret_like_path:" + relative)
            binary = b"\0" in payload[:8192]
            if binary:
                warnings.append("binary_tracked_path:" + relative)
            if payload.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                blockers.append("git_lfs_pointer")
            if relative == ".gitignore" or relative.endswith("/.gitignore"):
                try:
                    gitignore_sources.append((str(PurePosixPath(relative).parent),
                                              payload.decode("utf-8")))
                except UnicodeDecodeError:
                    warnings.append("non_utf8_gitignore:" + relative)
            entries.append({
                "path": relative, "mode": mode, "oid": item["oid"],
                "size": len(payload), "binary": binary,
                "secret_like_path": secret_like,
            })

        _, untracked_raw, _ = self._git(root, "ls-files", "--others", "-z")
        try:
            all_untracked = sorted(_relative(item.decode("utf-8"), allow_dot=False)
                                   for item in untracked_raw.split(b"\0") if item)
        except UnicodeDecodeError as exc:
            raise ProjectIntakeError("untracked path is not UTF-8") from exc
        if len(all_untracked) > self.limits.max_untracked_files * 10:
            raise ProjectIntakeError("untracked scan exceeds inspection bound")
        ignored, untracked = self._apply_tracked_gitignores(all_untracked, gitignore_sources,
                                                            warnings)
        if len(untracked) > self.limits.max_untracked_files:
            raise ProjectIntakeError("untracked file count exceeds inspection bound")
        if (root / ".gitmodules").exists() or ".gitmodules" in index:
            blockers.append("git_submodule_configuration")
        attributes = root / ".gitattributes"
        if attributes.is_file() and not attributes.is_symlink():
            text = attributes.read_bytes()[:256 * 1024].decode("utf-8", "replace")
            if re.search(r"(?m)(^|\s)(filter|working-tree-encoding|smudge|clean)=", text):
                blockers.append("git_attribute_transform")
        clean = not (staged or modified or deleted or untracked)
        if not clean:
            blockers.append("dirty_worktree")
        _, final_head_raw, _ = self._git(root, "rev-parse", "--verify", "HEAD^{commit}")
        _, final_index_raw, _ = self._git(root, "ls-files", "--stage", "-z")
        _, final_untracked_raw, _ = self._git(root, "ls-files", "--others", "-z")
        _, _, final_blockers, _, final_config_sha256 = self._preflight(root)
        if (final_head_raw != head_raw or final_index_raw != index_raw or
                final_untracked_raw != untracked_raw or
                final_config_sha256 != config_sha256 or final_blockers != preflight_blockers):
            raise ProjectIntakeError("repository metadata changed during inspection")
        for relative, expected in worktree_fingerprints.items():
            try:
                observed_stat = (root / relative).lstat()
            except FileNotFoundError as exc:
                raise ProjectIntakeError("repository content changed during inspection") from exc
            observed = (observed_stat.st_dev, observed_stat.st_ino, observed_stat.st_size,
                        observed_stat.st_mtime_ns, stat.S_IFMT(observed_stat.st_mode))
            if observed != expected:
                raise ProjectIntakeError("repository content changed during inspection")
        inventory = {
            "tracked_count": len(entries), "tracked_bytes": total_bytes,
            "manifest_sha256": _sha256(entries), "entries": entries,
        }
        report = {
            "schema_version": SCHEMA_VERSION,
            "project": {
                "root": str(root), "root_identity_sha256": _sha256(str(root).encode()),
                "device": root.stat().st_dev, "inode": root.stat().st_ino,
                "base_revision": head, "branch": branch, "object_format": object_format,
            },
            "inventory": inventory,
            "working_tree": {
                "clean": clean, "staged": staged, "modified": modified,
                "deleted": deleted, "untracked": untracked, "ignored_untracked": ignored,
            },
            "readiness": {
                "status": "ready" if not blockers else "blocked",
                "blockers": sorted(set(blockers)), "warnings": sorted(set(warnings)),
                "execution_supported": False,
                "next_action": ("enroll a validated read-only profile" if not blockers else
                                "resolve blockers without changing them through AgentKit"),
            },
            "inspection": {
                "mode": "read-only-metadata-and-raw-tracked-content",
                "commands": self.commands,
                "hooks_executed": False, "filters_executed": False,
                "project_commands_executed": False, "network_used": False,
                "limits": dict(self.limits.__dict__),
            },
        }
        report["report_sha256"] = _sha256(report)
        return report

    @staticmethod
    def _apply_tracked_gitignores(paths: List[str], sources: List[Tuple[str, str]],
                                  warnings: List[str]) -> Tuple[List[str], List[str]]:
        rules = []
        for base, content in sources:
            for raw in content.splitlines():
                pattern = raw.strip()
                if not pattern or pattern.startswith("#"):
                    continue
                if pattern.startswith("!") or "**" in pattern or "[" in pattern:
                    warnings.append("complex_gitignore_rule:" + pattern[:80])
                    continue
                directory = pattern.endswith("/")
                pattern = pattern.lstrip("/").rstrip("/")
                if pattern:
                    rules.append((base, pattern, directory))

        def ignored(path):
            candidate = PurePosixPath(path)
            for base, pattern, directory in rules:
                base_path = PurePosixPath(base)
                try:
                    local = candidate.relative_to(base_path) if base != "." else candidate
                except ValueError:
                    continue
                local_text = str(local)
                if directory and (local_text == pattern or local_text.startswith(pattern + "/")):
                    return True
                if "/" in pattern and fnmatch.fnmatchcase(local_text, pattern):
                    return True
                if "/" not in pattern and any(fnmatch.fnmatchcase(part, pattern)
                                                for part in local.parts):
                    return True
            return False

        ignored_paths = [path for path in paths if ignored(path)]
        visible_paths = [path for path in paths if not ignored(path)]
        return ignored_paths, visible_paths

    def _partial(self, root: Path, blockers: List[str], warnings: List[str]) -> Dict[str, Any]:
        report = {
            "schema_version": SCHEMA_VERSION,
            "project": {
                "root": str(root), "root_identity_sha256": _sha256(str(root).encode()),
                "device": root.stat().st_dev, "inode": root.stat().st_ino,
                "base_revision": None, "branch": None, "object_format": None,
            },
            "inventory": None,
            "working_tree": None,
            "readiness": {
                "status": "blocked", "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)), "execution_supported": False,
                "next_action": "resolve blockers without changing them through AgentKit",
            },
            "inspection": {
                "mode": "preflight-only", "commands": [], "hooks_executed": False,
                "filters_executed": False, "project_commands_executed": False,
                "network_used": False, "limits": dict(self.limits.__dict__),
            },
        }
        report["report_sha256"] = _sha256(report)
        return report


def inspect_project(project_root: os.PathLike, *, limits: Optional[InspectionLimits] = None):
    return RepositoryInspector(limits).inspect(project_root)


class ProjectRegistry:
    def __init__(self, state_root: os.PathLike):
        requested = Path(state_root).expanduser()
        if requested.exists() and requested.is_symlink():
            raise ProjectIntakeError("project registry root cannot be a symlink")
        self.root = requested.resolve()
        self.projects = self.root / "projects"
        self.projects.mkdir(parents=True, exist_ok=True, mode=0o700)

    def enroll(self, project_root: os.PathLike, profile_document: Any) -> Dict[str, Any]:
        profile = validate_project_profile(profile_document)
        report = inspect_project(project_root)
        project = Path(report["project"]["root"])
        if self.root == project or project in self.root.parents or self.root in project.parents:
            raise ProjectIntakeError("project registry must be outside the enrolled repository")
        if report["readiness"]["status"] != "ready":
            raise ProjectIntakeError(
                "repository is not ready: " + ", ".join(report["readiness"]["blockers"]))
        tracked_paths = [item["path"] for item in report["inventory"]["entries"]]
        for name in ("read_paths", "context_paths", "write_paths"):
            for prefix in profile[name]:
                if prefix != "." and not any(_path_is_within(path, [prefix])
                                              for path in tracked_paths):
                    raise ProjectIntakeError(name + " references no tracked content: " + prefix)
        for item in report["inventory"]["entries"]:
            if ((item["binary"] or item["secret_like_path"]) and
                    not _path_is_within(item["path"], profile["excludes"])):
                raise ProjectIntakeError(
                    "profile must explicitly exclude binary or secret-like tracked path: " +
                    item["path"])
        profile_hash = _sha256(profile)
        project_id = "project-" + _sha256({
            "root": report["project"]["root_identity_sha256"],
            "base": report["project"]["base_revision"], "profile": profile_hash,
        })[:16]
        record = {
            "schema_version": SCHEMA_VERSION, "project_id": project_id,
            "project": report["project"], "inventory": report["inventory"],
            "inspection_sha256": report["report_sha256"],
            "profile": profile, "profile_sha256": profile_hash,
            "execution_authorized": False,
            "capabilities": {
                "read_only_intake": "verified", "planning": "verified",
                "repository_execution": "unsupported_until_R2",
            },
        }
        record["record_sha256"] = _sha256(record)
        target = self.projects / (project_id + ".json")
        if target.exists():
            existing = self.load(project_id)
            if existing != record:
                raise ProjectIntakeError("project identifier collision or changed enrollment")
            return existing
        atomic_private_write(target, json.dumps(record, indent=2, sort_keys=True) + "\n")
        return record

    def load(self, project_id: str) -> Dict[str, Any]:
        if not isinstance(project_id, str) or not re.fullmatch(r"project-[0-9a-f]{16}", project_id):
            raise ProjectIntakeError("invalid project identifier")
        target = self.projects / (project_id + ".json")
        if target.is_symlink() or not target.is_file():
            raise ProjectIntakeError("enrolled project does not exist")
        value = read_json(target)
        expected_fields = {
            "schema_version", "project_id", "project", "inventory", "inspection_sha256",
            "profile", "profile_sha256", "execution_authorized", "capabilities",
            "record_sha256",
        }
        if not isinstance(value, dict) or set(value) != expected_fields:
            raise ProjectIntakeError("enrollment record fields do not match schema")
        recorded_hash = value.pop("record_sha256", None)
        if recorded_hash != _sha256(value):
            raise ProjectIntakeError("enrollment record integrity check failed")
        if (type(value["schema_version"]) is not int or
                value["schema_version"] != SCHEMA_VERSION or
                value["project_id"] != project_id or value["execution_authorized"] is not False):
            raise ProjectIntakeError("enrollment record authority or identity is invalid")
        if value["capabilities"] != {
                "read_only_intake": "verified", "planning": "verified",
                "repository_execution": "unsupported_until_R2"}:
            raise ProjectIntakeError("enrollment capability record is invalid")
        project = value["project"]
        if (not isinstance(project, dict) or set(project) != {
                "root", "root_identity_sha256", "device", "inode", "base_revision",
                "branch", "object_format"} or
                not isinstance(project["root"], str) or not Path(project["root"]).is_absolute() or
                not isinstance(project["branch"], str) or not project["branch"] or
                project["object_format"] != "sha1" or
                not OID.fullmatch(project["base_revision"]) or
                type(project["device"]) is not int or type(project["inode"]) is not int or
                not re.fullmatch(r"[0-9a-f]{64}", project["root_identity_sha256"])):
            raise ProjectIntakeError("enrollment project identity is invalid")
        inventory = value["inventory"]
        if (not isinstance(inventory, dict) or set(inventory) != {
                "tracked_count", "tracked_bytes", "manifest_sha256", "entries"} or
                type(inventory["tracked_count"]) is not int or inventory["tracked_count"] < 0 or
                type(inventory["tracked_bytes"]) is not int or inventory["tracked_bytes"] < 0 or
                not isinstance(inventory["entries"], list) or
                inventory["tracked_count"] != len(inventory["entries"]) or
                inventory["manifest_sha256"] != _sha256(inventory["entries"])):
            raise ProjectIntakeError("enrollment inventory is invalid")
        for item in inventory["entries"]:
            if (not isinstance(item, dict) or set(item) != {
                    "path", "mode", "oid", "size", "binary", "secret_like_path"} or
                    _relative(item["path"], allow_dot=False) != item["path"] or
                    item["mode"] not in ("100644", "100755") or
                    not OID.fullmatch(item["oid"]) or type(item["size"]) is not int or
                    item["size"] < 0 or type(item["binary"]) is not bool or
                    type(item["secret_like_path"]) is not bool):
                raise ProjectIntakeError("enrollment inventory entry is invalid")
        if (not isinstance(value["inspection_sha256"], str) or
                not re.fullmatch(r"[0-9a-f]{64}", value["inspection_sha256"])):
            raise ProjectIntakeError("enrollment inspection hash is invalid")
        value["record_sha256"] = recorded_hash
        profile = validate_project_profile(value.get("profile"))
        if value.get("profile_sha256") != _sha256(profile):
            raise ProjectIntakeError("enrolled profile hash changed")
        return value

    def plan(self, project_id: str, request: str) -> Dict[str, Any]:
        if not isinstance(request, str) or not request.strip() or len(request.encode()) > 8192:
            raise ProjectIntakeError("request must contain 1..8192 UTF-8 bytes")
        record = self.load(project_id)
        current = inspect_project(record["project"]["root"])
        identity_fields = ("root_identity_sha256", "device", "inode", "base_revision", "branch")
        stale = any(current["project"].get(field) != record["project"].get(field)
                    for field in identity_fields)
        current_inventory = current.get("inventory") or {}
        stale = stale or current_inventory.get("manifest_sha256") != record[
            "inventory"]["manifest_sha256"]
        blockers = list(current["readiness"]["blockers"])
        if stale:
            blockers.append("enrollment_stale")
        tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", request)
                  if len(token) >= 3}
        candidates = [entry["path"] for entry in record["inventory"]["entries"]
                      if not entry["binary"] and not entry["secret_like_path"] and
                      not _path_is_within(entry["path"], record["profile"]["excludes"])]
        scored = []
        for path in candidates:
            path_tokens = set(re.findall(r"[a-z0-9_]+", path.lower()))
            score = len(tokens & path_tokens)
            if score:
                scored.append((-score, path))
        relevant = [path for _, path in sorted(scored)[:20]]
        if not relevant:
            relevant = [path for path in candidates
                        if path.lower().endswith(("readme.md", "pyproject.toml", "setup.cfg"))][:20]
        checks = [{"id": item["id"], "argv": item["argv"], "status": "proposed_only"}
                  for item in record["profile"]["checks"]]
        plan = {
            "schema_version": SCHEMA_VERSION, "project_id": project_id,
            "objective": request.strip(),
            "requirements": [{"source": "user", "text": request.strip()}],
            "assumptions": [
                "The enrolled committed baseline remains authoritative.",
                "R1 proposes scope and checks but cannot execute repository work.",
            ],
            "relevant_inventory": relevant,
            "proposed_scope": {
                "read_paths": record["profile"]["read_paths"],
                "write_paths": record["profile"]["write_paths"],
                "excluded_paths": record["profile"]["excludes"],
            },
            "acceptance": [
                {"id": "requested-behavior", "expected": request.strip()},
                {"id": "declared-checks", "expected": "All enrolled check recipes pass."},
                {"id": "scope", "expected": "Only enrolled write paths change."},
            ],
            "checks": checks,
            "stages": ["independent-import", "implementation", "verification",
                       "independent-review", "local-package"],
            "status": "blocked" if blockers else "planned_read_only",
            "blockers": sorted(set(blockers + ["repository_execution_requires_R2"])),
            "model_calls": 0, "execution_authorized": False,
            "base_revision": record["project"]["base_revision"],
            "profile_sha256": record["profile_sha256"],
            "inventory_sha256": record["inventory"]["manifest_sha256"],
            "next_action": "implement and validate the R2 independent importer",
        }
        plan["plan_sha256"] = _sha256(plan)
        return plan


def example_python_profile() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "profile_id": "python-library-readonly",
        "stack": "python-library",
        "read_paths": ["."],
        "context_paths": ["README.md", "src", "tests"],
        "write_paths": ["src", "tests"],
        "excludes": [".venv", "build", "dist"],
        "checks": [{
            "id": "unit-tests", "argv": ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            "cwd": ".", "timeout_seconds": 120, "result": "unittest",
        }],
        "environment": {"kind": "prepared", "install_during_run": False},
        "network": "none",
        "data_disclosure": "selected-source-to-configured-provider",
        "execution_profile": "trusted-disposable-macos-owned-code",
        "required_review": "independent",
        "execution_enabled": False,
    }
