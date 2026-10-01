"""Build configuration that bundles checkout resources inside installed wheels."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


ROOT = Path(__file__).resolve().parent
RESOURCE_FILES = (
    "catalog.json",
    "THIRD_PARTY_NOTICES.md",
    "audit/sources.lock.json",
)
RESOURCE_DIRECTORIES = ("contracts", "domains", "notices", "skills", "third_party")
RESOURCE_DOCS = (
    "docs/authentication-recovery.md",
    "docs/r3-compatibility.md",
    "docs/r3-data-flow.md",
    "docs/r3-distribution.md",
    "docs/r3-license-review.md",
    "docs/r3-portable-package.md",
    "docs/r3-provenance-manifest.md",
    "docs/r3-terminal-workflow.md",
    "docs/skill-contract.md",
)
FRONTEND_FILES = (
    "frontend/agentkit-terminal/package.json",
    "frontend/agentkit-terminal/src/render-events.mjs",
    "frontend/agentkit-terminal/src/renderer.mjs",
    "frontend/agentkit-terminal/src/request-demo.mjs",
)


class build_py(_build_py):
    def run(self):
        super().run()
        destination = Path(self.build_lib) / "agentkit" / "_resources"
        destination.mkdir(parents=True, exist_ok=True)
        for relative in RESOURCE_FILES:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        for relative in RESOURCE_DIRECTORIES:
            shutil.copytree(ROOT / relative, destination / relative, dirs_exist_ok=True)
        for relative in RESOURCE_DOCS + FRONTEND_FILES:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)


setup(cmdclass={"build_py": build_py})
