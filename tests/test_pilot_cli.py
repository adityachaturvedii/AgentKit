import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PilotCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agentkit-pilot-cli-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.state = self.base / "state"

    def run_cli(self, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, "-m", "agentkit", *arguments], cwd=ROOT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def initialize(self):
        result = self.run_cli(
            "pilot", "init", "--root", str(self.state), "--protocol",
            str(ROOT / "docs/examples/pilot-protocol.json"),
        )
        return json.loads(result.stdout)

    def test_complete_offline_cli_record_and_report_path(self):
        initialized = self.initialize()
        self.assertEqual(initialized["state"], "frozen_collecting")
        self.assertFalse(initialized["execution_authority"])
        assignment = json.loads((self.state / "assignments.json").read_text())["assignments"][0]
        protocol = json.loads((self.state / "protocol.json").read_text())
        task = next(item for item in protocol["protocol"]["tasks"]
                    if item["task_id"] == assignment["task_id"])
        observation = {
            "schema_version": 1,
            "observation_id": "cli-not-run",
            "assignment_id": assignment["assignment_id"],
            "assignment_sha256": assignment["assignment_sha256"],
            "protocol_sha256": protocol["protocol_sha256"],
            "terminal_outcome": "not_run",
            "terminal_reason": "not_started",
            "first_pass_acceptance": "not_assessed",
            "final_acceptance": "failed",
            "acceptance_at_utc": None,
            "follow_up_observed_at_utc": None,
            "merge_status": "not_applicable",
            "wall_seconds": None,
            "wall_seconds_unavailable_reason": "fixture record did not execute work",
            "human_minutes": {"setup": None, "operator_intervention": None,
                              "review": None, "source_edit": None},
            "intervention_count": 0,
            "attempts": [],
            "checks": [],
            "evidence": {"runtime_sha256": None, "policy_sha256": None,
                         "skills_sha256": None,
                         "acceptance_sha256": task["acceptance_sha256"],
                         "candidate_sha256": None, "package_sha256": None},
            "quality": {"follow_up_complete": False, "escaped_defects": None,
                        "findings": {"true_positive": 0, "false_positive": 0,
                                     "unresolved": 0},
                        "unnecessary_repairs": 0, "repair_cycles": 0},
        }
        observation_path = self.base / "observation.json"
        observation_path.write_text(json.dumps(observation))
        recorded = json.loads(self.run_cli(
            "pilot", "record", "--root", str(self.state),
            "--observation", str(observation_path)).stdout)
        self.assertEqual(recorded["terminal_outcome"], "not_run")

        feedback = {
            "schema_version": 1, "feedback_id": "cli-feedback",
            "assignment_id": assignment["assignment_id"],
            "assignment_sha256": assignment["assignment_sha256"],
            "protocol_sha256": protocol["protocol_sha256"],
            "evidence_usefulness": "neutral", "evidence_understandable": True,
            "limitations_understood": True, "review_confidence": "same",
            "would_use_again": "unsure",
        }
        feedback_path = self.base / "feedback.json"
        feedback_path.write_text(json.dumps(feedback))
        self.run_cli("pilot", "feedback", "--root", str(self.state),
                     "--feedback", str(feedback_path))

        status = json.loads(self.run_cli(
            "pilot", "status", "--root", str(self.state)).stdout)
        self.assertEqual(status["observation_count"], 1)
        self.assertEqual(status["feedback_count"], 1)
        report = json.loads(self.run_cli(
            "pilot", "report", "--root", str(self.state)).stdout)
        condition = report["conditions"][assignment["condition_id"]]
        self.assertEqual(condition["terminal_outcomes"]["not_run"], 1)
        self.assertTrue(report["descriptive_only"])
        self.assertFalse(report["superiority_claim"])

        duplicate = self.run_cli(
            "pilot", "record", "--root", str(self.state),
            "--observation", str(observation_path), expected=2)
        self.assertIn("observation record already exists", duplicate.stderr)

    def test_status_rejects_missing_state_without_creating_it(self):
        result = self.run_cli(
            "pilot", "status", "--root", str(self.state), expected=2)
        self.assertIn("pilot root does not exist", result.stderr)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
