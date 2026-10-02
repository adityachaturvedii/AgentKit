"""Validated product-refinement records and deterministic guided intake.

These records describe intent, design, acceptance, presentation and follow-up.
They carry no execution, filesystem, budget, approval or publication authority.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from pathlib import PurePosixPath


SCHEMA_VERSION = 1
CHECK_KINDS = frozenset(('existing-repo', 'protected-independent', 'browser', 'manual'))
WORKFLOW_KINDS = frozenset(('fixture', 'repository', 'static-product'))
RECOVERABLE_STAGES = frozenset(('verification', 'browser_verification'))
ACCEPTANCE_EXECUTABLES = frozenset(('python3', 'node'))


def _text(value, name, maximum=4096, *, optional=False):
    if value is None and optional:
        return None
    if (not isinstance(value, str) or not value.strip() or
            len(value.encode('utf-8')) > maximum or '\x00' in value):
        raise ValueError(name + ' must be a nonempty bounded string')
    return value.strip()


def _strings(values, name, *, empty=False, maximum=32):
    if not isinstance(values, (list, tuple)) or (not empty and not values) or len(values) > maximum:
        raise ValueError(name + ' must be a bounded string sequence')
    result = tuple(_text(value, name, 2048) for value in values)
    if len(set(result)) != len(result):
        raise ValueError(name + ' contains duplicates')
    return result


def _safe_paths(values):
    result = []
    for value in _strings(values, 'scope path', empty=True):
        path = PurePosixPath(value)
        if (path.is_absolute() or '..' in path.parts or not path.parts or
                path.parts[0] in ('.git', 'controller')):
            raise ValueError('scope path escapes the controlled project')
        result.append(value)
    return tuple(result)


@dataclass(frozen=True)
class GuidedIntent:
    objective: str
    workflow_kind: str
    requirements: tuple
    assumptions: tuple
    allowed_paths: tuple
    acceptance: tuple
    non_goals: tuple
    material_question: object = None
    source: str = 'user-request'
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('unsupported guided-intent schema')
        object.__setattr__(self, 'objective', _text(self.objective, 'objective'))
        if self.workflow_kind not in WORKFLOW_KINDS:
            raise ValueError('unsupported workflow kind')
        for name in ('requirements', 'assumptions', 'acceptance', 'non_goals'):
            object.__setattr__(self, name, _strings(getattr(self, name), name,
                                                   empty=name in ('assumptions', 'non_goals')))
        object.__setattr__(self, 'allowed_paths', _safe_paths(self.allowed_paths))
        if self.material_question is not None:
            object.__setattr__(self, 'material_question',
                               _text(self.material_question, 'material question', 1024))
        object.__setattr__(self, 'source', _text(self.source, 'intent source', 128))

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DesignBrief:
    audience_job: str
    critical_flows: tuple
    direction: str
    rationale: str
    tokens: tuple
    components: tuple
    responsive_criteria: tuple
    accessibility_criteria: tuple
    assets: tuple
    assumptions: tuple
    non_goals: tuple
    acceptance_ids: tuple
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('unsupported design-brief schema')
        for name in ('audience_job', 'direction', 'rationale'):
            object.__setattr__(self, name, _text(getattr(self, name), name, 2048))
        for name in ('critical_flows', 'tokens', 'components', 'responsive_criteria',
                     'accessibility_criteria', 'assets', 'assumptions', 'non_goals',
                     'acceptance_ids'):
            object.__setattr__(self, name, _strings(
                getattr(self, name), name, empty=name in ('assets', 'assumptions', 'non_goals')))

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class AcceptanceCheck:
    check_id: str
    requirement_id: str
    kind: str
    expected: str
    expected_source: str
    argv: tuple = ()

    def __post_init__(self):
        for name in ('check_id', 'requirement_id', 'expected', 'expected_source'):
            object.__setattr__(self, name, _text(getattr(self, name), name, 1024))
        if self.kind not in CHECK_KINDS:
            raise ValueError('unsupported acceptance check kind')
        if not isinstance(self.argv, (tuple, list)) or len(self.argv) > 16 or any(
                not isinstance(item, str) or not item or '\x00' in item for item in self.argv):
            raise ValueError('invalid acceptance argv')
        object.__setattr__(self, 'argv', tuple(self.argv))
        if self.kind in ('browser', 'manual') and self.argv:
            raise ValueError('browser/manual checks cannot embed commands')
        if self.argv and self.argv[0] not in ACCEPTANCE_EXECUTABLES:
            raise ValueError('acceptance command is outside the controlled executable allowlist')


@dataclass(frozen=True)
class AcceptanceSpec:
    checks: tuple
    runtime_profile: str
    oracle_version: int
    oracle_sha256: str
    positive_controls: tuple
    negative_controls: tuple
    coverage_gaps: tuple
    frozen: bool = True
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION or self.frozen is not True:
            raise ValueError('acceptance spec must be a frozen supported schema')
        if (not isinstance(self.checks, tuple) or not self.checks or
                any(not isinstance(item, AcceptanceCheck) for item in self.checks)):
            raise ValueError('acceptance requires validated checks')
        ids = [item.check_id for item in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate acceptance check')
        object.__setattr__(self, 'runtime_profile',
                           _text(self.runtime_profile, 'acceptance runtime', 128))
        if type(self.oracle_version) is not int or self.oracle_version < 1:
            raise ValueError('invalid oracle version')
        if not re.fullmatch(r'[0-9a-f]{64}', self.oracle_sha256 or ''):
            raise ValueError('invalid oracle hash')
        for name in ('positive_controls', 'negative_controls', 'coverage_gaps'):
            object.__setattr__(self, name, _strings(
                getattr(self, name), name, empty=name == 'coverage_gaps'))

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class RunView:
    task_id: str
    objective: str
    workflow_kind: str
    stage: str
    active_assignments: tuple
    last_activity: object
    candidate_revision: object
    failure: object
    acceptance_coverage: dict
    usage: dict
    next_actions: tuple
    needs_attention: bool
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('unsupported run-view schema')
        for value, name in ((self.task_id, 'task id'), (self.objective, 'objective'),
                            (self.stage, 'stage')):
            _text(value, name, 4096)
        if self.workflow_kind not in WORKFLOW_KINDS:
            raise ValueError('unsupported workflow kind')
        if type(self.needs_attention) is not bool:
            raise ValueError('needs_attention must be boolean')
        object.__setattr__(self, 'active_assignments', _strings(
            self.active_assignments, 'active assignments', empty=True))
        object.__setattr__(self, 'next_actions', _strings(
            self.next_actions, 'next actions', empty=True))
        if not isinstance(self.acceptance_coverage, dict) or set(self.acceptance_coverage) != {
                'passed', 'failed', 'unknown'} or any(
                    type(value) is not int or value < 0
                    for value in self.acceptance_coverage.values()):
            raise ValueError('invalid acceptance coverage')
        if not isinstance(self.usage, dict):
            raise ValueError('invalid usage summary')

    def to_dict(self):
        return asdict(self)


def guided_intake(request, inventory, *, workflow_kind):
    """Produce a conservative draft from a request and controller inventory."""
    request = _text(request, 'request', 32768)
    if not isinstance(inventory, dict) or not isinstance(inventory.get('paths'), list):
        raise ValueError('bounded inventory with paths is required')
    paths = _safe_paths(inventory['paths'])
    lowered = request.lower()
    conflict = (('without tests' in lowered or 'do not test' in lowered) and
                ('test' in lowered or 'acceptance' in lowered))
    ambiguous = conflict or any(term in lowered for term in
                                ('whatever you think', 'either ', 'or maybe', 'not sure'))
    question = ('Which conflicting requirement should control acceptance?' if conflict else
                'Which of the materially different outcomes should be the primary user journey?'
                if ambiguous else None)
    sentences = tuple(item.strip() for item in re.split(r'[\n.!?]+', request) if item.strip())
    requirements = sentences[:16] or (request,)
    acceptance = tuple('Observe: ' + item for item in requirements[:8])
    assumptions = () if ambiguous else ('Use existing project conventions where the request is silent.',)
    return GuidedIntent(
        request, workflow_kind, requirements, assumptions, paths, acceptance,
        ('No publication, deployment, paid fallback, or authority expansion.',), question)


def run_view(status, task, *, workflow_kind, last_activity=None):
    if not isinstance(status, dict) or not isinstance(task, dict):
        raise ValueError('authoritative task and status are required')
    if status.get('task_id') != task.get('task_id'):
        raise ValueError('run view task identity mismatch')
    groups = status.get('assignments') or {}
    active = tuple(item.get('node_id') for item in groups.get('active', ())
                   if isinstance(item, dict) and isinstance(item.get('node_id'), str))
    verification = status.get('verification') or ()
    coverage = {
        'passed': sum(item.get('status') == 'passed' and not item.get('stale')
                      for item in verification if isinstance(item, dict)),
        'failed': sum(item.get('status') == 'failed' and not item.get('stale')
                      for item in verification if isinstance(item, dict)),
        'unknown': sum(item.get('status') not in ('passed', 'failed') or item.get('stale')
                       for item in verification if isinstance(item, dict)),
    }
    next_actions = tuple(item for item in (status.get('attention'), status.get('next_action'))
                         if isinstance(item, str) and item.strip())
    return RunView(
        task['task_id'], task['objective'], workflow_kind, status['state'], active,
        last_activity, task.get('head_revision'), status.get('current_failure'), coverage,
        status.get('budget', {}).get('usage_reporting') or {}, next_actions,
        bool(status.get('attention') or status.get('blocker')))


def refinement_decision(*, prior_revision, current_revision, requested_paths, allowed_paths,
                        remaining_repairs, active_execution=False):
    for value, name in ((prior_revision, 'prior revision'),
                        (current_revision, 'current revision')):
        _text(value, name, 128)
    if active_execution:
        raise ValueError('active execution must be reconciled before refinement')
    if type(remaining_repairs) is not int or remaining_repairs <= 0:
        raise ValueError('no bounded repair allocation remains')
    requested = set(_safe_paths(requested_paths))
    allowed = set(_safe_paths(allowed_paths))
    if not requested or not requested <= allowed:
        raise ValueError('refinement expands path authority')
    return {
        'schema_version': 1,
        'prior_revision': prior_revision,
        'current_revision': current_revision,
        'requested_paths': sorted(requested),
        'remaining_repairs': remaining_repairs,
        'invalidates': ['verification', 'browser_verification', 'review', 'approval_package'],
        'approval_recorded': False,
    }


@dataclass(frozen=True)
class RecoveryDecision:
    """Authority-free proof required for one narrow quality-stage retry."""

    task_id: str
    failure_event_id: str
    failed_stage: str
    source_state: str
    candidate_revision: str
    repository_manifest_sha256: str
    prior_execution_termination: str
    correction_kind: str
    corrected_identity_sha256: str
    remaining_calls: int
    remaining_seconds: float
    invalidated_evidence: tuple
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('unsupported recovery decision schema')
        for name in ('task_id', 'failure_event_id', 'source_state', 'candidate_revision'):
            object.__setattr__(self, name, _text(getattr(self, name), name, 256))
        if self.failed_stage not in RECOVERABLE_STAGES:
            raise ValueError('failure stage has no supported recovery transition')
        if self.correction_kind not in ('environment', 'oracle'):
            raise ValueError('unsupported recovery correction')
        if self.prior_execution_termination != 'confirmed_ended':
            raise ValueError('prior execution must be confirmed ended')
        for name in ('repository_manifest_sha256', 'corrected_identity_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', getattr(self, name) or ''):
                raise ValueError(name + ' is invalid')
        if type(self.remaining_calls) is not int or self.remaining_calls < 1:
            raise ValueError('recovery requires a remaining call')
        if (type(self.remaining_seconds) not in (int, float) or
                not 0 < self.remaining_seconds < float('inf')):
            raise ValueError('recovery requires finite remaining time')
        object.__setattr__(self, 'invalidated_evidence', _strings(
            self.invalidated_evidence, 'invalidated evidence', empty=True))

    def authorize(self, *, actual_revision, actual_manifest_sha256, current_state,
                  competing_claim=False):
        if competing_claim:
            raise ValueError('recovery already has an active claimant')
        if current_state != self.source_state:
            raise ValueError('recovery source state changed')
        if actual_revision != self.candidate_revision:
            raise ValueError('candidate revision changed before recovery')
        if actual_manifest_sha256 != self.repository_manifest_sha256:
            raise ValueError('candidate manifest changed before recovery')
        return {
            'schema_version': self.schema_version,
            'task_id': self.task_id,
            'failed_stage': self.failed_stage,
            'resume_stage': self.failed_stage,
            'correction_kind': self.correction_kind,
            'corrected_identity_sha256': self.corrected_identity_sha256,
            'remaining_calls': self.remaining_calls,
            'remaining_seconds': self.remaining_seconds,
            'invalidated_evidence': list(self.invalidated_evidence),
            'implementation_reexecution': False,
            'approval_recorded': False,
        }
