import hashlib
import json
from pathlib import Path
import re
import unittest


class CliIntegrationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = (Path(__file__).resolve().parents[1] /
                    'evidence' / 'phase4-cli-integration')

    def test_manifest_binds_every_retained_file(self):
        manifest = json.loads((self.root / 'manifest.json').read_text())
        actual = {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(self.root.rglob('*'))
                  if path.is_file() and path.name != 'manifest.json'}
        self.assertEqual(manifest['files'], actual)
        self.assertEqual(manifest['executable_revision'],
                         'a0f2906b59d7adf0858c1749228a5b2d815ea0c6')

    def test_checkpoint_failed_closed_without_game_review_or_retry(self):
        summary = json.loads((self.root / 'summary.json').read_text())
        self.assertEqual(summary['status'], 'blocked')
        self.assertEqual((summary['cli_launches'], summary['unused_cli_launches']), (4, 2))
        self.assertEqual(summary['review'], 'not_run_without_accepted_candidate')
        self.assertFalse(summary['game_trial_executed'])
        self.assertEqual(summary['retries_by_controller'], 0)
        self.assertFalse(summary['provider_substitution'])
        self.assertEqual([item['status'] for item in summary['launches']],
                         ['succeeded', 'succeeded', 'failed', 'failed'])
        self.assertEqual([item['error_class'] for item in summary['launches'][2:]],
                         ['authentication', 'authentication'])

    def test_productive_launches_did_not_set_historical_limits(self):
        comparison = json.loads((self.root / 'comparison.json').read_text())
        self.assertEqual(set(comparison['productive_provider_limit_environment'].values()),
                         {'unset'})
        self.assertEqual(comparison['pairs']['structured_planning']['direct_status'],
                         'succeeded')
        self.assertEqual(comparison['pairs']['structured_planning']['adapter_status'],
                         'succeeded')
        self.assertEqual(comparison['pairs']['independent_review']['status'], 'not_run')

    def test_archive_has_no_obvious_bearer_api_key_or_private_key(self):
        text = '\n'.join(path.read_text(errors='replace') for path in self.root.rglob('*')
                         if path.is_file())
        forbidden = [r'(?i)bearer\s+[a-z0-9._~-]{12,}',
                     r'(?i)sk-[a-z0-9_-]{12,}',
                     r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----']
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, text), pattern)


if __name__ == '__main__':
    unittest.main()
