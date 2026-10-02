# Refinement batch 1 integration contracts

This file freezes the interfaces and file ownership agreed before parallel implementation. It is controller design, not additional worker authority.

## Baseline and integration order

- Baseline: `e763d6a53805b66cb3613beb08c8d5cb8b5f5197`, which contains planning commit `280a434a4297c9481e798bef5b0395c49e074eeb`.
- R4 `3dd45c67abb40a6aa82d362b58d729ce60e7d9e6` and R5 `9a05b635855b89df3115edaabd8db4fefd0b7555` diverge from `8d9cc31`; neither is merged here. Runtime work may document an R5 dependency without copying its product changes.
- Integration order: runtime readiness, typed failures, accounting/identity, specialist contracts, then integration-lead wiring and documentation.

## Shared records

All records reject unknown authority-bearing fields, preserve unknown observations as `null`, and carry `schema_version: 1`.

### Runtime readiness

`RuntimeRequirement` identifies a runtime name, capability profile, required executable, optional version evidence, and approved command prefixes. `RuntimeReadiness` records resolved path, executable hash, version, state (`verified`, `unavailable`, or `unknown`), and evidence. Readiness is measured in the actual prepared worker environment. It never installs software or expands tools.

### Failure reporting

`FailureRecord` separates the original cause from controller disposition. Required fields are task, stage, category, summary, retryability, evidence references, candidate revision, and occurrence identity. Optional recovery data names only a validated transition. Repair exhaustion is a disposition layered over the retained cause, never a replacement category.

### Usage and identity

Usage summaries separate provider executions from local checks. Each provider quantity records a reported subtotal, contributing and missing execution counts, and completeness. Estimated and billed costs remain distinct. CLI launches are not presented as internal provider requests or turns. `GitIdentity` comes only from trusted run configuration and is passed command-scoped to Git; model text and repository config cannot set it.

### Specialist and skill bindings

`SpecialistProfile` extends one existing base role through versioned activation, required capability references, output contract, eligible model profiles, default skill IDs, context policy, completion criteria, and escalation rules. It cannot contain executable commands, approval, budget, path, or publication grants. `SkillBinding` pins the selected role, bounded regular source path, version, SHA-256, provenance/license reference, selection reason, loaded-reference hashes, and encoded byte count. Dispatch rehashes content.

## Parallel file ownership

- REF-01 owns `agentkit/runtime_readiness.py`, focused adapter/runtime seam edits, and `tests/test_runtime_readiness.py`.
- REF-02 owns `agentkit/failure_reporting.py`, focused status/failure projection edits, and `tests/test_failure_reporting.py`.
- REF-03 owns `agentkit/usage_summary.py`, trusted identity changes in `agentkit/git_broker.py`, and `tests/test_accounting_identity.py`.
- REF-04 owns `agentkit/specialists.py`, compatible specialist additions in `agentkit/phase4_contracts.py`, and `tests/test_specialist_contracts.py`.
- The integration lead owns this file, shared documentation/checklist/decision updates, and any minimal final seam reconciliation. Workers do not edit shared documentation or each other's files.

If an assigned change would cross ownership, the worker reports the required seam and stops that edit. The integration lead decides the minimal wiring after reviewing all patches.
