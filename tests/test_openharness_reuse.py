import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

from agentkit.integrations.openharness.backend import ReuseBackend, run_deterministic_demo
from agentkit.integrations.openharness.context import discover_context, render_context
from agentkit.integrations.openharness.fs import atomic_private_write
from agentkit.integrations.openharness.profiles import (PublicProviderProfile, parse_profile,
                                                        resolve_profile)
from agentkit.integrations.openharness.protocol import (BackendEvent, FrontendRequest,
                                                        event_stream, safe_ui_state)


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_REVISION = "9b2efd795c6aa09f88b0c257d269a9e518da6ae7"


class OpenHarnessReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentkit-r0-test-")
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def test_profile_resolution_is_hash_bound_and_cannot_add_authority(self):
        base = PublicProviderProfile("codex-code", "codex", capability_profile="code-implementation")
        resolved = resolve_profile(base, role_policy={"model": "role-model"},
                                   task_override={"model": "task-model"},
                                   expected_sha256=base.sha256)
        self.assertEqual(resolved["profile"]["model"], "task-model")
        self.assertEqual(resolved["provenance"]["model"], "task-override")
        with self.assertRaisesRegex(ValueError, "changed"):
            resolve_profile(PublicProviderProfile("codex-code", "codex", model="changed",
                                                  capability_profile="code-implementation"),
                            expected_sha256=base.sha256)
        for field in ("api_key", "auth_source", "base_url", "max_tokens", "tools"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "authority-bearing"):
                parse_profile({"profile_id": "bad", "provider": "codex", field: "value"})
        with self.assertRaisesRegex(ValueError, "only model and effort"):
            resolve_profile(base, task_override={"provider": "claude"})

    def test_context_discovery_stops_at_root_hashes_sources_and_marks_advisory(self):
        outside = self.root / "outside"
        project = self.root / "project"
        nested = project / "src" / "feature"
        nested.mkdir(parents=True)
        outside.mkdir()
        (self.root / "AGENTS.md").write_text("must stay outside\n")
        (project / "AGENTS.md").write_text("project guidance\n")
        (nested / "CLAUDE.md").write_text("feature guidance\n")
        sources = discover_context(project, nested)
        self.assertEqual([item.relative_path for item in sources],
                         ["AGENTS.md", "src/feature/CLAUDE.md"])
        self.assertTrue(all(item.advisory for item in sources))
        self.assertNotIn("must stay outside", render_context(sources))
        self.assertEqual(sources[0].sha256,
                         hashlib.sha256((project / "AGENTS.md").read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, "inside"):
            discover_context(project, outside)

    def test_context_rejects_symlinks_invalid_encoding_and_bounds(self):
        project = self.root / "project"
        project.mkdir()
        outside = self.root / "outside.md"
        outside.write_text("outside")
        (project / "AGENTS.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            discover_context(project)
        (project / "AGENTS.md").unlink()
        (project / "AGENTS.md").write_bytes(b"\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            discover_context(project)
        (project / "AGENTS.md").write_text("x" * 300)
        with self.assertRaisesRegex(ValueError, "total bound"):
            discover_context(project, max_chars_per_file=256, max_total_chars=256)

    def test_protocol_rejects_unbounded_unknown_or_approval_commands(self):
        request = FrontendRequest.parse('{"version":1,"type":"snapshot","task_id":"demo"}')
        self.assertEqual(request.type, "snapshot")
        for value in (
                '{"version":1,"type":"approval_response","task_id":"demo"}',
                '{"version":1,"type":"snapshot","task_id":"demo","permission":true}',
                "x" * 65537):
            with self.subTest(value=value[:30]), self.assertRaises((ValueError, json.JSONDecodeError)):
                FrontendRequest.parse(value)
        with self.assertRaisesRegex(ValueError, "unsupported"):
            BackendEvent("approval_granted")

    def test_display_preserves_unknown_usage_and_lifecycle_warnings(self):
        state = safe_ui_state({
            "state": "authentication_required",
            "budget": {"token_usage": {"input_tokens": None, "output_tokens": None}},
            "assignments": {"ready": [], "active": [], "waiting": [1], "completed": [1]},
            "candidate_stale": True,
        })
        self.assertFalse(state["usage_known"])
        self.assertTrue(state["authentication_required"])
        self.assertTrue(state["candidate_stale"])
        self.assertFalse(state["approval_recorded"])

    def test_atomic_write_is_private_and_rejects_symlink_target(self):
        target = self.root / "state" / "record.json"
        atomic_private_write(target, "one")
        atomic_private_write(target, "two")
        self.assertEqual(target.read_text(), "two")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        link = self.root / "link"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            atomic_private_write(link, "no")

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the adapted terminal slice")
    def test_actual_adapted_renderer_handles_events(self):
        stream = self.root / "events.jsonl"
        stream.write_text(event_stream((BackendEvent("state_snapshot", state={
            "stage": "cancelled", "cancelled": True, "ready": 0, "active": 0,
            "waiting": 0, "completed": 0, "usage_known": False,
        }),)))
        result = subprocess.run(
            [shutil.which("node"), str(ROOT / "frontend/agentkit-terminal/src/render-events.mjs"),
             str(stream)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        output = result.stdout.decode()
        self.assertIn("CANCELLED", output)
        self.assertIn("usage: unknown", output)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the adapted terminal slice")
    def test_vertical_demo_uses_real_controller_and_produces_unapproved_package(self):
        result = run_deterministic_demo(self.root / "demo")
        self.assertEqual(result["metadata"]["final_state"], "awaiting_pr_approval")
        self.assertFalse(result["metadata"]["provider_inference"])
        self.assertFalse(result["metadata"]["approval_recorded"])
        self.assertIn("stage: awaiting_pr_approval", result["terminal"])
        self.assertIn("approval recorded: no", result["terminal"])
        package = json.loads((self.root / "demo/workflow/approval/approval-package.json").read_text())
        self.assertFalse(package["approval"]["recorded"])
        self.assertEqual(package["head_revision"], result["metadata"]["final_state"]
                         and package["approval"]["bound_head"])

    def test_backend_does_not_replay_or_duplicate_deterministic_execution(self):
        backend = ReuseBackend(self.root / "workflow", "demo")
        events = backend.handle(FrontendRequest("run_demo"))
        self.assertEqual(events[-1].type, "package_ready")
        first_revision = events[-1].package["head_revision"]
        snapshot = backend.handle(FrontendRequest("snapshot", "demo"))
        self.assertEqual(snapshot[0].task.head_revision, first_revision)
        with self.assertRaisesRegex(ValueError, "only once"):
            backend.handle(FrontendRequest("run_demo"))
        with self.assertRaisesRegex(ValueError, "active"):
            backend.handle(FrontendRequest("snapshot", "other"))

    def test_adaptation_map_is_pinned_and_local_targets_exist(self):
        mapping = json.loads((ROOT / "agentkit/integrations/openharness/adaptation-map.json").read_text())
        self.assertEqual(mapping["upstream"]["revision"], UPSTREAM_REVISION)
        self.assertGreaterEqual(len(mapping["adaptations"]), 8)
        for item in mapping["adaptations"]:
            local = ROOT / item["local"]
            self.assertTrue(local.is_file(), item["local"])
            self.assertEqual(hashlib.sha256(local.read_bytes()).hexdigest(), item["local_sha256"])
            self.assertRegex(item["upstream_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
