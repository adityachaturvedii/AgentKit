"""Typed, read-only failure projections from durable controller history."""

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from .redaction import redact_text


class FailureReportingError(ValueError):
    """A failure or recovery projection is malformed or unsupported."""


_RESUMABLE_AUTH_STATES = frozenset(('implementing', 'repairing', 'reviewing'))
_DISPOSITIONS = {
    'repair_allowed': 'repair_allowed',
    'repeated_failure_checkpoint': 'repeated_failure',
    'repair_exhausted': 'repair_exhausted',
}


def _text(value, name, *, limit=4096, optional=False):
    if value is None and optional:
        return
    if (not isinstance(value, str) or not value.strip() or len(value) > limit or
            re.search(r'[\x00-\x08\x0b-\x1f\x7f]', value)):
        raise FailureReportingError('invalid ' + name)


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    artifact_sha256: str

    def __post_init__(self):
        _text(self.evidence_id, 'evidence id', limit=256)
        if (not isinstance(self.artifact_sha256, str) or len(self.artifact_sha256) != 64 or
                any(character not in '0123456789abcdef' for character in self.artifact_sha256)):
            raise FailureReportingError('invalid evidence hash')


@dataclass(frozen=True)
class RecoveryAction:
    operation: str
    source_state: str
    target_state: str
    authority_prerequisite: str
    checkpoint_id: str

    def __post_init__(self):
        for value, name in ((self.operation, 'recovery operation'),
                            (self.source_state, 'recovery source state'),
                            (self.target_state, 'recovery target state'),
                            (self.authority_prerequisite, 'authority prerequisite'),
                            (self.checkpoint_id, 'recovery checkpoint id')):
            _text(value, name, limit=256)
        if (self.operation != 'resume_authentication' or
                self.source_state != 'authentication_required' or
                self.target_state not in _RESUMABLE_AUTH_STATES or
                self.authority_prerequisite != 'controller_authority'):
            raise FailureReportingError('unsupported recovery transition')


@dataclass(frozen=True)
class FailureRecord:
    task_id: str
    stage: str
    category: str
    summary: str
    retryability: str
    evidence_refs: tuple
    candidate_revision: object
    occurrence_id: str
    disposition: str
    diagnostic_tail: object = None
    recovery_action: object = None
    recovery_blocked_reason: object = None
    schema_version: int = 1

    def __post_init__(self):
        for value, name, limit in ((self.task_id, 'failure task id', 128),
                                   (self.stage, 'failure stage', 128),
                                   (self.category, 'failure category', 128),
                                   (self.summary, 'failure summary', 4096),
                                   (self.occurrence_id, 'failure occurrence id', 512),
                                   (self.disposition, 'failure disposition', 128)):
            _text(value, name, limit=limit)
        if self.retryability not in ('controller_managed', 'after_prerequisite', 'blocked'):
            raise FailureReportingError('invalid failure retryability')
        if (not isinstance(self.evidence_refs, tuple) or
                any(not isinstance(item, EvidenceReference) for item in self.evidence_refs)):
            raise FailureReportingError('invalid failure evidence references')
        if self.candidate_revision is not None:
            _text(self.candidate_revision, 'failure candidate revision', limit=512)
        if self.diagnostic_tail is not None:
            _text(self.diagnostic_tail, 'failure diagnostic tail', limit=1024)
        if self.recovery_action is not None and not isinstance(self.recovery_action, RecoveryAction):
            raise FailureReportingError('invalid recovery action')
        if self.recovery_blocked_reason is not None:
            _text(self.recovery_blocked_reason, 'recovery blocked reason', limit=1024)
        if self.recovery_action is not None and self.recovery_blocked_reason is not None:
            raise FailureReportingError('recovery cannot be both actionable and blocked')
        if self.schema_version != 1:
            raise FailureReportingError('unsupported failure schema')

    def to_dict(self):
        value = asdict(self)
        value['evidence_refs'] = list(value['evidence_refs'])
        return value


def _json(value, fallback):
    try:
        parsed = json.loads(value or '')
    except (TypeError, ValueError):
        return fallback
    return parsed


def _signature_candidates(details):
    candidates = {hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest()}
    if isinstance(details, dict):
        for key in ('findings', 'checks'):
            if isinstance(details.get(key), list):
                candidates.add(hashlib.sha256(
                    json.dumps(details[key], sort_keys=True).encode()).hexdigest())
        if isinstance(details.get('details'), dict):
            candidates.add(hashlib.sha256(
                json.dumps(details['details'], sort_keys=True).encode()).hexdigest())
    return candidates


