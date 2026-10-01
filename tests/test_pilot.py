import json
import math
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from agentkit.pilot import (PilotError, build_report, initialize_pilot, pilot_status,
                            record_feedback, record_observation)


H = "a" * 64
R = "b" * 40


def protocol():
    shared = {"provider": "codex", "model": "account-default", "effort": "medium",
              "execution_profile": "trusted-disposable-macos", "call_limit": 2,
              "time_limit_seconds": 300}
    return {
        "schema_version": 1, "pilot_id": "pilot-one", "title": "Matched repository pilot",
        "randomization_seed": "precommitted-seed",
        "consent_version": "pilot-consent-v1",
        "provider_disclosure_sha256": "1" * 64,
        "retention_policy_sha256": "2" * 64,
        "conditions": [dict({"condition_id": "direct_cli", "mode": "direct_cli"}, **shared),
                       dict({"condition_id": "agentkit", "mode": "agentkit"}, **shared)],
        "participants": [
            {"participant_id": "operator-a", "local_evaluation_consent": True,
             "artifact_sharing_consent": False},
            {"participant_id": "operator-b", "local_evaluation_consent": True,
             "artifact_sharing_consent": False},
            {"participant_id": "operator-c", "local_evaluation_consent": True,
             "artifact_sharing_consent": True},
        ],
        "tasks": [
            {"task_id": "task-a", "project_id": "project-a", "base_revision": R,
             "task_contract_sha256": H, "acceptance_sha256": "c" * 64,
             "stratum": "python-small", "follow_up_days": 7},
            {"task_id": "task-b", "project_id": "project-b", "base_revision": "d" * 40,
             "task_contract_sha256": "e" * 64, "acceptance_sha256": "f" * 64,
             "stratum": "python-small", "follow_up_days": 7},
        ],
    }


def attempt(status="completed"):
    return {
        "attempt_id": "attempt-1", "status": status,
        "requested": {"provider": "codex", "model": "account-default", "effort": "medium"},
        "reported": {"provider": None, "model": None, "effort": None},
        "elapsed_seconds": None,
        "usage": {"input_tokens": None, "output_tokens": None,
                  "cached_input_tokens": None, "cache_creation_tokens": None,
                  "reasoning_tokens": None},
        "estimated_cost_usd": None, "billed_cost_usd": None, "cost_source": None,
    }


