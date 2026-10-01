from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DistributionDocumentationTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_readme_links_every_p13_document(self):
        readme = self.read("README.md")
        for relative in (
                "docs/r3-distribution.md", "docs/r3-compatibility.md",
                "docs/r3-data-flow.md"):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
                self.assertIn("(" + relative + ")", readme)

    def test_distribution_links_are_local_and_resolve(self):
        for relative in (
                "docs/r3-distribution.md", "docs/r3-compatibility.md",
                "docs/r3-data-flow.md"):
            text = self.read(relative)
            links = re.findall(r"\[[^]]+\]\(([^)]+)\)", text)
            self.assertTrue(links, relative + " must link to related local documentation")
            for link in links:
                with self.subTest(source=relative, link=link):
                    self.assertFalse(link.startswith(("http://", "https://")))
                    self.assertTrue((ROOT / "docs" / link).resolve().is_file())

    def test_source_checkout_onboarding_is_exact_and_offline(self):
        guide = self.read("docs/r3-distribution.md")
        for required in (
                "SOURCE=/absolute/path/to/verified/AgentKit",
                "TARGET=/private/tmp/agentkit-offline-checkout",
                "RUNTIME=/private/tmp/agentkit-offline-runtime",
                "env -i", "python3 -m agentkit check",
                "python3 -m unittest discover -s tests -v",
                "node --test test/*.test.mjs", 'rm -r -- "$TARGET"',
                'rm -r -- "$RUNTIME"'):
            with self.subTest(required=required):
                self.assertIn(required, guide)
        self.assertIn("perform no model inference", guide)
        self.assertIn("onboarding did not modify any of them", guide)

    def test_isolated_install_artifacts_exist_but_outbound_license_does_not(self):
        self.assertFalse((ROOT / "LICENSE").exists())
        for relative in ("pyproject.toml", "setup.py", "setup.cfg", "MANIFEST.in"):
            self.assertTrue((ROOT / relative).is_file())
        distribution = self.read("docs/r3-distribution.md")
        readme = self.read("README.md")
        checklist = self.read("docs/checklist.md")
        self.assertIn("not a public distributable release", distribution)
        self.assertIn("no outbound `LICENSE`", distribution)
        self.assertIn("has no outbound `LICENSE`", readme)
        self.assertIn("[ ] Select an outbound license", checklist)
        self.assertIn("python3 setup.py sdist --dist-dir", distribution)
        self.assertIn("pip wheel --no-index --no-deps --no-build-isolation", distribution)
        self.assertIn("pip install --no-index --no-deps", distribution)
        self.assertIn("pip uninstall -y agentkit-controller", distribution)
        self.assertNotIn("python3 -m build", distribution)
        self.assertNotIn("npm install\n", distribution)

    def test_compatibility_matrix_matches_declared_runtime_boundaries(self):
        compatibility = self.read("docs/r3-compatibility.md")
        terminal_package = self.read("frontend/agentkit-terminal/package.json")
        for expected in (
                "Python 3.9+", "Python 3.9.6", "Node.js 18+", "Node.js 22.19.0",
                "Darwin 25.6.0 arm64", "Codex CLI", "0.154.0",
                "Claude Code", "2.1.220", "Linux, WSL2 and Windows",
                "Full-screen terminal UI", "General repository execution"):
            with self.subTest(expected=expected):
                self.assertIn(expected, compatibility)
        self.assertIn('"node": ">=18"', terminal_package)
        self.assertIn("Unsupported", compatibility)

    def test_data_flow_preserves_auth_approval_and_export_separation(self):
        flow = self.read("docs/r3-data-flow.md")
        for required in (
                "Provider service during an authorized live run",
                "provider-domain allowlist", "outside AgentKit's local evidence controls",
                "does not read credential contents", "raw login transcripts are not captured",
                "controller SQLite state", "redacted provider streams",
                "approval remains false", "excludes the controller database",
                "grants no approval", "Uninstalling the source checkout does not delete workflow roots"):
            with self.subTest(required=required):
                self.assertIn(required, flow)

    def test_planning_status_marks_documentation_done_and_release_incomplete(self):
        planning = self.read("docs/planning/README.md")
        engineering = self.read("docs/planning/engineering-plan.md")
        decisions = self.read("docs/decisions.md")
        self.assertIn("P13 source-checkout", planning)
        self.assertIn("public distribution remains incomplete", planning)
        self.assertIn("Private onboarding implemented; public release incomplete", engineering)
        self.assertIn("| D118 |", decisions)


if __name__ == "__main__":
    unittest.main()
