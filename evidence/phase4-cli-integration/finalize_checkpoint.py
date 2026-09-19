#!/usr/bin/env python3
"""Finalize retained checkpoint evidence without launching a provider CLI."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
progress = json.loads((ROOT / 'checkpoint-progress.json').read_text())


def read_result(relative):
    return json.loads((ROOT / relative / 'result.json').read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


results = {
    'codex_direct_planning': read_result('01-codex-direct-plan'),
    'codex_adapter_planning': read_result('02-codex-adapter-plan'),
    'claude_direct_implementation': read_result('03-claude-direct-implementation'),
    'claude_adapter_implementation': read_result('04-claude-adapter-implementation'),
}
comparison = {
    'schema_version': 1,
    'executable_revision': progress['executable_revision'],
    'pairs': {
        'structured_planning': {
            'provider': 'codex',
            'direct_status': results['codex_direct_planning']['status'],
            'adapter_status': results['codex_adapter_planning']['status'],
            'direct_launch': results['codex_direct_planning']['provider_details']['launch_configuration'],
            'adapter_launch': results['codex_adapter_planning']['provider_details']['launch_configuration'],
            'controller_acceptance': [progress['launches'][0]['acceptance'],
                                      progress['launches'][1]['acceptance']],
        },
        'code_implementation': {
            'provider': 'claude',
            'direct_status': results['claude_direct_implementation']['status'],
            'adapter_status': results['claude_adapter_implementation']['status'],
            'direct_error': results['claude_direct_implementation']['error_class'],
            'adapter_error': results['claude_adapter_implementation']['error_class'],
            'direct_launch': results['claude_direct_implementation']['provider_details']['launch_configuration'],
            'adapter_launch': results['claude_adapter_implementation']['provider_details']['launch_configuration'],
            'controller_acceptance': [progress['launches'][2]['acceptance'],
                                      progress['launches'][3]['acceptance']],
            'finding': 'Both paths reached the same installed CLI and failed with expired subscription OAuth before tools ran.',
        },
        'independent_review': {
            'provider': 'codex',
            'status': 'not_run',
            'reason': 'No independently accepted implementation candidate; only two of six launches remained.',
        },
    },
    'productive_provider_limit_environment': {
        'CLAUDE_CODE_MAX_OUTPUT_TOKENS': 'unset',
        'CLAUDE_CODE_MAX_TURNS': 'unset',
        'CLAUDE_CODE_MAX_RETRIES': 'unset',
    },
}
(ROOT / 'comparison.json').write_text(json.dumps(comparison, indent=2, sort_keys=True) + '\n')

launches = progress['launches']
summary = {
    'schema_version': 1,
    'status': 'blocked',
    'executable_revision': progress['executable_revision'],
    'cli_launches': len(launches),
    'authorized_cli_launches': 6,
    'unused_cli_launches': 6 - len(launches),
    'provider_requests': None,
    'turns': None,
    'observed_claude_retry_events_per_failed_launch': 2,
    'elapsed_seconds_through_last_record': progress['elapsed_seconds'],
    'overall_deadline_seconds': 1200,
    'launches': launches,
    'passed_stages': ['codex direct structured planning',
                      'codex adapter structured planning'],
    'blocked_stage': 'claude direct/adapter owned-code implementation',
    'blocker': 'Claude Code reported 401 OAuth access token has expired on both paths.',
    'review': 'not_run_without_accepted_candidate',
    'game_trial_executed': False,
    'retries_by_controller': 0,
    'provider_substitution': False,
    'reported_usage_totals_for_successful_codex_launches': {
        'input_tokens': 24927,
        'output_tokens': 3226,
        'cached_input_tokens': 14592,
        'cache_creation_tokens': None,
        'reasoning_tokens': 0,
    },
    'claude_failed_launch_usage': ('historical normalized records are unknown; each complete raw terminal '
                                   'reported zero input/output/cache tokens and zero estimated cost'),
    'post_run_offline_correction_revision': '1c0008c34ef85bdcc303edfe6f7f5ac5465cafca',
    'post_run_offline_correction_note': ('Complete terminal usage and retry/turn observations are now '
                                         'preserved after a monitored stop; this correction was not live-tested.'),
    'estimated_cost_usd': None,
    'billed_cost_usd': None,
    'billing_note': 'No hard token or monetary cap is inferred; billing and paid overflow remain unknown.',
}
(ROOT / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')

files = {str(path.relative_to(ROOT)): digest(path)
         for path in sorted(ROOT.rglob('*'))
         if path.is_file() and path.name != 'manifest.json'}
(ROOT / 'manifest.json').write_text(json.dumps({
    'schema_version': 1,
    'executable_revision': progress['executable_revision'],
    'files': files,
}, indent=2, sort_keys=True) + '\n')
print(json.dumps(summary, indent=2, sort_keys=True))
