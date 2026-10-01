# AgentKit reuse-first product plan

Planning review: 2026-10-01. Status: R0 reuse spike, R1 read-only intake, the R2 disposable-fixture delivery slice, R3 P11 portable-package verifier, P12 one-shot terminal workflow and P13 source-checkout/wheel compatibility and data-flow documentation are implemented. P13 public distribution remains incomplete until an outbound license exists; later capabilities are not authorization for paid inference or publication.

The user has selected **both existing-repository engineering and new-product creation, with existing repositories first**, for **small engineering teams and some public open-source users**. Substantial reuse of OpenHarness is an explicit engineering preference. We will compare and adapt working code before writing replacements.

Read in this order:

1. [Product direction](product-direction.md): users, promise, release scope and outcomes.
2. [OpenHarness reuse assessment](openharness-reuse.md): pinned source findings, concrete reuse packages, architecture options and adoption gates.
3. [Engineering plan](engineering-plan.md): contracts, workflow, repository boundary, milestones, tests, migration and implementation tickets.
4. [Decision register](decisions.md): agreed constraints, recommendations, assumptions and consequential decisions still open.
5. [Source inventory](openharness-source-inventory.json): exact upstream revision, file hashes and static import inventory. This is not an approved runtime dependency list.
6. [Planning validation](validation.md): checks performed for this documentation change and checks deliberately not claimed.

## Baselines and evidence

- AgentKit planning base: `ddf6145002efd0bd59b85d54996263f6edb7f675`, containing the resource-policy correction and preserved authentication/dependency/claim fixes.
- Planning branch: `planning/reuse-first-product`; worktree: `/Users/aditya/agentic/portable-agentkit-reuse-plan`.
- OpenHarness source pin: `9b2efd795c6aa09f88b0c257d269a9e518da6ae7`, resolved from the public repository and fetched into a disposable source-only Git checkout. No upstream code, installer, tests or plugins were executed.
- The supplied product vision is preserved outside the repository. Its filename and SHA-256 are recorded in the source inventory; this proposal supersedes neither its original text nor historical evidence.
- Existing final regression report: 182 tests, two expected managed-environment skips, structural check passed. This is historical evidence from the prior corrective task, not a new test run.
- Last integration trial: exact executable `a0f2906`, two successful Codex planning launches and two Claude authentication failures; implementation/review comparison incomplete. The later `1c0008c` normalization correction has offline evidence only. See [validation report](../phase4-validation-report.md).
- Existing runtime scope remains trusted controller-created disposable macOS execution. Any real-repository, API, container or Linux path below is planned and must pass its own release gate.

## Recommended decision

Proceed with a substantial, attributed OpenHarness component port around the existing AgentKit delivery core. First prove a working vertical integration of the reused terminal, profile configuration and context-discovery components. Do not rebuild those subsystems independently while the reuse spike is pending. Do not replace the durable controller merely to make an upstream runtime easier to import.

The first external-use milestone is one real task against an explicitly enrolled repository, executed from an independent managed copy, returning a portable review package. The repository's original checkout stays untouched. New-product work follows through the same delivery contracts, rather than a second orchestrator.

All command examples in the engineering plan are **proposed interface specifications**. Existing executable commands remain documented in the [current CLI guide](../phase4-cli-guide.md).

## R0 outcome

R0 accepted the recommended component-port architecture. Actual profile, context, protocol, atomic-write and terminal presentation behavior was adapted around the unchanged controller, and a deterministic workflow reached an unapproved local package through the new seam. The adopted runtime adds no Python or Node package dependency. See the [R0 validation report](../r0-validation-report.md) and [dependency/license audit](../r0-dependency-license-audit.md).

The executable terminal is deliberately a dependency-free one-shot renderer. The complete React/Ink TUI remains optional pending its 80-entry locked dependency/license/build audit.

## R3 terminal outcome

P12 adds one allowlisted frontend for existing Phase 4 disposable workflows with equivalent plain, JSON, protocol-event and one-shot terminal output. It reads status without relaunching work and supports start, authentication resume, cancellation and bounded package summary. Live start/resume authority comes only from explicit CLI construction flags. This is not a full-screen interactive TUI; public distribution licensing and any optional frontend package remain open P13 gates. See the [terminal workflow guide](../r3-terminal-workflow.md).

## R3 distribution documentation outcome

P13 now records exact source-checkout and isolated no-index wheel procedures, removal steps, tested Python/Node/macOS boundaries, provider data flow, authentication separation, retained local data and portable-export limits. It adds no runtime dependency, global configuration change, network installation or inference. The absence of an outbound `LICENSE` keeps public distribution incomplete; npm publication and a full-screen frontend remain excluded. See the [distribution guide](../r3-distribution.md), [compatibility matrix](../r3-compatibility.md) and [data-flow contract](../r3-data-flow.md).

## R4 pilot-protocol outcome

P14 provides offline bookkeeping for a precommitted exploratory comparison between direct provider-CLI work and AgentKit. It freezes matched conditions and deterministic assignments before collection, keeps unsuccessful and missing work in the denominator, preserves unknown effort/usage/cost values, and emits neutral descriptive summaries. It grants no repository, provider, approval or publication authority. Real participant and repository collection remains pending. See the [pilot protocol](../r4-pilot-protocol.md).

## R1 outcome

R1 implements P05 for controller-created disposable repository fixtures: bounded read-only inspection, strict Python-library profile validation, private hash-bound enrollment and revision-bound non-executing plans. The inspector runs no project code, hooks, filters, dependency installation, provider calls or network operations. It fails closed on repository shapes that could escape or transform the observed content. No personal or third-party repository was accessed, so applicability beyond the tested shapes remains unverified.

R1 does not authorize implementation against an enrolled repository.

## R2 outcome

R2 implements P06–P10 as an offline, deterministic integration slice for clean disposable Python-library repositories. It reconstructs current enrolled content without shared Git storage, validates a prepared environment without installation, generalizes protected verification, grounds narrow requests in enrolled content, reuses the durable controller/broker, and produces an exact-revision unapproved package. Repository execution requires a separate controller authorization; live providers and personal repositories were not used. See the [delivery contract](../r2-repository-delivery.md) and [validation report](../r2-validation-report.md).
