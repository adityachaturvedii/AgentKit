import hashlib
import ast
import json
from pathlib import Path
import re
import tarfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DistributionLicenseTests(unittest.TestCase):
    def test_locked_sources_have_exact_retained_notices(self):
        lock = json.loads((ROOT / "audit/sources.lock.json").read_text())
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertEqual(lock["schema_version"], 1)

        seen_notice_paths = set()
        for source in lock["sources"]:
            with self.subTest(source=source["id"]):
                notice_path = source["notice"]
                self.assertNotIn(notice_path, seen_notice_paths)
                seen_notice_paths.add(notice_path)
                notice = ROOT / notice_path
                self.assertTrue(notice.is_file())
                self.assertIn(notice_path, notices)
                self.assertIn(source["commit"], notices)

                license_files = [entry for entry in source["files"]
                                 if entry["disposition"] == "adopt-notice"]
                self.assertEqual(len(license_files), 1)
                locked_license = license_files[0]
                self.assertEqual(locked_license["path"], "LICENSE")
                self.assertEqual(notice.stat().st_size, locked_license["bytes"])
                self.assertEqual(sha256(notice), locked_license["sha256"])
                self.assertIn(b"MIT License", notice.read_bytes())

    def test_every_adapted_procedure_links_exact_source_and_notices(self):
        lock = json.loads((ROOT / "audit/sources.lock.json").read_text())
        for source in lock["sources"]:
            for candidate in source["candidates"]:
                if candidate["decision"] != "adapt":
                    continue
                target = ROOT / "skills" / candidate["target"] / "SKILL.md"
                with self.subTest(source=source["id"], candidate=candidate["path"]):
                    self.assertTrue(target.is_file())
                    content = target.read_text()
                    expected_url = (f'{source["repository"]}/blob/{source["commit"]}/'
                                    f'{candidate["path"]}')
                    self.assertIn(expected_url, content)
                    self.assertIn("../../THIRD_PARTY_NOTICES.md", content)

    def test_openharness_adaptations_and_license_are_hash_bound(self):
        mapping = json.loads(
            (ROOT / "agentkit/integrations/openharness/adaptation-map.json").read_text())
        upstream = mapping["upstream"]
        license_path = ROOT / "third_party/openharness/LICENSE"
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()

        self.assertEqual(upstream["license"], "MIT")
        self.assertEqual(sha256(license_path), upstream["license_sha256"])
        self.assertIn("Copyright (c) 2025 OpenHarness Contributors",
                      license_path.read_text())
        self.assertIn(upstream["revision"], notices)
        self.assertIn("third_party/openharness/LICENSE", notices)
        self.assertTrue(mapping["adaptations"])

        for adaptation in mapping["adaptations"]:
            with self.subTest(local=adaptation["local"], upstream=adaptation["upstream"]):
                local = ROOT / adaptation["local"]
                self.assertEqual(adaptation["decision"], "adapt")
                self.assertTrue(local.is_file())
                self.assertRegex(adaptation["upstream_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(sha256(local), adaptation["local_sha256"])
                self.assertTrue(adaptation["changes"])

    def test_terminal_slice_has_no_third_party_package_closure(self):
        frontend = ROOT / "frontend/agentkit-terminal"
        package = json.loads((frontend / "package.json").read_text())
        self.assertTrue(package["private"])
        self.assertNotIn("dependencies", package)
        self.assertNotIn("devDependencies", package)
        self.assertEqual(list(frontend.glob("*lock*")), [])

        import_pattern = re.compile(
            r'''(?:from\s+|import\s*\(\s*)["']([^"']+)["']''')
        for source in (frontend / "src").glob("*.mjs"):
            with self.subTest(source=source.name):
                specifiers = import_pattern.findall(source.read_text())
                self.assertTrue(all(item.startswith(("node:", "./", "../"))
                                    for item in specifiers), specifiers)

    def test_distribution_documents_keep_license_choice_explicit(self):
        review = (ROOT / "docs/r3-license-review.md").read_text()
        provenance = (ROOT / "docs/r3-provenance-manifest.md").read_text()
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertIn("Apache License 2.0", review)
        self.assertIn("maintainer must make the outbound-license decision", review)
        self.assertIn("not yet been selected", notices)
        for required in (
                "THIRD_PARTY_NOTICES.md",
                "notices/pstack-LICENSE.txt",
                "notices/matt-skills-LICENSE.txt",
                "notices/gstack-LICENSE.txt",
                "third_party/openharness/LICENSE",
                "audit/sources.lock.json",
                "agentkit/integrations/openharness/adaptation-map.json"):
            self.assertIn(required, review + provenance)

    def test_packaging_manifests_link_all_provenance_material(self):
        manifest = (ROOT / "MANIFEST.in").read_text().splitlines()
        self.assertIn("include THIRD_PARTY_NOTICES.md", manifest)
        self.assertIn("include audit/sources.lock.json", manifest)
        for directory in ("notices", "third_party"):
            self.assertIn(f"recursive-include {directory} *", manifest)
        self.assertIn("recursive-include agentkit *.py *.json", manifest)

        setup_tree = ast.parse((ROOT / "setup.py").read_text())
        assignments = {}
        for node in setup_tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    try:
                        assignments[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
        self.assertIn("THIRD_PARTY_NOTICES.md", assignments["RESOURCE_FILES"])
        self.assertIn("audit/sources.lock.json", assignments["RESOURCE_FILES"])
        for directory in ("notices", "third_party"):
            self.assertIn(directory, assignments["RESOURCE_DIRECTORIES"])

    def test_existing_build_artifacts_retain_provenance_material(self):
        required_suffixes = (
            "THIRD_PARTY_NOTICES.md",
            "notices/pstack-LICENSE.txt",
            "notices/matt-skills-LICENSE.txt",
            "notices/gstack-LICENSE.txt",
            "third_party/openharness/LICENSE",
            "audit/sources.lock.json",
            "agentkit/integrations/openharness/adaptation-map.json",
        )
        artifacts = sorted((ROOT / "dist").glob("*")) if (ROOT / "dist").is_dir() else []
        for artifact in artifacts:
            with self.subTest(artifact=artifact.name):
                if artifact.name.endswith(".tar.gz"):
                    with tarfile.open(artifact, "r:gz") as archive:
                        names = archive.getnames()
                        contents = {
                            required: archive.extractfile(matches[0]).read()
                            for required in required_suffixes
                            if len(matches := [name for name in names
                                               if name.endswith(required)]) == 1
                        }
                elif artifact.suffix == ".whl":
                    with zipfile.ZipFile(artifact) as archive:
                        names = archive.namelist()
                        contents = {
                            required: archive.read(matches[0])
                            for required in required_suffixes
                            if len(matches := [name for name in names
                                               if name.endswith(required)]) == 1
                        }
                else:
                    continue
                for required in required_suffixes:
                    matches = [name for name in names if name.endswith(required)]
                    self.assertEqual(len(matches), 1, required)
                    self.assertEqual(contents.get(required), (ROOT / required).read_bytes(),
                                     required)


if __name__ == "__main__":
    unittest.main()