def observation(root, assignment, *, outcome="completed", first="passed", final="passed",
                follow_up=True):
    task_id = assignment["task_id"]
    acceptance = "c" * 64 if task_id == "task-a" else "f" * 64
    attempts = [] if outcome in {"blocked", "cancelled", "withdrawn", "not_run"} else [attempt(
        "completed" if outcome == "completed" else
        "authentication_required" if outcome == "authentication_required" else "failed")]
    reasons = {"completed": "none", "failed": "execution", "blocked": "environment",
               "cancelled": "cancellation", "withdrawn": "participant_withdrew",
               "timed_out": "timeout", "authentication_required": "authentication",
               "not_run": "not_started"}
    return {
        "schema_version": 1, "observation_id": "observation-" + assignment["assignment_id"],
        "assignment_id": assignment["assignment_id"],
        "assignment_sha256": assignment["assignment_sha256"],
        "protocol_sha256": pilot_status(root)["protocol_sha256"],
        "terminal_outcome": outcome, "terminal_reason": reasons[outcome],
        "first_pass_acceptance": first,
        "final_acceptance": final,
        "acceptance_at_utc": "2026-01-01T00:00:00Z" if final == "passed" else None,
        "follow_up_observed_at_utc": (
            "2026-01-08T00:00:00Z" if follow_up and final == "passed" else None),
        "merge_status": "not_merged",
        "wall_seconds": 42 if outcome == "completed" else None,
        "wall_seconds_unavailable_reason": None if outcome == "completed" else "ended before timing",
        "human_minutes": {"setup": 1, "operator_intervention": 2, "review": 3,
                          "source_edit": 0},
        "intervention_count": 1, "attempts": attempts,
        "checks": [{"check_id": "acceptance", "kind": "protected_acceptance",
                    "status": "passed" if final == "passed" else "failed",
                    "identity_sha256": acceptance}],
        "evidence": {"runtime_sha256": None, "policy_sha256": None,
                     "skills_sha256": None, "acceptance_sha256": acceptance,
                     "candidate_sha256": None, "package_sha256": None},
        "quality": {"follow_up_complete": follow_up,
                    "escaped_defects": 0 if follow_up else None,
                    "findings": {"true_positive": 1, "false_positive": 0, "unresolved": 0},
                    "unnecessary_repairs": 0, "repair_cycles": 0},
    }


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentkit-pilot-")
        self.parent = Path(self.tmp.name)
        self.root = self.parent / "pilot"
        self.addCleanup(self.tmp.cleanup)

    def assignments(self):
        return json.loads((self.root / "assignments.json").read_text())["assignments"]

    def test_initialization_freezes_private_deterministic_matched_assignments(self):
        status = initialize_pilot(self.root, protocol())
        self.assertEqual(status["assignment_count"], 4)
        self.assertEqual(status["missing_observation_count"], 4)
        self.assertFalse(status["execution_authority"])
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / "protocol.json").stat().st_mode & 0o777, 0o600)
        assignments = self.assignments()
        for task_id in ("task-a", "task-b"):
            cells = [item for item in assignments if item["task_id"] == task_id]
            self.assertEqual({item["condition_id"] for item in cells}, {"direct_cli", "agentkit"})
            self.assertEqual(len({item["participant_id"] for item in cells}), 2)

        second = self.parent / "second"
        initialize_pilot(second, protocol())
        self.assertEqual(json.loads((second / "assignments.json").read_text())["assignments"],
                         assignments)

    def test_protocol_is_strict_finite_consented_and_matched(self):
        cases = []
        value = protocol(); value["extra"] = True; cases.append(value)
        value = protocol(); value["participants"][0]["local_evaluation_consent"] = False; cases.append(value)
        value = protocol(); value["participants"] = value["participants"][:1]; cases.append(value)
        value = protocol(); value["conditions"][1]["model"] = "different"; cases.append(value)
        value = protocol(); value["conditions"][0]["time_limit_seconds"] = math.inf; cases.append(value)
        value = protocol(); value["conditions"][0]["time_limit_seconds"] = 0; value["conditions"][1]["time_limit_seconds"] = 0; cases.append(value)
        value = protocol(); value["tasks"][0]["unexpected"] = 1; cases.append(value)
        value = protocol(); value["tasks"][0]["follow_up_days"] = 0; cases.append(value)
        value = protocol(); value["participants"][0]["artifact_sharing_consent"] = "yes"; cases.append(value)
        for index, invalid in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(PilotError):
                initialize_pilot(self.parent / ("bad-" + str(index)), invalid)

    def test_fresh_root_and_symlinks_are_rejected(self):
        self.root.mkdir()
        with self.assertRaisesRegex(PilotError, "fresh"):
            initialize_pilot(self.root, protocol())
        self.root.rmdir()
        target = self.parent / "target"
        target.mkdir()
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(PilotError, "fresh"):
            initialize_pilot(self.root, protocol())

    def test_observations_are_strict_bound_and_immutable(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        value = observation(self.root, assignment)
        stored = record_observation(self.root, value)
        self.assertRegex(stored["record_sha256"], r"^[0-9a-f]{64}$")
        with self.assertRaisesRegex(PilotError, "already"):
            record_observation(self.root, value)

        other = self.assignments()[1]
        stale = observation(self.root, other)
        stale["assignment_sha256"] = H
        with self.assertRaisesRegex(PilotError, "binding"):
            record_observation(self.root, stale)
        invalid = observation(self.root, other)
        invalid["unknown"] = True
        with self.assertRaisesRegex(PilotError, "fields"):
            record_observation(self.root, invalid)

    def test_concurrent_records_for_one_assignment_have_one_winner(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        barrier = threading.Barrier(2)
        outcomes = []

        def write(index):
            value = observation(self.root, assignment)
            value["observation_id"] = "concurrent-" + str(index)
            barrier.wait()
            try:
                record_observation(self.root, value)
                outcomes.append("stored")
            except PilotError:
                outcomes.append("rejected")

        threads = [threading.Thread(target=write, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["rejected", "stored"])
        self.assertEqual(len(list((self.root / "observations").glob("*.json"))), 1)

    def test_failures_and_missing_assignments_remain_in_denominator(self):
        initialize_pilot(self.root, protocol())
        assignments = self.assignments()
        direct = next(item for item in assignments if item["condition_id"] == "direct_cli")
        failed = observation(self.root, direct, outcome="failed", first="not_assessed",
                             final="failed", follow_up=False)
        record_observation(self.root, failed)
        report = build_report(self.root)
        direct_report = report["conditions"]["direct_cli"]
        agentkit_report = report["conditions"]["agentkit"]
        self.assertEqual(direct_report["assigned_denominator"], 2)
        self.assertEqual(direct_report["terminal_outcomes"]["failed"], 1)
        self.assertEqual(direct_report["missing"], 1)
        self.assertEqual(agentkit_report["assigned_denominator"], 2)
        self.assertEqual(agentkit_report["missing"], 2)
        self.assertEqual(direct_report["rates"]["completion"],
                         {"numerator": 0, "denominator": 2, "value": 0.0})
        self.assertEqual(report["matched_pairs"]["incomplete_pairs"], 2)
        self.assertTrue(report["descriptive_only"])
        self.assertFalse(report["significance_tested"])
        self.assertFalse(report["superiority_claim"])

    def test_attempt_usage_cost_and_human_effort_preserve_unknowns(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        value = observation(self.root, assignment)
        value["attempts"].append(dict(attempt("failed"), attempt_id="attempt-2"))
        record_observation(self.root, value)
        report = build_report(self.root)["conditions"][assignment["condition_id"]]
        self.assertEqual(report["provider_attempts"], 2)
        self.assertEqual(report["usage"]["input_tokens"]["unknown_attempts"], 2)
        self.assertEqual(report["costs"]["billed_cost_usd"]["unknown_attempts"], 2)
        self.assertEqual(report["total_human_minutes"]["distribution"]["median"], 6)

    def test_reported_setting_deviations_are_visible_and_unknowns_stay_missing(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        value = observation(self.root, assignment)
        value["attempts"][0]["reported"] = {
            "provider": "codex", "model": "unexpected-model", "effort": None,
        }
        record_observation(self.root, value)
        status = pilot_status(self.root)
        self.assertEqual(status["observations_with_reported_setting_deviation"], 1)
        deviations = build_report(self.root)["conditions"][assignment["condition_id"]][
            "reported_setting_deviations"]
        self.assertEqual(deviations["observations"], 1)
        self.assertEqual(deviations["attempts"], 1)
        self.assertEqual(deviations["by_field"], {"provider": 0, "model": 1, "effort": 0})
        self.assertEqual(deviations["unknown_by_field"]["effort"], 1)

    def test_nullable_human_effort_is_missing_not_zero(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        value = observation(self.root, assignment)
        value["human_minutes"]["review"] = None
        record_observation(self.root, value)
        report = build_report(self.root)["conditions"][assignment["condition_id"]]
        self.assertEqual(report["human_minutes"]["review"]["unknown_observations"], 1)
        self.assertEqual(report["human_minutes"]["review"]["distribution"]["count"], 0)
        self.assertEqual(report["total_human_minutes"]["unknown_observations"], 1)
        self.assertEqual(report["total_human_minutes"]["distribution"]["count"], 0)

    def test_resource_deviations_are_retained_and_reported(self):
        value = protocol()
        for condition in value["conditions"]:
            condition["call_limit"] = 1
            condition["time_limit_seconds"] = 10
        initialize_pilot(self.root, value)
        assignment = self.assignments()[0]
        record = observation(self.root, assignment)
        record["attempts"][0]["elapsed_seconds"] = 6
        record["attempts"].append(dict(attempt("failed"), attempt_id="attempt-2",
                                       elapsed_seconds=5))
        record_observation(self.root, record)
        deviations = build_report(self.root)["conditions"][assignment["condition_id"]][
            "matching_resource_deviations"]
        self.assertEqual(deviations["observations"], 1)
        self.assertEqual(deviations["attempts_over_call_limit_observations"], 1)
        self.assertEqual(deviations["known_elapsed_over_time_limit_observations"], 1)
        self.assertEqual(pilot_status(self.root)[
            "observations_with_matching_or_resource_deviation"], 1)

    def test_explicit_terminal_failure_categories_are_retained(self):
        for index, outcome in enumerate(("timed_out", "authentication_required", "not_run")):
            root = self.parent / ("failure-" + str(index))
            initialize_pilot(root, protocol())
            assignment = json.loads((root / "assignments.json").read_text())["assignments"][0]
            value = observation(root, assignment, outcome=outcome, first="not_assessed",
                                final="failed", follow_up=False)
            record_observation(root, value)
            condition = build_report(root)["conditions"][assignment["condition_id"]]
            self.assertEqual(condition["terminal_outcomes"][outcome], 1)

    def test_invalid_outcome_claims_and_mismatched_attempt_settings_fail(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        invalid = observation(self.root, assignment, outcome="blocked", first="passed",
                              final="passed", follow_up=False)
        with self.assertRaisesRegex(PilotError, "non-completed"):
            record_observation(self.root, invalid)
        invalid = observation(self.root, assignment)
        invalid["attempts"][0]["requested"]["provider"] = "claude"
        with self.assertRaisesRegex(PilotError, "frozen condition"):
            record_observation(self.root, invalid)

    def test_acceptance_requires_independent_check_and_zero_first_pass_source_edits(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        invalid = observation(self.root, assignment)
        invalid["checks"] = []
        with self.assertRaisesRegex(PilotError, "protected check"):
            record_observation(self.root, invalid)
        invalid = observation(self.root, assignment)
        invalid["human_minutes"]["source_edit"] = 1
        with self.assertRaisesRegex(PilotError, "zero human source-edit"):
            record_observation(self.root, invalid)

    def test_follow_up_requires_accepted_candidate_and_frozen_window(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        premature = observation(self.root, assignment)
        premature["follow_up_observed_at_utc"] = "2026-01-07T23:59:59Z"
        with self.assertRaisesRegex(PilotError, "predates"):
            record_observation(self.root, premature)
        invalid = observation(self.root, assignment, outcome="not_run",
                              first="not_assessed", final="failed", follow_up=False)
        invalid["follow_up_observed_at_utc"] = "2026-01-08T00:00:00Z"
        invalid["quality"]["follow_up_complete"] = True
        invalid["quality"]["escaped_defects"] = 0
        with self.assertRaisesRegex(PilotError, "accepted completed"):
            record_observation(self.root, invalid)

    def test_duplicate_observation_labels_do_not_collapse_assignment_deviations(self):
        initialize_pilot(self.root, protocol())
        assignments = self.assignments()
        for assignment in assignments:
            value = observation(self.root, assignment)
            value["observation_id"] = "shared-label"
            if assignment["condition_id"] == "direct_cli" and assignment["task_id"] == "task-a":
                value["attempts"][0]["reported"]["model"] = "different-model"
            record_observation(self.root, value)
        pairs = build_report(self.root)["matched_pairs"]
        self.assertEqual(pairs["complete_observation_pairs"], 2)
        self.assertEqual(pairs["deviating_pairs"], 1)
        self.assertEqual(pairs["eligible_pairs"], 1)

    def test_feedback_has_no_free_text_and_is_immutable(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        feedback = {
            "schema_version": 1, "feedback_id": "feedback-one",
            "assignment_id": assignment["assignment_id"],
            "assignment_sha256": assignment["assignment_sha256"],
            "protocol_sha256": pilot_status(self.root)["protocol_sha256"],
            "evidence_usefulness": "helpful", "evidence_understandable": True,
            "limitations_understood": True, "review_confidence": "higher",
            "would_use_again": "yes",
        }
        record_feedback(self.root, feedback)
        with self.assertRaisesRegex(PilotError, "already"):
            record_feedback(self.root, dict(feedback, feedback_id="feedback-two"))
        bad = dict(feedback, feedback_id="feedback-three", comments="private text")
        bad["assignment_id"] = self.assignments()[1]["assignment_id"]
        bad["assignment_sha256"] = self.assignments()[1]["assignment_sha256"]
        with self.assertRaisesRegex(PilotError, "fields"):
            record_feedback(self.root, bad)
        self.assertEqual(build_report(self.root)["feedback"]["would_use_again"], {"yes": 1})

    def test_tampering_and_record_symlinks_fail_closed(self):
        initialize_pilot(self.root, protocol())
        assignment = self.assignments()[0]
        stored = record_observation(self.root, observation(self.root, assignment))
        path = self.root / "observations" / (assignment["assignment_id"] + ".json")
        value = json.loads(path.read_text())
        value["terminal_outcome"] = "failed"
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(PilotError, "integrity"):
            pilot_status(self.root)

        path.unlink()
        outside = self.parent / "outside.json"
        outside.write_text("{}")
        path.symlink_to(outside)
        with self.assertRaisesRegex(PilotError, "invalid record"):
            pilot_status(self.root)

    def test_ledger_never_starts_subprocesses_or_mutates_controller_state(self):
        with mock.patch("subprocess.run", side_effect=AssertionError("must not execute")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("must not execute")), \
             mock.patch("socket.create_connection", side_effect=AssertionError("must not network")):
            initialize_pilot(self.root, protocol())
            assignment = self.assignments()[0]
            record_observation(self.root, observation(self.root, assignment))
            build_report(self.root)
        self.assertFalse((self.root / "controller").exists())


if __name__ == "__main__":
    unittest.main()
