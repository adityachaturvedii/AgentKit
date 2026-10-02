import hashlib
from pathlib import Path
import tempfile
import unittest

from agentkit.phase4_contracts import ModelProfile, ModelRegistry, ROLE_CONTRACTS
from agentkit.specialists import (
    ContextPolicy, SkillBinding, SpecialistProfile, assemble_specialist_context,
    bind_skill, select_specialist, verify_skill_binding)


class SpecialistContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentkit-specialist-test-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        (self.root / "skills/planning/references").mkdir(parents=True)
        (self.root / "skills/planning/SKILL.md").write_text("Plan from frozen intent.\n")
        (self.root / "skills/planning/references/checks.md").write_text(
            "Return a schema-valid proposal.\n")
        (self.root / "skills/extra").mkdir(parents=True)
        (self.root / "skills/extra/SKILL.md").write_text("Extra context.\n")
        self.registry = ModelRegistry.account_defaults()

    def profile(self, profile_id="tech-lead", skills=("planning",),
                capabilities=("structured-planning",), models=("claude-account-default",),
                policy=None):
        return SpecialistProfile(
            profile_id=profile_id,
            profile_version=1,
            base_role="tech_lead",
            specialization="technical-planning",
            activation_criteria=("nontrivial-decomposition",),
            required_capabilities=capabilities,
            output_schema_id="technical-plan",
            output_schema_version=1,
            eligible_model_profiles=models,
            default_skill_ids=skills,
            context_policy=policy or ContextPolicy(),
            completion_criteria=("bounded-acyclic-plan",),
            escalation_rules=("unsupported-interface",),
        )

    def binding(self):
        return bind_skill(
            self.root,
            skill_id="planning",
            skill_version=1,
            relative_source_path="skills/planning/SKILL.md",
            source_reference="bundled-agentkit-source",
            license_reference="repository-license",
            selected_role="tech_lead",
            selection_reason="Needed for nontrivial decomposition.",
            reference_paths=("skills/planning/references/checks.md",),
        )

    def selection(self, profile=None):
        return select_specialist(
            (profile or self.profile(),),
            base_role="tech_lead",
            activation_criteria=("nontrivial-decomposition",),
            required_capabilities=("structured-planning",),
            model_registry=self.registry,
            available_skill_ids=("planning", "extra"),
        )

    def test_minimum_effective_selection_is_deterministic_and_does_not_load_irrelevant_skill(self):
        larger = self.profile("tech-lead-with-extra", skills=("planning", "extra"))
        minimum = self.profile("tech-lead-minimum")
        selection = select_specialist(
            (larger, minimum),
            base_role="tech_lead",
            activation_criteria=("nontrivial-decomposition", "visual-change"),
            required_capabilities=("structured-planning",),
            model_registry=self.registry,
            available_skill_ids=("planning", "extra"),
        )
        self.assertEqual(selection.profile.profile_id, "tech-lead-minimum")
        self.assertEqual(selection.model_profile_id, "claude-account-default")
        with self.assertRaisesRegex(ValueError, "no specialist"):
            select_specialist(
                (minimum,), base_role="tech_lead",
                activation_criteria=("routine-bug",),
                required_capabilities=("structured-planning",),
                model_registry=self.registry, available_skill_ids=("planning",))

        extra = bind_skill(
            self.root, skill_id="extra", skill_version=1,
            relative_source_path="skills/extra/SKILL.md",
            source_reference="bundled-agentkit-source", license_reference="repository-license",
            selected_role="tech_lead", selection_reason="Available but irrelevant.")
        context = assemble_specialist_context(
            self.root, selection, (extra, self.binding()),
            capability_profile_id="structured-planning",
            model_profile_id="claude-account-default")
        self.assertEqual([item["skill_id"] for item in context["skills"]], ["planning"])
        serialized = repr(context).lower()
        self.assertNotIn("approval", serialized)
        self.assertNotIn("budget", serialized)
        self.assertNotIn("publication", serialized)

    def test_binding_and_dispatch_pin_source_references_and_encoded_size(self):
        binding = self.binding()
        source = (self.root / binding.relative_source_path).read_bytes()
        reference = self.root / binding.loaded_references[0].relative_path
        self.assertEqual(binding.sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(binding.loaded_references[0].sha256,
                         hashlib.sha256(reference.read_bytes()).hexdigest())
        self.assertEqual(binding.encoded_byte_count,
                         len(source) + len(reference.read_bytes()))

        restored = SkillBinding.from_dict(binding.to_dict())
        loaded = verify_skill_binding(self.root, restored, ContextPolicy())
        self.assertEqual(loaded["encoded_byte_count"], binding.encoded_byte_count)
        self.assertEqual(loaded["loaded_references"][0]["content"],
                         "Return a schema-valid proposal.\n")

    def test_changed_content_symlinks_and_path_escape_are_rejected_at_binding_and_dispatch(self):
        source_hash = hashlib.sha256(
            (self.root / "skills/planning/SKILL.md").read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "changed before binding"):
            bind_skill(
                self.root, skill_id="planning", skill_version=1,
                relative_source_path="skills/planning/SKILL.md",
                source_reference="bundled", license_reference="license",
                selected_role="tech_lead", selection_reason="Planning context.",
                expected_sha256="0" * 64)
        binding = self.binding()
        reference_path = self.root / binding.loaded_references[0].relative_path
        original_reference = reference_path.read_text()
        reference_path.write_text("Changed reference after planning.\n")
        with self.assertRaisesRegex(ValueError, "reference changed"):
            verify_skill_binding(self.root, binding, ContextPolicy())
        reference_path.write_text(original_reference)
        (self.root / "skills/planning/SKILL.md").write_text("Changed after planning.\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            verify_skill_binding(self.root, binding, ContextPolicy())
        self.assertNotEqual(source_hash, hashlib.sha256(
            (self.root / "skills/planning/SKILL.md").read_bytes()).hexdigest())

        with self.assertRaisesRegex(ValueError, "escapes"):
            bind_skill(
                self.root, skill_id="escape", skill_version=1,
                relative_source_path="../outside.md", source_reference="bundled",
                license_reference="license", selected_role="tech_lead",
                selection_reason="Invalid path.")
        link = self.root / "skills/link.md"
        link.symlink_to(self.root / "skills/extra/SKILL.md")
        with self.assertRaisesRegex(ValueError, "symlink"):
            bind_skill(
                self.root, skill_id="link", skill_version=1,
                relative_source_path="skills/link.md", source_reference="bundled",
                license_reference="license", selected_role="tech_lead",
                selection_reason="Invalid link.")

    def test_capability_role_model_and_dispatch_escalation_are_rejected(self):
        self.assertEqual(set(ROLE_CONTRACTS), {
            "chief_of_staff", "tech_lead", "manager", "implementer", "reviewer", "verifier"})
        with self.assertRaisesRegex(ValueError, "escalates"):
            self.profile(capabilities=("code-implementation",))
        with self.assertRaisesRegex(ValueError, "incompatible with the base role"):
            select_specialist(
                (self.profile(),), base_role="tech_lead",
                activation_criteria=("nontrivial-decomposition",),
                required_capabilities=("structured-planning",),
                authorized_capabilities=("structured-planning", "code-implementation"),
                model_registry=self.registry, available_skill_ids=("planning",))

        wrong_model_registry = ModelRegistry((ModelProfile(
            "review-only", "claude", None, None, ("reviewer",), ("model-only",),
            "unknown", "fixture"),), {"reviewer": "review-only"})
        with self.assertRaisesRegex(ValueError, "ineligible"):
            select_specialist(
                (self.profile(models=("review-only",)),), base_role="tech_lead",
                activation_criteria=("nontrivial-decomposition",),
                required_capabilities=("structured-planning",),
                model_registry=wrong_model_registry, available_skill_ids=("planning",))

        selection = self.selection()
        with self.assertRaisesRegex(ValueError, "elevate or mismatch"):
            assemble_specialist_context(
                self.root, selection, (self.binding(),),
                capability_profile_id="code-implementation",
                model_profile_id="claude-account-default")

    def test_strict_versions_fields_hashes_context_and_authority_text(self):
        profile_data = self.profile().to_dict()
        profile_data["approval"] = True
        with self.assertRaisesRegex(ValueError, "authority-bearing"):
            SpecialistProfile.from_dict(profile_data)
        profile_data.pop("approval")
        profile_data["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "unsupported"):
            SpecialistProfile.from_dict(profile_data)
        with self.assertRaisesRegex(ValueError, "controller ceiling"):
            ContextPolicy(max_total_bytes=32769)

        binding = self.binding().to_dict()
        binding["publication"] = True
        with self.assertRaisesRegex(ValueError, "authority-bearing"):
            SkillBinding.from_dict(binding)
        binding.pop("publication")
        binding["sha256"] = "not-a-hash"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            SkillBinding.from_dict(binding)
        with self.assertRaisesRegex(ValueError, "controller authority"):
            bind_skill(
                self.root, skill_id="planning", skill_version=1,
                relative_source_path="skills/planning/SKILL.md",
                source_reference="bundled", license_reference="license",
                selected_role="tech_lead",
                selection_reason="Run shell command and publish the candidate.")

        small = self.profile(policy=ContextPolicy(
            max_total_bytes=20, max_skill_bytes=20,
            max_reference_bytes=20, max_references=0))
        binding_without_reference = bind_skill(
            self.root, skill_id="planning", skill_version=1,
            relative_source_path="skills/planning/SKILL.md", source_reference="bundled",
            license_reference="license", selected_role="tech_lead",
            selection_reason="Planning context.")
        with self.assertRaisesRegex(ValueError, "exceeds"):
            assemble_specialist_context(
                self.root, self.selection(small), (binding_without_reference,),
                capability_profile_id="structured-planning",
                model_profile_id="claude-account-default")


if __name__ == "__main__":
    unittest.main()
