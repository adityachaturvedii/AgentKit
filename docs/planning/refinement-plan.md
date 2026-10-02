# Next milestone: a complete AgentKit experience

Status: proposed engineering work, not implemented behavior. Prepared 2026-10-02 after reviewing the local R5 completion checkpoint. This change contains documentation only; it authorizes no provider inference, installation, repository execution, publication or merge.

Read alongside the [specialist and skill design](specialist-skills.md) and [implementation backlog](refinement-backlog.md). This increment refines the existing controller and OpenHarness component port; it introduces no second orchestrator.

## Verified starting points

`git fetch origin` completed before planning. Observed refs:

| Work | Revision | Relationship and evidence |
|---|---|---|
| Remote integration | `8d9cc311df47355ce64e588b8cb8de60a4ae25ae` | Base of this dedicated planning worktree; R0–R3 delivery components |
| Remote release | `cd81a4e` | Merge of integration through PR #21; do not start from an assumed local main |
| R5 product path | `e4feae3` | Descendant of integration, not contained in refreshed integration |
| R5 fixes and live archive | `9a05b635855b89df3115edaabd8db4fefd0b7555` | Includes forced login, planner corrections and SplitSmart evidence; not contained in integration |
| R4 pilot ledger | `3dd45c67abb40a6aa82d362b58d729ce60e7d9e6` | Separate child of integration; protocol/fixtures implemented, no measured pilot collected |

R5 executable tested: `accfed2889fb6e76f46c87e3a7c3e6cdebcfbe65`. Generated candidate: `dff426470d69802372d289acc950072e23677a0d`. Planning and implementation succeeded; protected verification failed on an oracle bug; no independent review or approval package followed. Separate diagnostic mechanics and partial Safari checks are not authoritative completion. Historical artifacts stay unchanged.

Before implementation, reconcile these branches through the established, separately authorized feature PR → integration → release flow. Do not replay their changes from scratch. R4 is required only for the later pilot; R5 is required for product-specific recovery, environment and browser tickets. Shared CLI/role work can proceed from integration with explicit compatibility seams before that merge. There is no merge authorization in this planning request.

## Product outcome

AgentKit should let a developer describe a supported change, understand the proposed approach, watch useful progress, and inspect a working candidate with independent evidence. Existing-repository work remains the first release priority; a new-product path uses the same interaction and delivery contracts. Named personal repositories still require explicit authorization and a validated profile.

The next milestone is successful when a fresh operator can complete the supported journey without writing internal JSON, diagnosing SQLite state or asking a developer which historical command family to use. Expert JSON/argv interfaces remain available for automation. Broader platform coverage, more simultaneous agents and dashboards are not acceptance criteria for this milestone.

### What the review established

| Gap | Observed basis | Engineering implication |
|---|---|---|
| Intake requires engineering assembly | R5 `product submit` requires a brief, acceptance JSON and executable mechanics test | Add a guided task/acceptance proposal and independently controlled test preparation |
| Frontend is fragmented | `TerminalWorkflow` targets `Phase4Workflow`; repository/product execution has separate entry points | Introduce one validated workflow facade, retaining compatibility commands |
| Blocker presentation hides the cause | R5 status reports `repair budget exhausted`, while evidence identifies a Node VM error-constructor mismatch | Carry failure domain, reason, evidence and supported next action through the UI |
| Product tools are not ready inside workers | R5 Codex stream records Node unavailable although the verifier has a pinned Node runtime | Probe and provision the approved runtime into the actual worker environment before inference |
| Design expertise is underspecified | `interface-design` is an API/ownership skill; frontend procedure is primarily verification | Add explicit product shaping and visual/interaction design skills |
| Usage summary loses useful information | Local-check null token fields turn status aggregates unknown | Exclude non-provider calls from provider totals; show reported subtotals with completeness metadata |
| Authenticated is not necessarily inference-ready | Official shallow status preceded a real expired-OAuth response | Keep non-inference status qualified; recover the exact stage on real auth failure |
| Commit identity ignores operator preference | Broker fixes author and committer to `controller@localhost` | Resolve a controller-owned per-run identity before creating new commits |

These findings do not show that every candidate is wrong or that the sandbox should be relaxed. They show that the product currently depends on developer intervention. The next work must reduce that intervention while preserving existing boundaries.

## Intended user journey

The following commands and views are proposed, not executable instructions for today's release. Final spelling can change before the CLI compatibility gate.

```text
agentkit work new                 # choose Change a project / Create a product
agentkit work plan <run>          # inspect scope, approach, acceptance, team, allocation
agentkit work start <run>         # explicit authorized execution
agentkit work watch <run>         # reconnectable, read-only progress
agentkit work inspect <run>       # blocker, checks, findings, usage, diff
agentkit work resume <run>        # supported checkpoint only
agentkit work cancel <run>
agentkit work result <run>        # summary, replay/preview, evidence/package
```

