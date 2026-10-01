# R1 validation report

Date: 2026-10-01. Executable base: `cac3f113fda373b28a94b2a923b9ddcdce8c6bfb`. Scope: offline read-only project intake using controller-created disposable Git fixtures only.

## Implemented and tested

- Bounded standalone-repository identity, branch, base revision, raw tracked-file inventory and clean-state inspection.
- Pre-Git rejection of config includes, alternates, shared or symlinked Git metadata and metadata-count overflow.
- No-hook/no-filter metadata query construction and raw SHA-1 blob comparison without `git status`.
- Conservative detection of staged, modified, deleted and visible untracked files, symlinks, submodules, LFS pointers, filter/attribute transforms, binary files and secret-like paths.
- Strict Python-library profile schema with no network, installation or execution authorization.
- Private atomic enrollment records bound to project identity, revision, inventory and profile hashes outside the project.
- Revision revalidation, stale-enrollment blocking and request-sensitive read-only plans across `src` and flat package shapes.
- CLI operations for inspection, example profile generation, enrollment, record display and planning.

The focused suite uses only disposable repositories. It plants executable hooks and filters and verifies they are not invoked. It also verifies that config includes and alternate object stores stop before any Git query, registry tampering fails integrity validation, profile authority expansion is rejected, and different requests select different bounded inventory context.

## Capability status

| Capability | Status |
|---|---|
| Read-only inspection of the supported standalone fixture shape | Implemented and fixture-tested |
| Hash-bound profile enrollment outside the project | Implemented and fixture-tested |
| Non-executing revision-bound plan | Implemented and fixture-tested |
| Real personal or third-party repository onboarding | Unverified; deliberately not accessed in R1 development |
| Repository import, project checks or worker execution | Unsupported until R2 |
| Completeness of secret detection | Unsupported claim; filename screening only |
| Linux, containers, linked worktrees, submodules, LFS and transformed worktrees | Unsupported |

No provider inference, authentication access, network dependency, plugin installation, global configuration change, project command or paid API usage was used. The final complete regression result and exact executable revision are recorded after the implementation commit.
