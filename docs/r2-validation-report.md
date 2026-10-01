# R2 validation report

Date: 2026-10-01. Scope: offline safe-repository delivery against controller-created disposable Python repositories. No personal repository, provider inference, authentication flow, network dependency, package installation or publication was used.

## Implemented and independently exercised

- Independent reconstruction from a current R1 enrollment, with verified bytes, Git blob IDs, sizes, regular-file modes, spaces and Unicode names.
- No remotes, alternate object store, inherited Git templates or hard-linked working files; original repository identity/content remains unchanged.
- Separate controller execution authorization; an R1 profile remains non-executing.
- Prepared Python/check resolution with installation and network disabled; missing third-party dependencies block as `environment_required`.
- Request grounding in bounded enrolled content, with clarification for unmatched and contradictory requests.
- Structured implementation and review handoffs without expected patches or protected acceptance source.
- Existing-test and protected-acceptance execution, nonempty collection checks, candidate/protected-input immutability checks and exact-revision evidence.
- A deterministic implementation → commit → verification → independent review → local package workflow using the durable controller and Git broker.
- Scope rejection for unauthorized paths and unsupported file additions, deletions, renames and mode changes.
- Existing dependency snapshot, atomic claim, cancellation, authentication-history and resume regressions remain passing.

## Evidence classes

| Capability | Evidence |
|---|---|
| Import and original-source preservation | Offline behavioral fixtures |
| Prepared environment and missing-dependency block | Offline behavioral fixtures |
| Defect, empty collection, mutation and stale-candidate rejection | Offline behavioral fixtures |
| Complete revision-bound local package | Deterministic adapters plus real local unittest processes; provider roles simulated |
| macOS source/controller/home/fake-secret denial | Host-only Seatbelt behavioral check; skipped when an outer sandbox prevents nested `sandbox_apply` |
| Live Codex/Claude repository implementation and review | Unverified; no inference authorized or used |
| General repository compatibility | Unsupported; only clean standalone Python-library fixtures |

The deterministic verifier is not security evidence. Only the host Seatbelt case exercises the filesystem/network boundary. Even that case does not establish hostile-code support, universal credential isolation, detached-process containment or protection for every tool path.

## Retain, adapt, drop assessment at the R2 gate

- **Retain:** R1 enrollment, `ControllerStore`, `GitBroker` ownership, authentication history, resource accounting, revision-bound evidence and local approval semantics.
- **Adapt:** the broker now accepts verified byte/mode snapshots, preserves executable modes during export and rejects worker mode changes; verification accepts enrolled check recipes and protected acceptance instead of the calculator-only test.
- **Drop:** cloning or linking an enrolled repository, running dependency installers, inheriting repository Git configuration, silently omitting excluded tracked files, and treating worker tests or summaries as acceptance.

## Remaining gate

R2 is ready as a deterministic integration slice and host-verifier boundary for disposable fixtures. Before an operator uses it on an existing repository, AgentKit still needs the R3 terminal/package workflow and an explicitly authorized live provider validation against a nominated non-personal test repository. Applying changes to an original checkout remains outside this milestone.

## Corrective follow-up

The post-R2 review found five reproducible gaps. The corrective branch now rejects candidate changes made during review, enforces cross-provider profiles, adapts the existing live implementer/reviewer call contracts, creates authentication checkpoints at either provider stage, moves native verification snapshots outside the denied home tree, and asks the selected Python interpreter whether extension modules such as `math` are available. These behaviors have offline regressions; no provider inference was used.

The follow-up adds a durable reopen/resume driver. It stores the request, protected acceptance and import identity under private controller state, validates their hash and the controller's actual Git candidate checks after verified subscription login, and resumes only implementation or review. Reviewer recovery preserves the single passed verification record; implementation recovery continues through verification and review. Failed provider calls remain in usage and call accounting, with a five-call ceiling that accommodates one authentication failure at each provider without creating an unbounded retry path.

This recovery is fixture-tested with the real adapter/request construction and external transports stubbed. Interactive login and live repository inference remain unverified and require separate authorization.

The resume milestone passed the complete 226-test suite with the same 3 managed-environment skips, plus a focused sequential-authentication regression added afterward. That regression exercised Codex implementation authentication and Claude review authentication across two reopen cycles, retained one verification record and two checkpoint-history entries, and finished in exactly five controller-counted executions. Structural checks, Python 3.9 compilation and diff hygiene passed; no live login or inference was used.

Corrective validation used no inference: the complete suite passed 222 tests with 3 managed-environment skips before the final private-temporary-root hardening; the focused repository suite and Phase 3 broker/verifier regressions then passed 42 tests with 2 nested-Seatbelt skips. Structural checks, Python 3.9 compilation and diff hygiene passed. The new native-verifier placement test uses a controlled process runner and establishes path construction, not a live Seatbelt pass.

## Validation results

| Check | Result |
|---|---|
| `python3 -m unittest tests.test_repository_delivery -v` | 11 total: 10 passed, 1 expected nested-Seatbelt skip |
| `python3 -m unittest discover -s tests -v` | 215 total: 212 passed, 3 expected managed-environment skips |
| Separate host checks | 3 passed: Phase 3 verifier, loopback preview lifecycle and R2 repository verifier boundary |
| `python3 -m agentkit check` | Passed: 10 skills, 7 domains, 10 examples, 3 sources |
| Terminal `npm test` | 4 passed |
| Python 3.9 compilation and `git diff --check` | Passed |

The complete-suite skips are environment-specific, not silently promoted passes. All three exact cases passed when run outside the managed outer sandbox; the R2 native verifier was rerun after the final mode-integrity change. No live inference was performed.
