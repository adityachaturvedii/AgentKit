"""Controller-owned runtime preparation for bounded worker processes.

Runtime discovery is observational.  It never installs an executable, changes
global configuration, or grants commands beyond the selected capability
profile.  A readiness probe uses the same environment, working directory and
outer guard prefix as the provider process that will receive the runtime.
"""

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
from typing import Optional, Tuple

from .process import run_process
from .resource_policy import capability_profile


SCHEMA_VERSION = 1
STATES = ('verified', 'unavailable', 'unknown')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _bounded_text(value, name, maximum=512):
    if not isinstance(value, str) or not value or len(value.encode()) > maximum or '\0' in value:
        raise ValueError(name + ' must be a nonempty bounded string')
    return value


@dataclass(frozen=True)
class RuntimeRequirement:
    """A non-authority-bearing declaration of one worker runtime."""

    runtime_name: str
    capability_profile: str
    required_executable: str
    approved_command_prefixes: Tuple[Tuple[str, ...], ...]
    version_evidence: Optional[str] = None
    expected_executable_sha256: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('unsupported runtime-requirement schema version')
        _bounded_text(self.runtime_name, 'runtime name', 64)
        _bounded_text(self.capability_profile, 'capability profile', 128)
        profile = capability_profile(self.capability_profile, 'owned-code')
        _bounded_text(self.required_executable, 'required executable', 4096)
        if (Path(self.required_executable).name != self.runtime_name or
                (not Path(self.required_executable).is_absolute() and
                 self.required_executable != self.runtime_name)):
            raise ValueError('required executable must name the declared runtime')
        prefixes = tuple(tuple(item) for item in self.approved_command_prefixes)
        if (not prefixes or any(not prefix or any(not isinstance(part, str) or not part or
                '\0' in part for part in prefix) for prefix in prefixes)):
            raise ValueError('approved command prefixes must be nonempty argument tuples')
        if any(prefix[0] not in (self.runtime_name, 'npm') for prefix in prefixes):
            raise ValueError('command prefix is outside the declared runtime')
        expected = {
            tuple(rule.removeprefix('Bash(').removesuffix(')').removesuffix('*').rstrip().split())
            for rule in profile.bash_rules
        }
        if not set(prefixes) <= expected:
            raise ValueError('command prefix is outside the capability profile')
        if self.version_evidence is not None:
            _bounded_text(self.version_evidence, 'version evidence', 256)
        if (self.expected_executable_sha256 is not None and
                not _SHA256.fullmatch(self.expected_executable_sha256)):
            raise ValueError('expected executable hash must be lowercase SHA-256')
        object.__setattr__(self, 'approved_command_prefixes', prefixes)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError('runtime requirement must be an object')
        converted = dict(value)
        if 'approved_command_prefixes' in converted:
            converted['approved_command_prefixes'] = tuple(
                tuple(item) for item in converted['approved_command_prefixes'])
        return cls(**converted)


@dataclass(frozen=True)
class RuntimeReadiness:
    runtime_name: str
    capability_profile: str
    resolved_path: Optional[str]
    executable_sha256: Optional[str]
    version: Optional[str]
    state: str
    evidence: str
    approved_command_prefixes: Tuple[Tuple[str, ...], ...]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('unsupported runtime-readiness schema version')
        _bounded_text(self.runtime_name, 'runtime name', 64)
        _bounded_text(self.capability_profile, 'capability profile', 128)
        if self.state not in STATES:
            raise ValueError('invalid runtime-readiness state')
        _bounded_text(self.evidence, 'runtime readiness evidence', 2048)
        if self.resolved_path is not None and not Path(self.resolved_path).is_absolute():
            raise ValueError('resolved runtime path must be absolute')
        if self.executable_sha256 is not None and not _SHA256.fullmatch(self.executable_sha256):
            raise ValueError('runtime executable hash must be lowercase SHA-256')
        if self.version is not None:
            _bounded_text(self.version, 'runtime version', 256)
        object.__setattr__(self, 'approved_command_prefixes', tuple(
            tuple(item) for item in self.approved_command_prefixes))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError('runtime readiness must be an object')
        converted = dict(value)
        if 'approved_command_prefixes' in converted:
            converted['approved_command_prefixes'] = tuple(
                tuple(item) for item in converted['approved_command_prefixes'])
        return cls(**converted)


