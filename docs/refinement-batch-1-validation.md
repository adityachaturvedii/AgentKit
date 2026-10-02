# Refinement batch 1 validation

This report covers the first implementation batch from the product-refinement plan. Results below are tied to the exact revisions named here. Historical R4/R5 evidence is not promoted to validation of this candidate.

## Baseline and ancestry

- Refreshed integration baseline: `e763d6a53805b66cb3613beb08c8d5cb8b5f5197` (`origin/implementation/phase-2`).
- Refreshed release baseline: `090e77bb1a48921408c10ec5390eb9b953a1adee` (`origin/main`).
- Planning commit `280a434a4297c9481e798bef5b0395c49e074eeb` is an ancestor of integration through merge commit `e763d6a`.
- R5 live-product branch `9a05b635855b89df3115edaabd8db4fefd0b7555` and R4 pilot branch `3dd45c67abb40a6aa82d362b58d729ce60e7d9e6` both diverge from common ancestor `8d9cc311df47355ce64e588b8cb8de60a4ae25ae`. Neither is an ancestor or descendant of current integration. They were inspected, not merged or copied wholesale.
- The integration candidate is assembled only on `implementation/refinement-batch-1`; shared integration and release branches remain unchanged.

## Pre-change baseline

`python3 -m unittest discover -s tests -v` passed 266 tests in 255.598 seconds. Three host-dependent checks skipped because nested Seatbelt initialization or loopback preview was unavailable in this execution environment. No live provider inference ran.

## Implemented and tested

### REF-01 runtime readiness

- Added versioned runtime requirement/readiness records and a prepared worker `PATH` derived from the selected capability profile.
- Python and Node are resolved, hashed and version-probed through the same workspace environment and outer guard used for provider dispatch. Missing, changed or unprobeable runtimes block before inference; no installer or fallback is attempted.
- The real owned-code adapter/request boundary is exercised with only external provider transport stubbed. The result retains the readiness record.
- R5 prerequisite: once its product path is reconciled, the recorded Node path/version/hash must be supplied through `runtime_requirement`. This batch does not import R5 product code.

### REF-02 failure and recovery reporting

- Added immutable `FailureRecord`, `EvidenceReference` and `RecoveryAction` contracts.
- Phase 4 status exposes original category/summary and a redacted diagnostic tail separately from `repair_exhausted`, repeated-failure or prerequisite disposition.
- Recovery is actionable only for the existing ready authentication checkpoint under controller authority. Waiting, uncertain and unsupported failures remain blocked; there is no generic unblock.
- Projection reads durable evidence/events without changing history, evidence identity, repair counts or budgets.

### REF-03 accounting and identity

- Provider-reported token and cost quantities now retain reported subtotals, contributing/missing execution counts and `complete`, `partial` or `unknown` metadata. Local checks are counted separately.
- CLI launch counts remain separate from unknown provider-internal requests/turns. Estimated and billed costs stay distinct.
- Phase 4 status exposes the complete usage report while retaining the conservative legacy token total as unknown for any incomplete category.
- `GitBroker` accepts a validated trusted per-run `GitIdentity` and supplies author/committer only through the child Git environment. Hostile repository/global identity cannot override it. The existing controller identity remains the compatibility default until a caller supplies trusted run configuration.

### REF-04 specialist contracts

- Added strict versioned specialist, context-policy, skill-reference, skill-binding and selection contracts over existing roles, model registry and capability profiles.
- Selection is deterministic and minimum-effective. Binding and dispatch reject path escape, symlinks, changed hashes, excessive context, role/model/capability mismatch and authority-bearing fields.
- Detailed authoring/forward-test plans exist for `product-shaping`, `interaction-design`, `visual-design` and `acceptance-design`. They are not catalog entries or executable skills yet.

### Integrated validation

- Combined focused suite: 129 tests passed across runtime readiness, adapters/resource policy, failure projection, usage/identity, specialist contracts, Phase 4/dynamic scheduling and authentication recovery.
- Final full repository suite: 288 tests ran in 260.817 seconds: 285 passed and three host-dependent checks skipped. This includes a real deterministic Phase 4 workflow that reports a partial provider subtotal while keeping the legacy aggregate unknown.
- Dependency-free terminal: 8 Node tests passed.
- `python3 -m agentkit check`: passed with 10 existing skills, 7 domains, 10 examples and 3 sources. The specialist plans did not alter the catalog.
- `git diff --check`: passed before final documentation/commit; repeated in final hygiene.

## Simulated and host-only scope

Provider transport remains stubbed for this batch. Disposable processes and repositories exercise controller, adapter, runtime, failure, usage, identity and specialist-contract seams without model inference. macOS Seatbelt enforcement is reported only when the native probe succeeds; a skip or unavailable probe does not become positive isolation evidence.

The three skipped full-suite checks were the Phase 3 native verifier boundary, the repository-delivery native verifier boundary and loopback preview lifecycle. Nested Seatbelt initialization and loopback binding were unavailable in this execution environment. Existing host evidence remains historical and is not relabeled as validation of this revision.

## Boundaries and remaining prerequisites

- No global Git or CLI configuration, credentials, plugins, paid API path, personal repository, GPU, publication or deployment is used.
- R5 product execution remains separate. Any runtime-readiness dependency on its product path must be integrated through a later reviewed reconciliation, not inferred from this batch.
- R4 pilot collection remains unimplemented; its synthetic protocol branch is not included here.
- Specialist selection/bindings are contract-tested but not yet persisted in Phase 4 graph state or assembled into provider dispatch. Existing role-specific skill context remains unchanged.
- Typed failures appear in Phase 4/Product JSON status. Repository-delivery status and the one-shot terminal still present their existing blocker text until a later protocol-compatible projection is added.
- No live inference, provider authentication action, network-dependent package operation or new host sandbox claim occurred.

## Worker provenance

| Ticket | Branch / worktree | Worker commit |
|---|---|---|
| REF-01 | `fix/ref01-runtime-readiness` / `/Users/aditya/agentic/agentkit-ref01-runtime` | `014850b32d422f63bf46190e661997d13f6d7d91` |
| REF-02 | `fix/ref02-failure-reporting` / `/Users/aditya/agentic/agentkit-ref02-failures` | `6258060999dfd6ecada72f8bb7b2fec2db6d88aa` |
| REF-03 | `fix/ref03-accounting-identity` / `/Users/aditya/agentic/agentkit-ref03-accounting` | `0a509d5cd33ede96699ce552345508ad74a33b1d` |
| REF-04 | `implementation/ref04-specialist-contracts` / `/Users/aditya/agentic/agentkit-ref04-specialists` | `77adbc0de5640cc2d219941c9d5c3a90c8cc2236` |

The integration lead reviewed and merged these commits into the isolated candidate in the agreed order. Workers did not merge or cherry-pick one another's changes.
