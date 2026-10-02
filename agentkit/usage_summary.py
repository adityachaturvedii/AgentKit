"""Honest aggregation of provider-reported usage observations."""

from collections.abc import Mapping
import json
import math


PROVIDER_ENGINES = frozenset(('codex', 'claude'))
TOKEN_QUANTITIES = (
    'input_tokens',
    'output_tokens',
    'cached_input_tokens',
    'cache_creation_tokens',
    'reasoning_tokens',
)
COST_QUANTITIES = ('estimated_cost_usd', 'billed_cost_usd')
QUANTITIES = TOKEN_QUANTITIES + COST_QUANTITIES
NOT_LAUNCHED_STATUSES = frozenset(('reserved', 'reconciled_not_started'))


def _usage(execution):
    value = execution.get('usage')
    if value is None and execution.get('usage_json'):
        try:
            value = json.loads(execution['usage_json'])
        except (TypeError, ValueError) as exc:
            raise ValueError('usage_json must contain a JSON object') from exc
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError('execution usage must be an object or unknown')
    return value


def _validate_quantity(name, value):
    if value is None:
        return
    if name in TOKEN_QUANTITIES:
        valid = type(value) is int and value >= 0
    else:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    if not valid:
        raise ValueError(name + ' must be nonnegative or unknown')


def _quantity(observations, name):
    values = []
    for observation in observations:
        value = observation.get(name)
        _validate_quantity(name, value)
        if value is not None:
            values.append(value)
    contributing = len(values)
    missing = len(observations) - contributing
    if not observations or not values:
        completeness = 'unknown'
    elif missing:
        completeness = 'partial'
    else:
        completeness = 'complete'
    return {
        'reported_subtotal': sum(values) if values else None,
        'contributing_execution_count': contributing,
        'missing_execution_count': missing,
        'completeness': completeness,
    }


def _quantities(observations):
    return {name: _quantity(observations, name) for name in QUANTITIES}


def summarize_usage(executions, *, wall_elapsed_seconds=None, reservations=None,
                    provider_engines=PROVIDER_ENGINES):
    """Summarize launched executions without inventing unreported provider telemetry.

    ``executions`` accepts controller snapshot rows (including ``usage_json``) or
    presentation rows containing a decoded ``usage`` mapping. A CLI launch is any
    execution whose status is no longer reserved or reconciled as not started.
    """
    if not isinstance(executions, (list, tuple)):
        raise ValueError('executions must be a sequence')
    if wall_elapsed_seconds is not None and (
            type(wall_elapsed_seconds) not in (int, float) or
            not math.isfinite(wall_elapsed_seconds) or wall_elapsed_seconds < 0):
        raise ValueError('wall elapsed seconds must be nonnegative or unknown')

    launched = []
    for execution in executions:
        if not isinstance(execution, Mapping):
            raise ValueError('each execution must be an object')
        if execution.get('status') not in NOT_LAUNCHED_STATUSES:
            launched.append(execution)

    providers = [item for item in launched if item.get('engine') in provider_engines]
    local = [item for item in launched if item.get('engine') not in provider_engines]
    provider_observations = [_usage(item) for item in providers]
    by_provider = {}
    for engine in sorted({item.get('engine') for item in providers}):
        selected = [item for item in providers if item.get('engine') == engine]
        by_provider[engine] = {
            'cli_launches': len(selected),
            'usage': _quantities([_usage(item) for item in selected]),
        }

    elapsed = []
    for execution in launched:
        value = execution.get('elapsed_seconds')
        if value is not None:
            if (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError('execution elapsed seconds must be nonnegative or unknown')
            elapsed.append(value)

    return {
        'schema_version': 1,
        'cli_launches': {
            'provider': len(providers),
            'local_checks': len(local),
            'total': len(launched),
        },
        'provider_internal_requests': None,
        'provider_internal_turns': None,
        'provider_usage': _quantities(provider_observations),
        'providers': by_provider,
        'local_checks': {
            'cli_launches': len(local),
            'summed_execution_seconds': sum(
                item['elapsed_seconds'] for item in local
                if item.get('elapsed_seconds') is not None),
        },
        'elapsed': {
            'wall_seconds': wall_elapsed_seconds,
            'summed_execution_seconds': sum(elapsed) if elapsed else None,
        },
        'reservations': dict(reservations) if reservations is not None else None,
    }