1. **Intake.** Readiness establishes supported target, prepared tools and data exposure. Ask for the objective and material constraints. Separate supplied requirements from reversible assumptions. A product brief may need a short audience/flow clarification; a routine repository bug should not receive a design interview.
2. **Plan.** Present a short approach, observable acceptance, allowed paths, selected specialists/skills, routing rationale, resolved call/time bounds and limitations. Routine approved scope proceeds without repeated permission prompts. Missing authority, materially conflicting goals and cost changes produce one specific checkpoint.
3. **Execution.** Show current stage, elapsed time, last meaningful activity, active assignment, changed-file count and budget remaining. Use measured events, not fabricated percentages or inferred completion from silence. Expand logs and detailed routing on demand.
4. **Recovery.** State what failed, what is preserved, which operation can resume, and whether any remaining resource allowance is required. Authentication opens only the separate uncaptured official terminal flow. Uncertain process ownership remains blocked.
5. **Result.** Lead with what changed and how to try it, then acceptance coverage, review findings, exact revision and resource observations. Allow a bounded follow-up such as “make the controls clearer”; bind that new assignment to the candidate and invalidate affected evidence. It is not unlimited iteration.

Illustrative terminal layout (sample values only):

```text
AgentKit / Split a restaurant bill
Checking the candidate                   Last activity: mechanics test completed

Plan  ✓   Implement  ✓   Verify  !   Review  waiting   Result  waiting
Candidate preserved: <revision> · 4 changed files

Attention: the protected test failed in its VM exception assertion.
The product has not yet passed verification. No repair was launched.
Next: inspect verification evidence; request a supported oracle correction.

Calls 2/3 provider · local checks 1/1 · reported usage partially available
[Plan] [Diff] [Checks] [Usage] [Cancel]
```

This screen must not automatically label an ambiguous test failure an oracle defect. That diagnosis needs evidence and a validated recovery decision.

## Mature specialization

Maturity means reproducible role performance, specific deliverables, useful feedback, bounded context, environment readiness and honest failure reporting. It does not mean a larger always-running hierarchy.

Activate a product shaper for material product ambiguity, a UX/visual designer for user-visible design, and a tech lead for nontrivial decomposition. Use frontend or Python specialists for the supported implementation profiles. Prepare acceptance separately from implementation, execute it deterministically, and retain an independent reviewer. Accessibility, security and performance expertise are conditional overlays triggered by a concrete task, not mandatory extra calls.

Keep chief-of-staff status and manager scheduling deterministic. Start with at most two simultaneous provider executions and the existing two implementation assignments. Multiple specializations can run sequentially under existing base roles; a role label does not create permission to spawn processes. See [specialist contracts](specialist-skills.md) for tools, outputs and independence rules.

## Architecture changes, kept narrow

- Add versioned `SpecialistProfile`, `SkillBinding`, `DesignBrief`, `AcceptanceSpec`, `FailureRecord`, `RecoveryDecision` and `RunView` contracts where existing records lack the data. Extend rather than replace `TaskContract`, graph nodes, controller ledger and provider requests. Old fixtures and archived schemas remain readable.
- Persist specialization separately from the base execution role. Existing reservation rules continue to constrain base roles until a migration explicitly supports a new stage. New shaping/acceptance calls are real reserved executions, never hidden prompt preprocessing.
- Put facade adaptation at the CLI/frontend boundary. `TerminalWorkflow` delegates to an explicit validated workflow kind; never infer a kind from untrusted filenames or silently reopen a product as a fixture. UI events carry data and bounded command IDs, never authority objects or arbitrary shell actions.
- Reuse pinned OpenHarness components for terminal interaction and discovery. Audit the complete optional frontend dependency/license closure before importing its full UI. A usable streaming plain terminal is the fallback; adding a full-screen TUI is conditional on a measured usability benefit, not a prerequisite for correctness.
- Generate review presentation from existing sanitized package data. A local static HTML review artifact may improve diff/check/design inspection; it is an optional export, not a server/dashboard. Escape untrusted text, disable active content, and serve any candidate preview separately.
- Preserve source boundaries. The generated product stays in its managed repository, protected acceptance stays outside worker copies, and credentials remain managed by official provider CLIs. Browser provisioning is its own tested capability; a convenient local browser is not automatically a safe controller driver.

### State and migration seam to agree before implementation

Do not add a loosely checked generic agent stage. Treat shaping/design and acceptance preparation as explicit typed planning-node kinds with their own eligible source states, output schema and reservation role mapping. A proposed draft can be inspected before execution authority exists. Once requirements, acceptance, routes and budgets are frozen, the normal implementation → verification → review gates remain authoritative. Schema migration must preserve old task/graph identities and block an older executable from interpreting unknown new stages as runnable.

Planning authentication records the interrupted planning node and immutable draft inputs; supported resume repeats only that failed attempt under the same ledger. A corrected verifier checkpoint is a separate recovery kind, carrying explicit supersession of failed evidence rather than deleting or overwriting it. Any committed design/requirement revision stales dependent assignments/context and affected checks. Pure presentation edits to a result view cannot change the underlying candidate or approval state.

