import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrandingTests(unittest.TestCase):
    def test_public_product_name_is_agentkit(self):
        self.assertTrue((ROOT / "README.md").read_text().startswith("# AgentKit"))
        result = subprocess.run(
            [sys.executable, "-m", "agentkit", "--help"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AgentKit engineering-agent controller", result.stdout)

    def test_stable_machine_interfaces_are_preserved(self):
        package = json.loads(
            (ROOT / "frontend/agentkit-terminal/package.json").read_text()
        )
        schema = json.loads((ROOT / "contracts/handoff.schema.json").read_text())
        self.assertEqual(package["name"], "agentkit-openharness-terminal-slice")
        self.assertEqual(schema["$id"], "urn:portable-agentkit:handoff:1")
        self.assertTrue((ROOT / "agentkit/__init__.py").is_file())


if __name__ == "__main__":
    unittest.main()
