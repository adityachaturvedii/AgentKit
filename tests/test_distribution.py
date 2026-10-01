import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="agentkit-distribution-")
        cls.root = Path(cls.temporary.name)
        cls.source = cls.root / "source"
        shutil.copytree(
            ROOT, cls.source,
            ignore=shutil.ignore_patterns(".git", "build", "dist", "*.egg-info", "__pycache__"),
        )
        cls.artifacts = cls.root / "artifacts"
        cls.artifacts.mkdir()
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for command in (
                [sys.executable, "setup.py", "sdist", "--dist-dir", str(cls.artifacts)],
                [sys.executable, "setup.py", "bdist_wheel", "--dist-dir", str(cls.artifacts)]):
            subprocess.run(command, cwd=cls.source, env=environment, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
        cls.sdist = next(cls.artifacts.glob("*.tar.gz"))
        cls.wheel = next(cls.artifacts.glob("*.whl"))
        cls.venv = cls.root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(cls.venv)
        cls.python = cls.venv / "bin" / "python"
        cls.command = cls.venv / "bin" / "agentkit"
        subprocess.run(
            [str(cls.python), "-m", "pip", "install", "--no-index", "--no-deps",
             "--disable-pip-version-check", str(cls.wheel)],
            cwd=cls.root, env=environment, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=90,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_agentkit(self, *arguments):
        return subprocess.run(
            [str(self.command), *arguments], cwd=self.root,
            env={"PATH": os.environ.get("PATH", ""), "HOME": str(self.root / "empty-home"),
                 "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
        )

    def test_wheel_and_sdist_contain_runtime_and_attribution_resources(self):
        required = (
            "catalog.json", "skills/task-contract/SKILL.md", "domains/frontend.md",
            "contracts/handoff.schema.json", "audit/sources.lock.json",
            "THIRD_PARTY_NOTICES.md", "notices/pstack-LICENSE.txt",
            "third_party/openharness/LICENSE", "docs/skill-contract.md",
            "docs/product-workflow.md", "docs/r5-validation-report.md",
            "frontend/agentkit-terminal/src/render-events.mjs",
        )
        with zipfile.ZipFile(self.wheel) as archive:
            wheel_names = archive.namelist()
        with tarfile.open(self.sdist, "r:gz") as archive:
            sdist_names = archive.getnames()
        for relative in required:
            self.assertEqual(len([name for name in wheel_names if name.endswith(relative)]), 1)
            self.assertEqual(len([name for name in sdist_names if name.endswith(relative)]), 1)
        self.assertFalse(any("/audit/evaluations/" in name for name in wheel_names))
        self.assertFalse(any("/audit/evaluations/" in name for name in sdist_names))

    def test_installed_console_check_list_show_and_help(self):
        help_result = self.run_agentkit("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("AgentKit engineering-agent controller", help_result.stdout)
        checked = self.run_agentkit("check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["skills"], 10)
        listed = self.run_agentkit("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(len(json.loads(listed.stdout)["skills"]), 10)
        shown = self.run_agentkit("show", "behavioral-testing", "--domain", "frontend")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("# Behavioral testing", shown.stdout)
        self.assertIn("Trigger: A user-visible web flow", shown.stdout)

    def test_installed_package_verification_executes_no_candidate(self):
        package = self.root / "portable"
        (package / "evidence").mkdir(parents=True)
        base = "a" * 40
        head = "b" * 40
        required_ids = ["verification-0", "review-0", "approval-package"]
        approval = {
            "task_id": "installed-check", "managed_base_revision": base,
            "head_revision": head, "status": "awaiting_pr_approval",
            "approval": {"recorded": False}, "verification_evidence": ["verification-0"],
            "review_evidence": "review-0", "requirements": [{"id": "R1", "expected": "works"}],
            "diff": "",
        }
        files = {
            "approval-package.json": json.dumps(approval).encode(),
            "candidate.diff": b"",
            "requirement-matrix.json": json.dumps({"requirements": [{
                "requirement_id": "R1", "expected": "works", "status": "passed",
                "evidence": required_ids}]}).encode(),
            "review-guide.json": json.dumps({"purpose": "offline"}).encode(),
        }
        for identity, kind in (("verification-0", "independent-check"),
                               ("review-0", "independent-review"),
                               ("approval-package", "approval-package")):
            files["evidence/" + identity + ".json"] = json.dumps({
                "evidence_id": identity, "revision": head, "kind": kind, "status": "passed"}).encode()
        for relative, payload in files.items():
            target = package / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        manifest = {
            "schema_version": 1, "task_id": "installed-check", "base_revision": base,
            "head_revision": head, "execution_on_import": False,
            "files": {relative: {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
                      for relative, payload in files.items()},
        }
        (package / "manifest.json").write_text(json.dumps(manifest))
        result = self.run_agentkit("package", "verify", str(package))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])
        self.assertFalse(json.loads(result.stdout)["execution_performed"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for terminal rendering")
    def test_installed_terminal_renderer_uses_bundled_frontend(self):
        stream = self.root / "events.jsonl"
        stream.write_text(json.dumps({"version": 1, "type": "shutdown", "message": "done"}) + "\n")
        script = ("from agentkit.integrations.openharness.backend import "
                  "_render_with_adapted_terminal; import sys; "
                  "print(_render_with_adapted_terminal(sys.argv[1]), end='')")
        result = subprocess.run(
            [str(self.python), "-c", script, str(stream)], cwd=self.root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AgentKit", result.stdout)
        self.assertIn("done", result.stdout)


if __name__ == "__main__":
    unittest.main()
