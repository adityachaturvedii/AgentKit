"""Controller-owned execution resource and capability policy.

Provider defaults are represented by ``None``.  A missing provider control is
never described as unlimited: it means the installed CLI owns that setting and
the controller cannot enforce or reliably observe it.
"""

from dataclasses import asdict, dataclass
import math


CONTROL_SOURCES = ('task-override', 'role-policy', 'provider-default')
CONTROL_CLASSES = ('enforced', 'best-effort', 'observable-only', 'unsupported')


@dataclass(frozen=True)
class CapabilityProfile:
    profile_id: str
    mode: str
    tools: tuple
    bash_rules: tuple
    purpose: str


CAPABILITY_PROFILES = {
    'structured-planning': CapabilityProfile(
        'structured-planning', 'model-only', (), (),
        'Return a controller-validated structured proposal without tools.'),
    'code-implementation': CapabilityProfile(
        'code-implementation', 'owned-code', ('Read', 'Edit', 'Write', 'Bash'),
        ('Bash(python3 -B -m unittest*)',),
        'Edit controller-owned source and run the approved Python test command.'),
    'independent-review': CapabilityProfile(
        'independent-review', 'model-only', (), (),
        'Review an immutable candidate supplied in the prompt without tools.'),
    'web-product-implementation': CapabilityProfile(
        'web-product-implementation', 'owned-code', ('Read', 'Edit', 'Write', 'Bash'),
        ('Bash(node --check *)', 'Bash(npm run build*)', 'Bash(npm test*)'),
        'Edit the bounded static-web files and run approved local build or test commands.'),
    'smoke-model-only': CapabilityProfile(
        'smoke-model-only', 'model-only', (), (),
        'Tiny synthetic diagnostic with fixture-scoped restrictive settings.'),
}


ROLE_POLICY = {
    'planning': {'timeout_seconds': 180.0, 'max_capture_bytes': 1048576},
    'implementation': {'timeout_seconds': 60.0, 'max_capture_bytes': 1048576},
    'web-implementation': {'timeout_seconds': 180.0, 'max_capture_bytes': 1048576},
    'review': {'timeout_seconds': 60.0, 'max_capture_bytes': 1048576},
    'verification': {'timeout_seconds': 10.0, 'max_capture_bytes': 1048576},
    'smoke': {'timeout_seconds': 45.0, 'max_capture_bytes': 1048576},
}

PRODUCT_TASK_POLICY = {
    'max_calls': 8,
    'max_provider_calls': 8,
    'max_concurrency': 2,
    'max_repairs': 2,
    'max_retries': 1,
    'max_escalations': 2,
    'max_elapsed_seconds': 1200.0,
}


PROVIDER_CONTROLS = {
    'codex': {
        'model': ('best-effort', '--model is present in codex exec 0.154.0 help.'),
        'effort': ('unsupported', 'Installed codex exec help exposes no --effort flag; this harness does not infer model-specific config support.'),
        'generated_output_tokens': ('unsupported', 'No generated-output limit is exposed by installed codex exec help.'),
        'turn_limit': ('unsupported', 'No turn-limit control is exposed by installed codex exec help.'),
        'retry_limit': ('unsupported', 'No retry-limit control is exposed for the built-in subscription provider.'),
        'tool_permissions': ('best-effort', 'CLI sandbox flags are layered under the external Seatbelt boundary.'),
    },
    'claude': {
        'model': ('best-effort', '--model is present in Claude Code 2.1.220 help.'),
        'effort': ('best-effort', '--effort is present in Claude Code 2.1.220 help.'),
        'generated_output_tokens': ('observable-only', 'CLAUDE_CODE_MAX_OUTPUT_TOKENS affected an archived run but is absent from installed help and official CLI reference.'),
        'turn_limit': ('unsupported', 'Installed Claude Code 2.1.220 help exposes no max-turns flag.'),
        'retry_limit': ('observable-only', 'CLAUDE_CODE_MAX_RETRIES is absent from installed help and official CLI reference.'),
        'tool_permissions': ('best-effort', '--tools, --settings and permission rules are CLI controls; Seatbelt enforces the filesystem boundary.'),
    },
}


def capability_profile(profile_id, mode):
    if profile_id is None:
        # Compatibility for provider-neutral callers. Productive role adapters
        # always name a profile explicitly.
        profile_id = 'structured-planning' if mode == 'model-only' else 'code-implementation'
    try:
        profile = CAPABILITY_PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError('unsupported capability profile') from exc
    if profile.mode != mode:
        raise ValueError('capability profile is incompatible with execution mode')
    return profile


def provider_control_support(engine, name):
    try:
        classification, evidence = PROVIDER_CONTROLS[engine][name]
    except KeyError as exc:
        raise ValueError('unknown provider control') from exc
    return {'classification': classification, 'evidence': evidence}


