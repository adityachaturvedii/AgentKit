"""Portable, non-executing review-package export and verification."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import uuid

from .controller import ControllerStore
from .redaction import redact, redact_text


class PortablePackageError(ValueError):
    pass


OID = re.compile(r'^[0-9a-f]{40,64}$')
EVIDENCE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
MAX_FILES = 100
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _private_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.tmp-' + str(uuid.uuid4()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')


def _read_json(path, description):
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise PortablePackageError(description + ' is missing or invalid')
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, PortablePackageError):
            raise
        raise PortablePackageError(description + ' is malformed') from exc
    if not isinstance(value, dict):
        raise PortablePackageError(description + ' must be a JSON object')
    return value


def _safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise PortablePackageError('package path is invalid')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or any(not part for part in path.parts):
        raise PortablePackageError('package path escapes its root')
    return path


def _sanitized(value, workflow_root):
    """Remove local authority paths while keeping bounded review evidence."""
    blocked_keys = {'artifacts', 'raw_events', 'environment', 'managed_repository'}
    if isinstance(value, dict):
        return {key: _sanitized(item, workflow_root) for key, item in value.items()
                if key not in blocked_keys}
    if isinstance(value, list):
        return [_sanitized(item, workflow_root) for item in value]
    if isinstance(value, str):
        return value.replace(str(workflow_root), '<workflow>').replace(
            str(Path.home().resolve()), '<home>')
    return value


def export_package(workflow_root, task_id, output):
    workflow_root = Path(workflow_root).resolve()
    output = Path(output).resolve()
    if output.exists() or output.is_symlink():
        raise PortablePackageError('package output must be fresh')
    approval_path = workflow_root / 'approval' / 'approval-package.json'
    if approval_path.is_symlink() or not approval_path.is_file():
        raise PortablePackageError('workflow has no local approval package')
    approval = _read_json(approval_path, 'approval package')
    store = ControllerStore(workflow_root / 'controller')
    snapshot = store.snapshot(task_id)
    task = snapshot['task']
    if (task['state'] != 'awaiting_pr_approval' or approval.get('task_id') != task_id or
            approval.get('head_revision') != task['head_revision'] or
            approval.get('approval', {}).get('recorded') is not False):
        raise PortablePackageError('workflow is not an unapproved exact-revision candidate')
    verification_refs = approval.get('verification_evidence')
    review_ref = approval.get('review_evidence')
    if not isinstance(verification_refs, list) or not verification_refs:
        raise PortablePackageError('approval package has no required verification evidence')
    required = list(verification_refs)
    required.append(review_ref)
    required.append('approval-package')
    if (len(set(required)) != len(required) or
            any(not isinstance(item, str) or not EVIDENCE_ID.fullmatch(item)
                for item in required)):
        raise PortablePackageError('approval package has invalid evidence references')
    evidence = {item['evidence_id']: item for item in snapshot['evidence']}
    if len(evidence) != len(snapshot['evidence']):
        raise PortablePackageError('controller contains duplicate evidence identifiers')
    prepared_evidence = []
    for evidence_id in required:
        record = evidence.get(evidence_id)
        if (not record or record['revision'] != task['head_revision'] or record['stale'] or
                record['status'] != 'passed' or
                not store.artifact_intact(record['artifact_sha256'])):
            raise PortablePackageError('required evidence is absent, stale or not passed')
        expected_kind = ('independent-check' if evidence_id in approval['verification_evidence'] else
                         'independent-review' if evidence_id == approval['review_evidence'] else
                         'approval-package')
        if record['kind'] != expected_kind:
            raise PortablePackageError('required evidence has the wrong kind')
        try:
            details = json.loads(record['details_json'])
        except (TypeError, ValueError) as exc:
            raise PortablePackageError('required evidence details are malformed') from exc
        prepared_evidence.append((evidence_id, record, details))

    original_artifact = approval.get('artifact_sha256')
    original_approval = dict(approval)
    original_approval.pop('artifact_sha256', None)
    if (not store.artifact_intact(original_artifact) or
            _hash(json.dumps(original_approval, sort_keys=True).encode('utf-8')) != original_artifact):
        raise PortablePackageError('local approval artifact is absent or inconsistent')
    approval_record = next(record for evidence_id, record, _ in prepared_evidence
                           if evidence_id == 'approval-package')
    if approval_record['artifact_sha256'] != original_artifact:
        raise PortablePackageError('approval evidence does not identify the local approval artifact')
    if redact_text(str(approval.get('diff', ''))) != approval.get('diff', ''):
        raise PortablePackageError('candidate diff contains a potential secret and cannot be exported')

    requirement_matrix = []
    for requirement in approval.get('requirements', []):
        if (not isinstance(requirement, dict) or not isinstance(requirement.get('id'), str) or
                not requirement['id'] or not isinstance(requirement.get('expected'), str) or
                not requirement['expected']):
            raise PortablePackageError('approval package has an invalid requirement')
        requirement_matrix.append({
            'requirement_id': requirement['id'], 'expected': redact_text(requirement['expected']),
            'evidence': list(required), 'status': 'passed',
        })
    if not requirement_matrix:
        raise PortablePackageError('approval package has no requirements')

    output.mkdir(mode=0o700)
    files = {}
    exported_bytes = 0

    def write(relative, value):
        nonlocal exported_bytes
        relative = str(_safe_relative(relative))
        payload = value if isinstance(value, bytes) else _json_bytes(value)
        exported_bytes += len(payload)
        if (len(payload) > MAX_FILE_BYTES or len(files) >= MAX_FILES or
                exported_bytes > MAX_TOTAL_BYTES):
            raise PortablePackageError('package export exceeds its size or file-count limit')
        _private_write(output / relative, payload)
        files[relative] = {'sha256': _hash(payload), 'bytes': len(payload)}

    portable_approval = redact(_sanitized(approval, workflow_root))
    portable_approval['portable_provenance'] = {
        'source_inventory_sha256': approval.get('import', {}).get('source_inventory_sha256'),
        'profile_sha256': approval.get('import', {}).get('profile_sha256'),
        'policy_hashes': 'unknown', 'skill_hashes': 'unknown',
        'controller_database_included': False,
    }
    write('approval-package.json', portable_approval)
    for evidence_id, record, details in prepared_evidence:
        write('evidence/' + evidence_id + '.json', {
            'evidence_id': evidence_id, 'revision': record['revision'],
            'kind': record['kind'], 'status': record['status'],
            'source_artifact_sha256': record['artifact_sha256'],
            'details': redact(_sanitized(details, workflow_root)),
        })
    write('requirement-matrix.json', {'requirements': requirement_matrix})
    write('review-guide.json', {
        'schema_version': 1,
        'purpose': 'Offline inspection only; verification does not execute candidate code.',
        'steps': ['Read approval-package.json.', 'Inspect the complete candidate.diff.',
                  'Inspect every required evidence record and its limitations.',
                  'Re-run project checks only in a separately authorized environment.'],
        'limitations': ['Integrity proves package bytes and internal consistency only.',
                        'It does not authenticate the author or prove commands were run.',
                        'No approval, publication or execution authority is included.'],
    })
    write('candidate.diff', approval.get('diff', '').encode('utf-8'))
    manifest = {'schema_version': 1, 'task_id': task_id,
                'base_revision': approval.get('managed_base_revision'),
                'head_revision': task['head_revision'], 'files': files,
                'execution_on_import': False}
    _private_write(output / 'manifest.json', _json_bytes(manifest))
    return verify_package(output)


def verify_package(root):
    supplied_root = Path(root)
    if supplied_root.is_symlink():
        raise PortablePackageError('package root must be a real directory')
    root = supplied_root.resolve()
    if not root.is_dir():
        raise PortablePackageError('package root must be a real directory')
    manifest_path = root / 'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PortablePackageError('package manifest is missing')
    manifest = _read_json(manifest_path, 'package manifest')
    if (manifest.get('schema_version') != 1 or manifest.get('execution_on_import') is not False or
            not OID.fullmatch(str(manifest.get('base_revision', ''))) or
            not OID.fullmatch(str(manifest.get('head_revision', '')))):
        raise PortablePackageError('package manifest contract is invalid')
    declared = manifest.get('files')
    if not isinstance(declared, dict) or not 1 <= len(declared) <= MAX_FILES:
        raise PortablePackageError('package file inventory is invalid')
    fixed = {'approval-package.json', 'candidate.diff', 'requirement-matrix.json',
             'review-guide.json'}
    if not fixed.issubset(declared):
        raise PortablePackageError('package is missing a required content file')
    observed = []
    total = 0
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise PortablePackageError('package contains a symlink')
        if path.is_file():
            relative = str(path.relative_to(root))
            if relative != 'manifest.json':
                observed.append(relative)
                if len(observed) > MAX_FILES:
                    raise PortablePackageError('package contains too many files')
    if observed != sorted(declared):
        raise PortablePackageError('package contains missing or undeclared files')
    for relative, expected in declared.items():
        safe = _safe_relative(relative)
        path = root.joinpath(*safe.parts)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise PortablePackageError('package file cannot be read') from exc
        total += len(payload)
        if (len(payload) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or
                expected != {'sha256': _hash(payload), 'bytes': len(payload)}):
            raise PortablePackageError('package file integrity check failed')
    approval = _read_json(root / 'approval-package.json', 'portable approval package')
    head = manifest['head_revision']
    if (approval.get('task_id') != manifest.get('task_id') or
            approval.get('managed_base_revision') != manifest['base_revision'] or
            approval.get('head_revision') != head or
            approval.get('status') != 'awaiting_pr_approval' or
            approval.get('approval', {}).get('recorded') is not False):
        raise PortablePackageError('approval package is inconsistent with the manifest')
    verification_refs = approval.get('verification_evidence')
    if not isinstance(verification_refs, list) or not verification_refs:
        raise PortablePackageError('portable approval has no verification evidence')
    required = list(verification_refs)
    required.append(approval.get('review_evidence'))
    required.append('approval-package')
    if (len(set(required)) != len(required) or
            any(not isinstance(item, str) or not EVIDENCE_ID.fullmatch(item)
                for item in required)):
        raise PortablePackageError('portable approval has invalid evidence references')
    for evidence_id in required:
        path = root / 'evidence' / (str(evidence_id) + '.json')
        record = _read_json(path, 'required evidence file')
        expected_kind = ('independent-check' if evidence_id in approval['verification_evidence'] else
                         'independent-review' if evidence_id == approval['review_evidence'] else
                         'approval-package')
        if (record.get('evidence_id') != evidence_id or record.get('revision') != head or
                record.get('kind') != expected_kind or record.get('status') != 'passed'):
            raise PortablePackageError('required evidence is incomplete or inconsistent')
    matrix = _read_json(root / 'requirement-matrix.json', 'requirement matrix')
    rows = matrix.get('requirements')
    if not isinstance(rows, list) or not rows:
        raise PortablePackageError('requirement matrix is empty')
    expected_requirements = approval.get('requirements')
    if not isinstance(expected_requirements, list) or len(rows) != len(expected_requirements):
        raise PortablePackageError('requirement matrix does not match approval requirements')
    for row, requirement in zip(rows, expected_requirements):
        if (not isinstance(row, dict) or not isinstance(requirement, dict) or
                row.get('requirement_id') != requirement.get('id') or
                row.get('expected') != requirement.get('expected') or
                row.get('status') != 'passed' or row.get('evidence') != required):
            raise PortablePackageError('requirement matrix is inconsistent')
    try:
        diff = (root / 'candidate.diff').read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise PortablePackageError('candidate diff is unreadable') from exc
    if diff != approval.get('diff'):
        raise PortablePackageError('candidate diff is inconsistent with the approval package')
    return {'valid': True, 'schema_version': 1, 'task_id': manifest['task_id'],
            'base_revision': manifest['base_revision'], 'head_revision': head,
            'files': len(declared), 'bytes': total, 'execution_performed': False,
            'authority': 'none'}
