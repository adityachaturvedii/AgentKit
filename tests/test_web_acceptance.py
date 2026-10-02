import hashlib
from pathlib import Path
import tempfile
import unittest

from agentkit.web_acceptance import (MAX_ACCEPTANCE_CHECKS, WebAcceptanceError,
                                     create_preview_snapshot, validate_browser_report)


REVISION = "a" * 40
ACCEPTANCE = [
    {"id": "keyboard", "expected": "Enter activates the primary action."},
    {"id": "reset", "expected": "Reset restores the initial state."},
]


class WebAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentkit-web-acceptance-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "index.html").write_text("<main>Counter</main>\n")
        (self.source / "assets").mkdir()
        (self.source / "assets/app.js").write_text("window.value = 0;\n")
        (self.source / ".git").write_text("gitdir: /private/controller/repository\n")
        (self.source / "untracked.txt").write_text("not selected\n")
        self.manifest = {
            "index.html": self.sha(self.source / "index.html"),
            "assets/app.js": self.sha(self.source / "assets/app.js"),
        }
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()

    @staticmethod
    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def snapshot(self, name="preview"):
        return create_preview_snapshot(self.source, self.root / name,
                                       self.manifest, REVISION)

    def receipt(self, snapshot):
        return {
            "schema_version": 1,
            "candidate_revision": snapshot["candidate_revision"],
            "session_id": snapshot["session_id"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "status": "stopped",
            "cleanup_confirmed": True,
        }

    def report(self, snapshot):
        return {
            "schema_version": 1,
            "candidate_revision": REVISION,
            "session_id": snapshot["session_id"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "browser": {"name": "Fixture Browser", "version": "1.0"},
            "verifier": {"id": "operator-1", "type": "human"},
            "implementation_authors": ["implementer-1"],
            "checks": [
                {"id": item["id"], "status": "passed", "action": "Performed " + item["id"],
                 "assertion": item["expected"], "observation": "Observed expected behavior."}
                for item in ACCEPTANCE
            ],
            "screenshots": [],
            "visual_judgment": {"status": "passed", "observation": "Layout remained readable."},
        }

    def validate(self, report, snapshot, receipt=None, **kwargs):
        return validate_browser_report(
            report, acceptance=kwargs.get("acceptance", ACCEPTANCE),
            candidate_revision=kwargs.get("candidate_revision", REVISION),
            preview_receipt=receipt or self.receipt(snapshot), evidence_root=self.evidence,
            implementation_authors=kwargs.get("implementation_authors", ["implementer-1"]))

    def test_snapshot_is_private_plain_files_only_and_deterministic(self):
        first = self.snapshot("first")
        second = self.snapshot("second")
        first_root = Path(first["snapshot_root"])
        self.assertEqual(first_root.stat().st_mode & 0o777, 0o700)
        self.assertEqual((first_root / "index.html").read_text(), "<main>Counter</main>\n")
        self.assertFalse((first_root / ".git").exists())
        self.assertFalse((first_root / "untracked.txt").exists())
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(first["snapshot_sha256"], second["snapshot_sha256"])
        self.assertNotEqual(first["session_id"], second["session_id"])

    def test_snapshot_rejects_tamper_path_escape_git_and_symlink(self):
        changed = dict(self.manifest)
        changed["index.html"] = "0" * 64
        with self.assertRaisesRegex(WebAcceptanceError, "does not match"):
            create_preview_snapshot(self.source, self.root / "tampered", changed, REVISION)
        for unsafe in ("../escape", "/absolute", ".git", "nested/.git/config"):
            with self.subTest(unsafe=unsafe), self.assertRaises(WebAcceptanceError):
                create_preview_snapshot(self.source, self.root / ("bad-" + hashlib.sha1(
                    unsafe.encode()).hexdigest()), {unsafe: "0" * 64}, REVISION)
        outside = self.root / "outside.js"
        outside.write_text("outside\n")
        (self.source / "link.js").symlink_to(outside)
        with self.assertRaisesRegex(WebAcceptanceError, "non-symlink"):
            create_preview_snapshot(self.source, self.root / "linked",
                                    {"link.js": self.sha(outside)}, REVISION)

    def test_strict_bound_report_normalizes_a_passing_record(self):
        snapshot = self.snapshot()
        screenshot = self.evidence / "screen.png"
        screenshot.write_bytes(b"fixture-png")
        report = self.report(snapshot)
        report["screenshots"] = [{"path": "screen.png", "sha256": self.sha(screenshot),
                                  "viewport": "1280x720"}]
        result = self.validate(report, snapshot)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["checks"][0]["expected"], ACCEPTANCE[0]["expected"])
        self.assertIn("does not run a browser", result["limitations"][0])

    def test_report_requires_stopped_cleanup_confirmed_receipt(self):
        snapshot = self.snapshot()
        report = self.report(snapshot)
        for status, cleanup in (("running", True), ("stopped", False)):
            receipt = self.receipt(snapshot)
            receipt.update(status=status, cleanup_confirmed=cleanup)
            with self.subTest(status=status, cleanup=cleanup), self.assertRaisesRegex(
                    WebAcceptanceError, "cleanup"):
                self.validate(report, snapshot, receipt)

    def test_report_rejects_revision_session_and_snapshot_tamper(self):
        snapshot = self.snapshot()
        for key, value in (("candidate_revision", "b" * 40),
                           ("session_id", "0" * 32),
                           ("snapshot_sha256", "0" * 64)):
            report = self.report(snapshot)
            report[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(
                    WebAcceptanceError, "another preview or candidate"):
                self.validate(report, snapshot)

    def test_report_schema_checks_and_bounds_are_strict(self):
        snapshot = self.snapshot()
        mutations = []
        report = self.report(snapshot)
        report["extra"] = True
        mutations.append(report)
        report = self.report(snapshot)
        report["browser"].pop("version")
        mutations.append(report)
        report = self.report(snapshot)
        report["checks"][0] = "not-an-object"
        mutations.append(report)
        report = self.report(snapshot)
        report["checks"][1]["id"] = report["checks"][0]["id"]
        mutations.append(report)
        report = self.report(snapshot)
        report["checks"][0]["observation"] = "x" * 9000
        mutations.append(report)
        report = self.report(snapshot)
        report["visual_judgment"]["status"] = "pending"
        mutations.append(report)
        report = self.report(snapshot)
        report["schema_version"] = True
        mutations.append(report)
        for index, malformed in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(WebAcceptanceError):
                self.validate(malformed, snapshot)
        too_many = [{"id": "c" + str(index), "expected": "observable"}
                    for index in range(MAX_ACCEPTANCE_CHECKS + 1)]
        with self.assertRaisesRegex(WebAcceptanceError, "acceptance"):
            self.validate(self.report(snapshot), snapshot, acceptance=too_many)

    def test_failed_check_or_visual_judgment_produces_failed_result(self):
        snapshot = self.snapshot()
        report = self.report(snapshot)
        report["checks"][0]["status"] = "failed"
        self.assertEqual(self.validate(report, snapshot)["status"], "failed")
        report = self.report(snapshot)
        report["visual_judgment"] = {"status": "failed", "observation": "Controls overlap."}
        self.assertEqual(self.validate(report, snapshot)["status"], "failed")

    def test_independence_metadata_is_exact_and_verifier_is_separate(self):
        snapshot = self.snapshot()
        report = self.report(snapshot)
        report["verifier"]["id"] = "implementer-1"
        with self.assertRaisesRegex(WebAcceptanceError, "not independent"):
            self.validate(report, snapshot)
        report = self.report(snapshot)
        report["implementation_authors"] = ["somebody-else"]
        with self.assertRaisesRegex(WebAcceptanceError, "metadata changed"):
            self.validate(report, snapshot)
        report = self.report(snapshot)
        report["verifier"]["type"] = "model"
        with self.assertRaisesRegex(WebAcceptanceError, "type"):
            self.validate(report, snapshot)

    def test_screenshot_must_be_bounded_regular_file_inside_evidence_root(self):
        snapshot = self.snapshot()
        outside = self.root / "outside.png"
        outside.write_bytes(b"outside")
        (self.evidence / "linked.png").symlink_to(outside)
        cases = [
            {"path": "../outside.png", "sha256": self.sha(outside), "viewport": "800x600"},
            {"path": "linked.png", "sha256": self.sha(outside), "viewport": "800x600"},
            {"path": "missing.png", "sha256": "0" * 64, "viewport": "800x600"},
            {"path": "missing.png", "sha256": "0" * 64, "viewport": "0x600"},
        ]
        for item in cases:
            report = self.report(snapshot)
            report["screenshots"] = [item]
            with self.subTest(item=item), self.assertRaises(WebAcceptanceError):
                self.validate(report, snapshot)


if __name__ == "__main__":
    unittest.main()
