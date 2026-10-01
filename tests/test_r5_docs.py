from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class R5DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = (ROOT / 'docs/product-workflow.md').read_text(encoding='utf-8')
        cls.report = (ROOT / 'docs/r5-validation-report.md').read_text(encoding='utf-8')
        cls.plan = (ROOT / 'docs/planning/engineering-plan.md').read_text(encoding='utf-8')

    def test_guide_defines_snapshot_browser_and_portable_boundaries(self):
        for expected in (
                'serves that snapshot rather than the Git worktree',
                'Git metadata and untracked files are excluded',
                'identify the browser and version',
                'distinct from the recorded implementation providers',
                'does not launch a browser or prove that the reported interaction happened',
                'python3 -m agentkit package export',
                'planning authentication failure currently blocks'):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.guide)

    def test_validation_report_does_not_promote_fixture_evidence_to_live(self):
        self.assertIn('real provider and browser acceptance pending', self.report)
        self.assertIn('This validator does not run a browser', self.report)
        self.assertIn('No provider inference', self.report)
        self.assertIn('No live product, Breakout completion', self.report)
        self.assertIn('P15 | **Offline foundation implemented; live browser acceptance pending:**',
                      self.plan)


if __name__ == '__main__':
    unittest.main()