Define these contracts first, then let frontend, skill and recovery owners implement against fixtures. Keep a table of each node kind's allowed task state, reservation category, output validator and recovery operation in the implementation PR. Every transition needs an illegal-transition and concurrent-claim regression.

## Sequencing and release gates

| Gate | Work | Required outcome |
|---|---|---|
| G0 — coherent baseline | REF-00 | Reviewed R5 prerequisites and optional R4 ledger have explicit ancestry/status; unrelated branches stay untouched |
| G1 — useful, recoverable execution | REF-01–03 | Runtime readiness tested inside worker boundary; actual blockers/partial usage visible; supported recovery preserves prior work; selected commit identity used |
| G2 — skilled team, one front door | REF-04–06 | Typed specialization and context assembly pass behavioral fixtures; brief-to-plan works without user-authored internal JSON; old CLI remains compatible |
| G3 — design and review quality | REF-07–09 | Product design flows reach workers; live progress and useful results; controlled browser checks or a clear unsupported gate |
| G4 — operator acceptance | REF-10 | Supported repository task first, then product task; independent checks/review/package complete without database surgery or manual implementation |

Implement G1 and the contract portion of G2 before expanding visual orchestration. CLI interaction prototypes and skill authoring can run in parallel after their schemas are agreed. Browser work may proceed independently against deterministic snapshots but must not claim a supported execution mode before its boundary tests pass.

## Resource and model policy

Keep explicit task bounds → configured role allocation → provider defaults. Productive generation limits remain unset absent a verified supported override. Every planning, design, test-authoring, review, repair and retry launch consumes the same task ledger. Reserve mandatory verification and review before optional critique. Count CLI launches separately from provider requests/turns, which remain unknown when unreported.

For planning examples, a routine repository fix can need two provider launches (implement + review); a materially ambiguous repository change can need three (plan + implement + review); a visual product can need four to six (shape/design, optional separate technical plan or acceptance preparation, implement, review, optional justified design critique). These are proposed workflow shapes, not fixed defaults, authorization or cost estimates. If immutable independent acceptance already exists, reuse it. If it must be authored by a model, count that call and independently validate it before implementation.

Do not repeat the old 120-second product allocation. Resolve a suitable role timeout from complexity and available history within the explicit total task allowance, display its provenance, and allow an operator override. The observed 286-second implementation is one data point, not a calibrated global timeout. Clarify and separately enforce overall wall deadline versus summed provider/local allocated time; concurrent durations cannot substitute for wall time. Interactive waits release active capacity; their treatment under a task's overall deadline must be explicit before launch.

Model profiles declare exact verified identifiers or explicit account defaults. Recheck installed help and official documentation when implementing supported options; this planning change makes no new availability claims. No invented rankings or prices. Without comparative evidence, choose the configured capable default and label relative quality/cost unknown. Reserve a provider for independent code review against all code contributors, including repairs. With only two providers, do not allocate implementation to both if policy requires a third independent provider that is unavailable.

## Validation and product-quality bar

Use deterministic providers and disposable processes first, then separately authorize a finite live budget against committed executable code. Do not reuse an old trial's allowance. Report unsupported keyboard/mobile/browser controls as gaps, not passes. Run required full regression and structural checks after runtime changes, plus focused contracts, host boundary checks, frontend tests and artifact hygiene. Documentation-only planning does not require replaying the full runtime suite.

For skills, fixture schema tests are necessary but insufficient. Use blinded forward tasks with independently known success criteria, with/without-skill comparisons at matched provider configurations when authorized, and retain adverse outcomes. Check relevance, over-triggering, actual prompt contents, uncertainty handling, task success and human correction effort. Do not claim calibrated model routing or better design from a passing catalog validator.

The operator gate requires: one supported repository task and one product task; no hand-edited controller state; no user-written internal JSON; no manual source fix to force acceptance; no lost completed implementation on a recoverable interruption; a candidate-bound package; readable blocker/result summaries; explicit known/unknown usage; no publication approval. For the product, test desktop, narrow mobile, keyboard, visible focus, error/empty/success states and actual core interactions. Human visual judgment covers hierarchy, coherence, readability and suitability; screenshots support but never replace behavior.

Keep outcome claims modest until R4 pilot collection measures setup/active-human time, interventions, accepted/failed/blocked runs, false findings, rework and escaped defects. The R4 ledger branch is protocol infrastructure, not evidence of user value.

## Scope exclusions and decisions

Retain trusted disposable macOS execution, existing subscription authentication and separately authorized repository access. No paid API fallback, global configuration, automatic plugins, arbitrary dependency installation, hostile-code support, GPU/Linux/remote execution, central service, live GitHub publishing, deployment or autonomous management hierarchy.

Routine engineering choices are settled by this proposal: terminal-first guided experience; existing-repository priority; selective specialists; two-worker cap; reuse current controller; role-relevant bundled skills; immutable evidence. Still consequential before the relevant gate: original-code license before public distribution; chosen pilot repository and permission to inspect it; audited browser/frontend dependencies and installation; explicit live trial bounds. These do not prevent offline implementation planning.
