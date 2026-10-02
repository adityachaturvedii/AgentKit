import json
from pathlib import Path
import tempfile
import unittest

from agentkit.pilot import initialize_pilot


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/examples/pilot-protocol.json"
GUIDE_PATH = ROOT / "docs/r4-pilot-protocol.md"
REPORT_PATH = ROOT / "docs/r4-pilot-validation-report.md"


class PilotDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        cls.guide = GUIDE_PATH.read_text(encoding="utf-8")
        cls.report = REPORT_PATH.read_text(encoding="utf-8")

    def test_example_validates_and_initialization_freezes_without_authority(self):
        with tempfile.TemporaryDirectory(prefix="agentkit-pilot-docs-") as temporary:
            status = initialize_pilot(Path(temporary) / "pilot", self.protocol)
        self.assertEqual(status["pilot_id"], self.protocol["pilot_id"])
        self.assertEqual(status["state"], "frozen_collecting")
        self.assertEqual(status["assignment_count"], len(self.protocol["tasks"]) * 2)
        self.assertEqual(status["missing_observation_count"], status["assignment_count"])
        self.assertFalse(status["execution_authority"])

    def test_example_predeclares_exact_matched_conditions_tasks_and_consent(self):
        protocol = self.protocol
        self.assertEqual(protocol["schema_version"], 1)
        self.assertTrue(protocol["randomization_seed"])
        self.assertRegex(protocol["consent_version"], r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
        self.assertRegex(protocol["provider_disclosure_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(protocol["retention_policy_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual({item["condition_id"] for item in protocol["conditions"]},
                         {"direct_cli", "agentkit"})
        shared = ("provider", "model", "effort", "execution_profile", "call_limit",
                  "time_limit_seconds")
        direct, agentkit = protocol["conditions"]
        for field in shared:
            with self.subTest(field=field):
                self.assertEqual(direct[field], agentkit[field])
        self.assertGreaterEqual(len(protocol["participants"]), 2)
        self.assertTrue(all(item["local_evaluation_consent"]
                            for item in protocol["participants"]))
        self.assertTrue(all(item["artifact_sharing_consent"] is False
                            for item in protocol["participants"]))
        self.assertTrue(protocol["tasks"])
        for task in protocol["tasks"]:
            self.assertRegex(task["base_revision"], r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
            self.assertRegex(task["task_contract_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(task["acceptance_sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(task["follow_up_days"], 0)

    def test_guide_covers_freeze_denominators_deviations_effort_and_missingness(self):
        expected = (
            "frozen protocol and its generated assignment",
            "same task, project, base, task contract, protected acceptance",
            "reported provider/model/effort that differs",
            "allocated assignment without an observation remains an explicit missing",
            "Every retry and provider launch is a separate attempt",
            "first-pass acceptance separately from final acceptance",
            "active setup, operator-intervention, review, and human source-edit minutes",
            "without completed follow-up has escaped defects unknown, not zero",
            "Unknown native retries or billed costs remain unknown",
            "denominators beside every rate",
        )
        for text in expected:
            with self.subTest(text=text):
                self.assertIn(text, self.guide)

    def test_guide_covers_consent_discovery_and_secret_exclusion(self):
        expected = (
            "Consent is required before repository inspection, task capture, or provider use",
            "Repository/task authorization and evaluation-artifact sharing are separate choices",
            "Publicly readable code is not permission",
            "Missing consent blocks collection and is not recorded as a task failure",
            "Real credentials, production data, login transcripts, and authorization codes are prohibited",
            "ignored/untracked content, symlinks, task text, prompts, outputs, diffs, filenames, notes, and exports",
            "do not prove comprehensive secret or credential isolation",
        )
        for text in expected:
            with self.subTest(text=text):
                self.assertIn(text, self.guide)

    def test_guide_specifies_exact_five_offline_commands_and_limits(self):
        exact_commands = (
            "pilot init --root /private/tmp/agentkit-pilot --protocol",
            "pilot status --root /private/tmp/agentkit-pilot",
            "pilot record --root /private/tmp/agentkit-pilot --observation",
            "pilot feedback --root /private/tmp/agentkit-pilot --feedback",
            "pilot report --root /private/tmp/agentkit-pilot",
        )
        for command in exact_commands:
            with self.subTest(command=command):
                self.assertIn(command, self.guide)
        self.assertIn("do not launch a provider", self.guide)
        self.assertIn("prints a descriptive JSON report", self.guide)
        self.assertIn("requires the participant's artifact-sharing choice", self.guide)

    def test_validation_report_keeps_uncollected_results_pending_and_neutral(self):
        self.assertIn("comparative collection and results pending", self.report)
        self.assertGreaterEqual(self.report.count("Pending"), 10)
        self.assertIn("must remain missing rather than being reported as zero", self.report)
        self.assertIn("not added to this table or used as pilot results", self.report)
        for absent_claim in ("faster", "cheaper", "more accurate", "statistically superior"):
            with self.subTest(absent_claim=absent_claim):
                self.assertIn(absent_claim, self.report)
        self.assertIn("no actual collection, live inference, credential access, real-repository onboarding",
                      self.report)


if __name__ == "__main__":
    unittest.main()
