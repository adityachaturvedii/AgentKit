import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentkit.projects import (InspectionLimits, ProjectIntakeError, ProjectRegistry,
                               RepositoryInspector, example_python_profile,
                               inspect_project, validate_project_profile)


ROOT = Path(__file__).resolve().parents[1]


class ProjectIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentkit-r1-test-")
        self.root = Path(self.tmp.name).resolve()
        self.addCleanup(self.tmp.cleanup)

    def git(self, repository, *arguments, check=True):
        env = dict(os.environ)
        env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
                   GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@localhost",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@localhost")
        return subprocess.run(["git", "-C", str(repository), *arguments], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=check, timeout=10)

    def repository(self, name="project", extra=None):
        repository = self.root / name
        repository.mkdir()
        self.git(repository, "init", "-b", "main")
        files = {
            "README.md": "# Fixture\n",
            "src/parser.py": "def parse(value):\n    return value.strip()\n",
            "src/formatter.py": "def format_value(value):\n    return str(value)\n",
            "tests/test_parser.py": "import unittest\n",
            ".gitignore": ".cache/\n",
        }
        files.update(extra or {})
        for relative, content in files.items():
            target = repository / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content)
        self.git(repository, "add", "--", *sorted(files))
        self.git(repository, "commit", "-m", "fixture")
        return repository

    @staticmethod
    def content_manifest(root):
        result = {}
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def test_clean_repository_inspection_is_read_only_bounded_and_filter_free(self):
        repository = self.repository()
        (repository / ".cache").mkdir()
        (repository / ".cache/ignored.txt").write_text("ignored")
        before = self.content_manifest(repository)
        report = inspect_project(repository)
        after = self.content_manifest(repository)
        self.assertEqual(before, after)
        self.assertEqual(report["readiness"]["status"], "ready")
        self.assertTrue(report["working_tree"]["clean"])
        self.assertEqual(report["working_tree"]["untracked"], [])
        self.assertEqual(report["working_tree"]["ignored_untracked"], [".cache/ignored.txt"])
        self.assertEqual(report["inventory"]["tracked_count"], 5)
        self.assertFalse(report["readiness"]["execution_supported"])
        self.assertFalse(report["inspection"]["hooks_executed"])
        self.assertFalse(report["inspection"]["filters_executed"])
        rendered = json.dumps(report["inspection"]["commands"])
        self.assertNotIn("status", rendered)
        self.assertNotIn("diff", rendered)
        self.assertNotIn("hash-object", rendered)

    def test_dirty_staged_modified_deleted_and_untracked_states_block(self):
        cases = {}
        modified = self.repository("modified")
        (modified / "src/parser.py").write_text("changed\n")
        cases["modified"] = modified
        staged = self.repository("staged")
        (staged / "src/parser.py").write_text("staged\n")
        self.git(staged, "add", "src/parser.py")
        cases["staged"] = staged
        deleted = self.repository("deleted")
        (deleted / "src/parser.py").unlink()
        cases["deleted"] = deleted
        untracked = self.repository("untracked")
        (untracked / "new.py").write_text("new\n")
        cases["untracked"] = untracked
        for expected, repository in cases.items():
            with self.subTest(expected=expected):
                report = inspect_project(repository)
                self.assertEqual(report["readiness"]["status"], "blocked")
                self.assertIn("dirty_worktree", report["readiness"]["blockers"])
                observed = report["working_tree"][expected]
                self.assertTrue(observed)

    def test_configured_filter_and_attributes_are_rejected_without_execution(self):
        repository = self.repository("filter", {".gitattributes": "*.txt filter=hostile\n"})
        sentinel = self.root / "filter-ran"
        script = self.root / "filter.sh"
        script.write_text("#!/bin/sh\ntouch '" + str(sentinel) + "'\ncat\n")
        script.chmod(0o700)
        hook = repository / ".git/hooks/post-checkout"
        hook.write_text("#!/bin/sh\ntouch '" + str(sentinel) + "'\n")
        hook.chmod(0o700)
        self.git(repository, "config", "filter.hostile.clean", str(script))
        self.git(repository, "config", "filter.hostile.smudge", str(script))
        report = inspect_project(repository)
        self.assertFalse(sentinel.exists())
        self.assertIn("git_filter_configuration", report["readiness"]["blockers"])
        self.assertIn("git_attribute_transform", report["readiness"]["blockers"])
        self.assertFalse(report["inspection"]["filters_executed"])

    def test_config_include_and_alternate_stop_before_git_queries(self):
        repository = self.repository("include")
        outside = self.root / "outside.config"
        outside.write_text("[user]\nname = outside\n")
        with (repository / ".git/config").open("a") as stream:
            stream.write("\n[include]\npath = " + str(outside) + "\n")
        report = inspect_project(repository)
        self.assertEqual(report["inspection"]["commands"], [])
        self.assertIsNone(report["inventory"])
        self.assertIn("git_config_include", report["readiness"]["blockers"])

        alternate = self.repository("alternate")
        target = alternate / ".git/objects/info/alternates"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(self.root / "objects") + "\n")
        report = inspect_project(alternate)
        self.assertEqual(report["inspection"]["commands"], [])
        self.assertIn("alternate_object_store", report["readiness"]["blockers"])

        symlinked = self.repository("metadata-symlink")
        exclude = symlinked / ".git/info/exclude"
        exclude.unlink()
        exclude.symlink_to(outside)
        report = inspect_project(symlinked)
        self.assertEqual(report["inspection"]["commands"], [])
        self.assertIn("symlinked_git_metadata", report["readiness"]["blockers"])

    def test_symlink_lfs_secret_and_bounds_are_reported_conservatively(self):
        repository = self.repository("features", {
            "model.pem": "fake fixture value\n",
            "large.bin": b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"0" * 64 + b"\nsize 99\n",
        })
        (repository / "linked").symlink_to("README.md")
        self.git(repository, "add", "linked")
        self.git(repository, "commit", "-m", "add link")
        report = inspect_project(repository)
        self.assertIn("tracked_symlink", report["readiness"]["blockers"])
        self.assertIn("git_lfs_pointer", report["readiness"]["blockers"])
        self.assertIn("secret_like_path:model.pem", report["readiness"]["warnings"])
        secret_repository = self.repository("secret-only", {"model.pem": "fixture\n"})
        with self.assertRaisesRegex(ProjectIntakeError, "explicitly exclude"):
            ProjectRegistry(self.root / "feature-state").enroll(
                secret_repository, example_python_profile())
        with self.assertRaisesRegex(ProjectIntakeError, "count exceeds"):
            RepositoryInspector(InspectionLimits(max_tracked_files=2)).inspect(repository)

    def test_profile_rejects_authority_expansion_and_invalid_recipes(self):
        profile = example_python_profile()
        documented = json.loads((ROOT / "docs/examples/python-library-profile.json").read_text())
        self.assertEqual(documented, profile)
        self.assertEqual(validate_project_profile(profile)["execution_enabled"], False)
        mutations = (
            ("network", "full"),
            ("execution_enabled", True),
            ("stack", "javascript"),
            ("execution_profile", "untrusted-host"),
        )
        for key, value in mutations:
            changed = json.loads(json.dumps(profile))
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ProjectIntakeError):
                validate_project_profile(changed)
        changed = json.loads(json.dumps(profile))
        changed["api_key"] = "synthetic-secret"
        with self.assertRaisesRegex(ProjectIntakeError, "fields"):
            validate_project_profile(changed)
        changed = json.loads(json.dumps(profile))
        changed["checks"][0]["argv"] = ["sh", "-c", "curl example.com"]
        with self.assertRaisesRegex(ProjectIntakeError, "python3"):
            validate_project_profile(changed)
        changed = json.loads(json.dumps(profile))
        changed["write_paths"] = ["../outside"]
        with self.assertRaisesRegex(ProjectIntakeError, "escapes"):
            validate_project_profile(changed)

    def test_enrollment_and_plans_are_hash_bound_and_stale_safe(self):
        repository = self.repository("enrolled")
        state = self.root / "controller-state"
        registry = ProjectRegistry(state)
        record = registry.enroll(repository, example_python_profile())
        self.assertFalse(record["execution_authorized"])
        self.assertEqual(record["capabilities"]["repository_execution"],
                         "unsupported_until_R2")
        parser_plan = registry.plan(record["project_id"], "Correct parser whitespace handling")
        formatter_plan = registry.plan(record["project_id"], "Correct formatter output")
        self.assertIn("src/parser.py", parser_plan["relevant_inventory"])
        self.assertIn("src/formatter.py", formatter_plan["relevant_inventory"])
        self.assertNotEqual(parser_plan["plan_sha256"], formatter_plan["plan_sha256"])
        self.assertEqual(parser_plan["status"], "planned_read_only")
        self.assertEqual(parser_plan["model_calls"], 0)
        self.assertIn("repository_execution_requires_R2", parser_plan["blockers"])

        (repository / "src/parser.py").write_text("changed after enrollment\n")
        stale = registry.plan(record["project_id"], "Correct parser whitespace handling")
        self.assertEqual(stale["status"], "blocked")
        self.assertIn("enrollment_stale", stale["blockers"])
        self.assertIn("dirty_worktree", stale["blockers"])

    def test_flat_python_shape_enrolls_with_its_own_bounded_profile(self):
        repository = self.repository("flat", {
            "package/core.py": "def normalize(value):\n    return value.strip()\n",
            "docs/usage.md": "# Usage\n",
        })
        profile = example_python_profile()
        profile["profile_id"] = "flat-python-library"
        profile["context_paths"] = ["README.md", "package", "tests"]
        profile["write_paths"] = ["package", "tests"]
        registry = ProjectRegistry(self.root / "flat-state")
        record = registry.enroll(repository, profile)
        plan = registry.plan(record["project_id"], "Improve core normalize behavior")
        self.assertEqual(plan["status"], "planned_read_only")
        self.assertIn("package/core.py", plan["relevant_inventory"])

    def test_registry_cannot_be_inside_project_and_records_detect_tampering(self):
        repository = self.repository("registry")
        with self.assertRaisesRegex(ProjectIntakeError, "outside"):
            ProjectRegistry(repository / ".agentkit").enroll(
                repository, example_python_profile())
        registry = ProjectRegistry(self.root / "state")
        record = registry.enroll(repository, example_python_profile())
        path = registry.projects / (record["project_id"] + ".json")
        value = json.loads(path.read_text())
        value["execution_authorized"] = True
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ProjectIntakeError, "integrity"):
            registry.load(record["project_id"])

    def test_cli_exposes_inspect_example_enroll_show_and_plan(self):
        repository = self.repository("cli")
        state = self.root / "cli-state"
        profile_path = self.root / "profile.json"
        profile_path.write_text(json.dumps(example_python_profile()))

        def cli(*arguments):
            return subprocess.run([sys.executable, "-m", "agentkit", *arguments], cwd=ROOT,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  timeout=15, check=False)

        inspected = cli("project", "inspect", str(repository))
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout)["readiness"]["status"], "ready")
        example = cli("project", "profile-example")
        self.assertEqual(example.returncode, 0, example.stderr)
        self.assertFalse(json.loads(example.stdout)["execution_enabled"])
        enrolled = cli("project", "enroll", str(repository), "--profile", str(profile_path),
                       "--state-root", str(state))
        self.assertEqual(enrolled.returncode, 0, enrolled.stderr)
        project_id = json.loads(enrolled.stdout)["project_id"]
        shown = cli("project", "show", "--state-root", str(state),
                    "--project-id", project_id)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        planned = cli("project", "plan", "--state-root", str(state),
                      "--project-id", project_id, "--request", "Fix parser whitespace")
        self.assertEqual(planned.returncode, 0, planned.stderr)
        self.assertEqual(json.loads(planned.stdout)["status"], "planned_read_only")


if __name__ == "__main__":
    unittest.main()