def _positive_number(value, name):
    if (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
        raise ValueError(name + ' must be a finite positive number')
    return value


def _capture_bytes(value):
    if type(value) is not int or not 1024 <= value <= 4194304:
        raise ValueError('capture allocation must be 1 KiB..4 MiB')
    return value


def resolve_role_resources(role, *, task_timeout_seconds=None, task_capture_bytes=None,
                           provider_output_tokens=None):
    """Resolve controller allocations and provider controls with explicit provenance."""
    if role not in ROLE_POLICY:
        raise ValueError('unknown role resource policy')
    configured = ROLE_POLICY[role]
    timeout = (task_timeout_seconds if task_timeout_seconds is not None
               else configured.get('timeout_seconds'))
    capture = (task_capture_bytes if task_capture_bytes is not None
               else configured.get('max_capture_bytes'))
    if timeout is None:
        raise ValueError('controller timeout requires an explicit or role-policy allocation')
    if capture is None:
        raise ValueError('capture bytes require an explicit or role-policy allocation')
    _positive_number(timeout, 'timeout')
    _capture_bytes(capture)
    if provider_output_tokens is not None and (
            type(provider_output_tokens) is not int or provider_output_tokens <= 0):
        raise ValueError('provider output tokens must be a positive integer')
    return {
        'timeout_seconds': {
            'value': float(timeout),
            'source': 'task-override' if task_timeout_seconds is not None else 'role-policy',
            'classification': 'enforced',
            'rationale': 'Controller wall-clock process deadline.'},
        'max_capture_bytes': {
            'value': capture,
            'source': 'task-override' if task_capture_bytes is not None else 'role-policy',
            'classification': 'enforced',
            'rationale': 'Controller transport capture bound; not a generated-token limit.'},
        'generated_output_tokens': {
            'value': provider_output_tokens,
            'source': 'task-override' if provider_output_tokens is not None else 'provider-default',
            'classification': 'best-effort' if provider_output_tokens is not None else 'observable-only',
            'rationale': ('Explicit provider control, subject to verified CLI support.'
                          if provider_output_tokens is not None else
                          'Unset: provider behavior and effective ceiling are unknown.')},
    }


def resolve_product_task_budget(**overrides):
    unknown = set(overrides) - set(PRODUCT_TASK_POLICY)
    if unknown:
        raise ValueError('unknown product task budget')
    resolved = {}
    for name, configured in PRODUCT_TASK_POLICY.items():
        value = overrides.get(name)
        resolved[name] = {
            'value': configured if value is None else value,
            'source': 'role-policy' if value is None else 'task-override',
            'classification': 'enforced',
            'rationale': ('Configured controller workflow allocation.' if value is None else
                          'Explicit authorized task allocation.'),
        }
    integer_names = ('max_calls', 'max_provider_calls', 'max_concurrency',
                     'max_repairs', 'max_retries', 'max_escalations')
    if any(type(resolved[name]['value']) is not int for name in integer_names):
        raise ValueError('product task count budgets must be integers')
    if (resolved['max_calls']['value'] < 4 or
            not 3 <= resolved['max_provider_calls']['value'] <= resolved['max_calls']['value'] or
            not 1 <= resolved['max_concurrency']['value'] <= 2 or
            not 0 <= resolved['max_repairs']['value'] <= 2 or
            not 0 <= resolved['max_retries']['value'] <= 2 or
            not 0 <= resolved['max_escalations']['value'] <= 2):
        raise ValueError('invalid product task count budget')
    _positive_number(resolved['max_elapsed_seconds']['value'], 'overall elapsed budget')
    return resolved


def validate_resolution(value):
    if not isinstance(value, dict) or set(value) != {
            'timeout_seconds', 'max_capture_bytes', 'generated_output_tokens'}:
        raise ValueError('invalid resource resolution')
    for item in value.values():
        if (not isinstance(item, dict) or set(item) != {
                'value', 'source', 'classification', 'rationale'} or
                item['source'] not in CONTROL_SOURCES or
                item['classification'] not in CONTROL_CLASSES or
                not isinstance(item['rationale'], str) or not item['rationale']):
            raise ValueError('invalid resource-control provenance')
    _positive_number(value['timeout_seconds']['value'], 'timeout')
    _capture_bytes(value['max_capture_bytes']['value'])
    tokens = value['generated_output_tokens']['value']
    if tokens is not None and (type(tokens) is not int or tokens <= 0):
        raise ValueError('provider output tokens must be a positive integer')
    return value


def output_exhaustion_recovery(resolution, *, remaining_calls, remaining_seconds,
                               repeated_failure=False):
    """Remove one controller-imposed token control; never retry provider defaults blindly."""
    validate_resolution(resolution)
    control = resolution['generated_output_tokens']
    if (remaining_calls < 1 or remaining_seconds <= 0 or repeated_failure or
            control['value'] is None or control['source'] == 'provider-default'):
        return None
    recovered = {name: dict(value) for name, value in resolution.items()}
    recovered['generated_output_tokens'] = {
        'value': None, 'source': 'provider-default', 'classification': 'observable-only',
        'rationale': 'Removed an exhausted controller-imposed override within the existing task budget.'}
    return recovered


def policy_document():
    return {
        'precedence': ['task-override', 'role-policy', 'provider-default'],
        'role_policy': ROLE_POLICY,
        'product_task_policy': PRODUCT_TASK_POLICY,
        'provider_controls': PROVIDER_CONTROLS,
        'capability_profiles': {name: asdict(value) for name, value in CAPABILITY_PROFILES.items()},
    }
