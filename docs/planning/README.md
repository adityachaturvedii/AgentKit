# Agentkit reuse-first product plan

Planning review: 2026-10-01. Status: proposed engineering plan, not implementation authorization for new execution profiles, paid inference or publication.

The user has selected **both existing-repository engineering and new-product creation, with existing repositories first**, for **small engineering teams and some public open-source users**. Substantial reuse of OpenHarness is an explicit engineering preference. We will compare and adapt working code before writing replacements.

Read in this order:

1. [Product direction](product-direction.md): users, promise, release scope and outcomes.
2. [OpenHarness reuse assessment](openharness-reuse.md): pinned source findings, concrete reuse packages, architecture options and adoption gates.
3. [Engineering plan](engineering-plan.md): contracts, workflow, repository boundary, milestones, tests, migration and implementation tickets.
4. [Decision register](decisions.md): agreed constraints, recommendations, assumptions and consequential decisions still open.
5. [Source inventory](openharness-source-inventory.json): exact upstream revision, file hashes and static import inventory. This is not an approved runtime dependency list.
6. [Planning validation](validation.md): checks performed for this documentation change and checks deliberately not claimed.

## Baselines and evidence

- Agentkit planning base: `ddf6145002efd0bd59b85d54996263f6edb7f675`, containing the resource-policy correction and preserved authentication/dependency/claim fixes.
- Planning branch: `planning/reuse-first-product`; worktree: `/Users/aditya/agentic/portable-agentkit-reuse-plan`.
- OpenHarness source pin: `9b2efd795c6aa09f88b0c257d269a9e518da6ae7`, resolved from the public repository and fetched into a disposable source-only Git checkout. No upstream code, installer, tests or plugins were executed.
- The supplied product vision is preserved outside the repository. Its filename and SHA-256 are recorded in the source inventory; this proposal supersedes neither its original text nor historical evidence.
- Existing final regression report: 182 tests, two expected managed-environment skips, structural check passed. This is historical evidence from the prior corrective task, not a new test run.
- Last integration trial: exact executable `a0f2906`, two successful Codex planning launches and two Claude authentication failures; implementation/review comparison incomplete. The later `1c0008c` normalization correction has offline evidence only. See [validation report](../phase4-validation-report.md).
- Existing runtime scope remains trusted controller-created disposable macOS execution. Any real-repository, API, container or Linux path below is planned and must pass its own release gate.

## Recommended decision

Proceed with a substantial, attributed OpenHarness component port around the existing Agentkit delivery core. First prove a working vertical integration of the reused terminal, profile configuration and context-discovery components. Do not rebuild those subsystems independently while the reuse spike is pending. Do not replace the durable controller merely to make an upstream runtime easier to import.

The first external-use milestone is one real task against an explicitly enrolled repository, executed from an independent managed copy, returning a portable review package. The repository's original checkout stays untouched. New-product work follows through the same delivery contracts, rather than a second orchestrator.

All command examples in the engineering plan are **proposed interface specifications**. Existing executable commands remain documented in the [current CLI guide](../phase4-cli-guide.md).
