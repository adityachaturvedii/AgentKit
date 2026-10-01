# R3 P13 distribution validation

Validation date: 2026-10-01. Executable base: `40e726b44025577b87029ecd6f2049beca7b6304`. This corrective distribution work was exercised from the dedicated `implementation/r3-distribution` worktree without provider inference, network installation or global configuration changes.

## Implemented and tested

- Source checkouts continue to resolve their adjacent catalogs, skills, domains, contracts, notices and terminal assets.
- An offline-built `agentkit-controller` wheel installs into a fresh virtual environment with `--no-index --no-deps` and exposes the `agentkit` console command.
- The installed command passes `--help`, `check`, `list`, `show` and offline portable-package verification outside the source checkout with an empty disposable home.
- The installed optional terminal renderer resolves its bundled files and passes with the already-installed Node runtime. AgentKit does not install Node or npm packages.
- The wheel retains the pinned source lock and required third-party notices. Historical `audit/evaluations` records and repository tests remain source-only and are excluded from the wheel and source distribution.
- Uninstall removes the isolated Python distribution and console entry point. Workflow roots, review exports and provider-managed credentials remain separate retained data.

## Results

| Check | Result |
|---|---|
| Full Python discovery suite | 266 run; 263 passed; 3 skipped |
| Focused final distribution, documentation, license and pack suite | 23 passed |
| Dependency-free Node terminal suite | 8 passed |
| `python3 -m agentkit check` | Passed; 10 skills, 7 domains, 10 examples and 3 pinned sources |
| Fresh wheel install and installed commands | Passed |
| Wheel/sdist content inspection | Passed; required resources present and historical evaluation archive absent |
| Fresh-environment uninstall probe | Passed |
| Python compilation and `git diff --check` | Passed |

The three skips are unchanged host-bound checks: two nested macOS Seatbelt checks cannot initialize inside the current managed execution context, and one loopback preview check cannot bind on this host. They were not retried without their required guard and do not validate a broader execution mode.

## License and release status

Third-party attribution and local adaptation hashes are checked offline. The engineering review recommends Apache-2.0 for original AgentKit work, but no root `LICENSE` has been selected or added. Private artifact testing is complete; a public open-source or package-index release is not complete. Signing, authenticated provenance, npm publication, a full-screen terminal UI and support beyond the tested macOS boundary remain future work.