def _category_summary(kind, status, details):
    if isinstance(details, dict):
        nested = details.get('details') if isinstance(details.get('details'), dict) else {}
        error_class = details.get('error_class') or nested.get('error_class')
        boundary_error = details.get('boundary_error') or nested.get('boundary_error')
        exit_code = details.get('exit_code')
        if (isinstance(error_class, str) and
                re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', error_class)):
            return error_class, 'The ' + kind.replace('-', ' ') + ' reported ' + error_class + '.'
        if isinstance(boundary_error, str) and boundary_error:
            cleaned = re.sub(r'[\x00-\x1f\x7f]', ' ', redact_text(boundary_error)).strip()
            return 'boundary_violation', cleaned[:1024] or 'A controller boundary check failed.'
        if kind == 'independent-review':
            findings = details.get('findings')
            count = len(findings) if isinstance(findings, list) else 0
            return 'review_finding', ('Independent review reported ' + str(count) +
                                      (' finding.' if count == 1 else ' findings.'))
        if kind == 'browser-check':
            return 'browser_acceptance_failure', 'Controller-owned browser acceptance failed.'
        if exit_code is not None:
            return 'verification_failure', 'Independent verification failed with exit code ' + str(exit_code) + '.'
    return ('environment_unavailable' if status == 'blocked' else 'quality_failure',
            kind.replace('-', ' ').capitalize() + ' did not pass.')


def _diagnostic_tail(details):
    if not isinstance(details, dict):
        return None
    nested = details.get('details') if isinstance(details.get('details'), dict) else {}
    output = details.get('output') or nested.get('output')
    if not isinstance(output, str) or not output.strip():
        return None
    cleaned = redact_text(output).replace('\x1b', '')
    cleaned = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', ' ', cleaned).strip()
    return cleaned[-1024:] or None


def _quality_failures(controller):
    task = controller['task']
    events = []
    for event in controller.get('events', ()):
        if event.get('event_type') not in _DISPOSITIONS:
            continue
        payload = _json(event.get('payload_json'), {})
        events.append((event, payload))
    records = []
    used_events = set()
    stage_by_kind = {'independent-check': 'verification', 'independent-review': 'review',
                     'browser-check': 'browser_verification'}
    for evidence in controller.get('evidence', ()):
        if evidence.get('status') not in ('failed', 'blocked'):
            continue
        details = _json(evidence.get('details_json'), {})
        signatures = _signature_candidates(details)
        matched = None
        for event, payload in events:
            if event['event_id'] in used_events or payload.get('signature') not in signatures:
                continue
            matched = (event, payload)
            used_events.add(event['event_id'])
            break
        disposition = (_DISPOSITIONS[matched[0]['event_type']] if matched else
                       ('prerequisite_missing' if evidence['status'] == 'blocked' else 'blocked'))
        category, summary = _category_summary(evidence['kind'], evidence['status'], details)
        retryability = ('controller_managed' if disposition == 'repair_allowed' else
                        'after_prerequisite' if evidence['status'] == 'blocked' else 'blocked')
        occurrence_id = (matched[0]['event_id'] if matched else
                         task['task_id'] + '-failure-' + evidence['evidence_id'])
        blocked_reason = None
        if retryability == 'after_prerequisite':
            blocked_reason = 'A validated recovery transition is unavailable until the prerequisite is restored.'
        elif retryability == 'blocked':
            blocked_reason = ('The repair budget is exhausted.' if disposition == 'repair_exhausted' else
                              'No validated recovery transition exists for this failure.')
        records.append(FailureRecord(
            task_id=task['task_id'], stage=stage_by_kind.get(evidence['kind'], evidence['kind']),
            category=category, summary=summary, retryability=retryability,
            evidence_refs=(EvidenceReference(evidence['evidence_id'], evidence['artifact_sha256']),),
            candidate_revision=evidence.get('revision') or None, occurrence_id=occurrence_id,
            disposition=disposition, diagnostic_tail=_diagnostic_tail(details),
            recovery_blocked_reason=blocked_reason))
    return records


def _authentication_failure(controller):
    task = controller['task']
    checkpoints = [item for item in controller.get('authentication_checkpoints', ())
                   if item.get('status') in ('waiting', 'ready', 'login_reconciliation_required')]
    if task.get('state') != 'authentication_required' or not checkpoints:
        return None
    checkpoint = checkpoints[-1]
    evidence_by_id = {item['evidence_id']: item for item in controller.get('evidence', ())}
    refs = []
    for evidence_id in _json(checkpoint.get('evidence_refs_json'), []):
        evidence = evidence_by_id.get(evidence_id)
        if evidence:
            refs.append(EvidenceReference(evidence_id, evidence['artifact_sha256']))
    action = None
    blocked = None
    if checkpoint['status'] == 'ready':
        action = RecoveryAction('resume_authentication', 'authentication_required',
                                checkpoint['interrupted_state'], 'controller_authority',
                                checkpoint['checkpoint_id'])
    elif checkpoint['status'] == 'login_reconciliation_required':
        blocked = 'Interactive login ownership must be reconciled before recovery.'
    else:
        blocked = 'Verified subscription login is required before recovery.'
    return FailureRecord(
        task_id=task['task_id'], stage=checkpoint['interrupted_role'], category='authentication',
        summary=checkpoint['provider'] + ' subscription authentication is required.',
        retryability='after_prerequisite', evidence_refs=tuple(refs),
        candidate_revision=checkpoint.get('candidate_revision') or None,
        occurrence_id=checkpoint['checkpoint_id'], disposition='authentication_required',
        recovery_action=action, recovery_blocked_reason=blocked)


def project_failures(controller_snapshot):
    """Return immutable typed records without mutating controller history."""
    if (not isinstance(controller_snapshot, dict) or
            not isinstance(controller_snapshot.get('task'), dict)):
        raise FailureReportingError('invalid controller snapshot')
    records = _quality_failures(controller_snapshot)
    authentication = _authentication_failure(controller_snapshot)
    if authentication is not None:
        records.append(authentication)
    return tuple(records)