def requirement_for_profile(profile_id, *, executable=None, version_evidence=None,
                            expected_executable_sha256=None):
    """Return the single approved local runtime requirement for a worker role."""
    profile = capability_profile(profile_id, 'owned-code')
    if profile.profile_id == 'code-implementation':
        name = 'python3'
        prefixes = (('python3', '-B', '-m', 'unittest'),)
    elif profile.profile_id == 'web-product-implementation':
        name = 'node'
        prefixes = (('node', '--check'), ('npm', 'run', 'build'), ('npm', 'test'))
    else:
        raise ValueError('capability profile has no prepared worker runtime')
    selected = executable if executable is not None else (shutil.which(name) or name)
    return RuntimeRequirement(name, profile.profile_id, str(selected), prefixes,
                              version_evidence, expected_executable_sha256)


def prepared_environment(base_environment, requirement):
    """Create an allowlisted worker environment with a deterministic runtime PATH."""
    if not isinstance(requirement, RuntimeRequirement):
        raise TypeError('trusted RuntimeRequirement required')
    env = dict(base_environment)
    executable = Path(requirement.required_executable)
    directories = []
    if executable.is_absolute():
        directories.append(str(executable.parent.resolve()))
    for directory in ('/usr/bin', '/bin'):
        if directory not in directories:
            directories.append(directory)
    env['PATH'] = os.pathsep.join(directories)
    return env


def evaluate_readiness(requirement, environment, workspace, guard_prefix, *, process_runner=run_process):
    """Probe a runtime through the exact guard/environment used for dispatch."""
    if not isinstance(requirement, RuntimeRequirement):
        raise TypeError('trusted RuntimeRequirement required')
    if not isinstance(environment, dict) or not isinstance(guard_prefix, (tuple, list)):
        raise TypeError('prepared environment and explicit guard prefix required')
    workspace = Path(workspace).resolve()
    prefixes = requirement.approved_command_prefixes

    requested = Path(requirement.required_executable)
    if requested.is_absolute():
        found = str(requested.resolve()) if requested.exists() else None
    else:
        found = shutil.which(requirement.runtime_name, path=environment.get('PATH', ''))
    if not found:
        return RuntimeReadiness(
            requirement.runtime_name, requirement.capability_profile, None, None, None,
            'unavailable', 'Required executable is absent from the prepared worker PATH; no install or fallback.',
            prefixes)
    path = Path(found).resolve()
    visible = shutil.which(requirement.runtime_name, path=environment.get('PATH', ''))
    if (not path.is_file() or not os.access(path, os.X_OK) or visible is None or
            Path(visible).resolve() != path):
        return RuntimeReadiness(
            requirement.runtime_name, requirement.capability_profile, str(path), None, None,
            'unavailable', 'Required executable is not a regular executable at the prepared worker PATH resolution.',
            prefixes)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if (requirement.expected_executable_sha256 is not None and
            digest != requirement.expected_executable_sha256):
        return RuntimeReadiness(
            requirement.runtime_name, requirement.capability_profile, str(path), digest, None,
            'unavailable', 'Executable hash differs from the controller-pinned requirement; no alternate runtime used.',
            prefixes)
    outcome = process_runner(list(guard_prefix) + [str(path), '--version'], cwd=str(workspace),
                             env=environment, timeout=5, max_bytes=16384)
    if outcome.exit_code != 0 or outcome.stop_reason is not None:
        state = 'unavailable' if outcome.stop_reason == 'missing_executable' else 'unknown'
        return RuntimeReadiness(
            requirement.runtime_name, requirement.capability_profile, str(path), digest, None,
            state, 'Version probe did not complete inside the prepared worker boundary; no unrestricted retry.',
            prefixes)
    version = outcome.stdout.decode('utf-8', 'replace').strip()
    if not version or len(version.encode()) > 256:
        return RuntimeReadiness(
            requirement.runtime_name, requirement.capability_profile, str(path), digest, None,
            'unknown', 'Version probe returned no bounded version evidence.', prefixes)
    if requirement.version_evidence is not None and version != requirement.version_evidence:
        return RuntimeReadiness(
            requirement.runtime_name, requirement.capability_profile, str(path), digest, version,
            'unavailable', 'Runtime version differs from the controller-pinned evidence; no alternate runtime used.',
            prefixes)
    return RuntimeReadiness(
        requirement.runtime_name, requirement.capability_profile, str(path), digest, version,
        'verified', 'Executable path, hash and version were observed inside the prepared worker boundary.',
        prefixes)
