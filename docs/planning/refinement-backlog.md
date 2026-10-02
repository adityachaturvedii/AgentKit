# Product-refinement engineering backlog

Status: proposed, unimplemented tickets. The [plan](refinement-plan.md) defines scope and gates; [specialist contracts](specialist-skills.md) define agent and skill behavior. Ticket IDs are new and do not replace the historical P01–P15 ledger.

## Dependencies and independent ownership

```text
REF-00 baseline inventory / approved integration of prerequisites
  ├── REF-01 worker readiness ──────┐
  ├── REF-02 failure and recovery ──┤ G1
  └── REF-03 usage and identity ────┘

REF-04 specialist/context contracts ── REF-05 guided intent and acceptance
                    └── REF-06 facade and progress UI
REF-05 ── REF-07 design-guided implementation
REF-01 + REF-04 ── REF-08 browser capability
REF-02 + REF-06 + REF-07 + REF-08 ── REF-09 result and refinement
G1 + REF-05–09 ── REF-10 operator acceptance / pilot
```

These are engineering work packages, not the runtime graph of every user task. Until the interfaces below are agreed, do not delegate overlapping controller/CLI edits. Three implementation owners can then work in parallel: (A) recovery/accounting core, (B) specialist/skill/intake, (C) terminal/result frontend. Browser capability can be a fourth independent workstream after runtime contracts exist. This is a future implementation decomposition, not permission for runtime agents to spawn workers or exceed the two-provider limit.

One integration owner reviews cross-component changes and runs the full suite. Keep each change in a dedicated worktree based on refreshed integration. Frontend owners initially use typed fixture events; skill authors initially use fixed synthetic handoffs; neither invents its own controller schema. Integrate shared schema changes before consumers. No worker can merge or publish itself.

## REF-00 — reconcile the executable baseline

**Outcome:** implementation starts from the latest deliberately selected code and preserves all completed work.

**Inputs:** refreshed integration, R5 `9a05b63` and R4 `3dd45c6`. Inspect changes, ancestry, required checks and open findings. Do not assume the older local `implementation/phase-2` worktree matches its remote-tracking ref.

**Deliverable:** baseline ledger naming which commits are integrated, awaiting PR/merge, or deliberately excluded; retained historical archive manifests; current capability matrix. R5 fixes precede product changes; R4 may be deferred until pilot collection. Publication/merges require explicit authorization, so the planning task cannot close that part.

**Gate:** exact integration SHA and clean new worktree recorded; no resets/stashes/history rewrite; unchanged historical hashes; no reimplementation of existing work. Effort: small review/integration preparation, external merge timing excluded.

## REF-01 — make advertised worker tools actually usable

**Outcome:** a web worker can run its declared local tests, or submission reports a concrete missing capability before model inference.

**Owners/seams:** runtime adapter owner; `doctor.py`, `adapters.py`, `delivery.py`, resource profiles; R5 `product.py` when available. Resolve/pin the approved Node or Python runtime and its required support files; explicitly control worker PATH and shell startup behavior. Do not inherit the user's broad environment or open filesystem access merely to make `node` resolve.

**Deliverable:** per-role readiness result and prepared runtime manifest used by both dispatch and status. Keep worker self-check tools separate from the protected verifier copy.

**Behavioral tests:** real adapter/request construction with only external inference transport stubbed; fake CLI launches approved Node inside the actual supported owned-code profile; unavailable/tampered runtime blocks before provider launch; sibling/controller/Git/fake-secret canaries remain denied; invalid runtime cannot trigger unrestricted fallback. Host-only results remain separate from simulated tests.

**Gate:** source edit plus meaningful JS/Python test demonstrably works in each claimed role environment; no widened sandbox. Effort: medium, host-bound uncertainty.

## REF-02 — actionable failures and narrow quality-stage recovery

**Outcome:** failures name their cause and preserve useful work; fixing infrastructure does not require a new task or editing the database.

**Owners/seams:** controller owner; `controller.py`, `orchestration.py`, `auth.py`, R5 product verifier. Define versioned `FailureRecord` with category, failed stage/execution, candidate, evidence ID/hash, redacted diagnostic tail, retryability and permitted recovery action. Separate original cause from the later exhausted-repair decision.

**Deliverable:** state-specific recovery for planning authentication and proven environment/oracle correction. A `RecoveryDecision` binds old failure, corrected environment/oracle identity, source state, process termination evidence, actual repository/branch/HEAD/manifest, remaining budget and invalidated evidence. Use narrow validated transitions, not generic `blocked → running`. Unknown diagnosis/lifecycle stays blocked. Cancellation and quota never trigger automatic relaunch.

**Behavioral tests:** reproduce cross-realm oracle false failure without provider calls; calibrate corrected oracle with positive/negative controls; resume verification/review without implementation duplication; preserve failed history/counts; reject modified candidate, weakened acceptance, stale evidence, unresolved owner, exhausted budget and competing recovery claims; force-login remains uncaptured and one-owner; planning auth checkpoint survives restart.

**Gate:** one supported recovery reaches a package offline with zero repeated successful inference, and unsupported recoveries fail visibly. Historical SplitSmart state is not silently rewritten or retroactively called passed. Effort: large; land typed failures before recovery transitions.

## REF-03 — resource visibility and configured Git identity

**Outcome:** the operator sees useful observations and new commits honor their verified identity.

**Owners/seams:** accounting/broker owner; `orchestration.py`, controller usage records, `git_broker.py`, display projection. Add per-category reported subtotal, coverage count, missing-provider-execution count and complete/partial/unknown state. Local checks are not token-reporting providers; do not count missing local telemetry as missing model usage. Do not sum overlapping cache categories into a fictional total or treat reasoning counters as necessarily additional output.

**Deliverable:** usage view with CLI launches, reported internal counts where available, elapsed wall/summed execution time, reservations/remaining allocation, per-provider categories and distinct estimated/billed cost completeness. Resolve author and committer from trusted run configuration before the first commit; validate strings and persist the source. Worker output cannot select identity; use per-command environment/settings only.

**Behavioral tests:** mixed provider+local executions retain known provider totals; one unknown provider yields partial subtotal, not zero/full total; failed/auth calls counted; concurrent reservation/deadline limits retained; absent cost stays unknown; new Git commit uses configured identity; global config and historical candidates unchanged.

**Gate:** status can explain the archived SplitSmart usage without claiming complete cost or cache totals; identity matches the current user instruction on future disposable commits. Effort: medium; accounting and identity can land as separate commits.

## REF-04 — specialist profiles and evaluated skill registry

**Outcome:** expertise is an explicit, reproducible configuration instead of a persona label.

**Owners/seams:** role/context owner; extend `phase4_contracts.py`, routing configuration, catalog/pack, existing context assembly. Persist base role + specialization, activation reason, eligible capability/model profiles, output schema and selected skill/reference hashes. Avoid changing durable state roles just to add a specialist label.

**Deliverable:** the contracts in [specialist-skills.md](specialist-skills.md), a small bundled skill increment, and per-skill maturity/provenance metadata. Teach selector negative triggers and progressive disclosure. Keep existing catalog IDs and v1 handoffs compatible; explicitly version new payloads. Do not import global personal skills wholesale.

**Behavioral tests:** small bug activates no designer/manager model; visual work includes design instructions in actual provider input; API interface work does not misroute to visual design; changed source/reference/hash rejects dispatch; irrelevant skill not loaded; capability/authority requests cannot elevate scope; exact requested model/effort reaches transport; reviewer excludes every implementation/repair provider; impossible two-provider independence blocks before calls.

**Gate:** authored skills pass structural checks and held-out deterministic/independent forward cases with strengths/gaps recorded. Fixture maturity only until separately evaluated live. Effort: medium/large; schema commit first, skill and routing consumers next.

## REF-05 — guided intent and independent acceptance preparation

**Outcome:** the user supplies a natural-language task and meaningful constraints; AgentKit prepares inspectable internal contracts.

**Owners/seams:** intake owner; unified CLI facade, existing project inspector, planner and handoff validation. Build a requirements/assumptions view; ask only for material ambiguity. Preserve explicit execution authorization; ordinary task prose cannot expand paths, tools, spending or publication.

**Deliverable:** brief-to-contract path with deterministic handling for narrow changes and bounded model shaping only when needed. Reuse existing enrolled tests when adequate. Otherwise acceptance engineer proposes tests in a separate disposable assignment from requirements/interfaces, without implementation code. Controller validates source/argv/runtime policy, calibrates against controlled positive/negative cases, and freezes independent acceptance before worker execution. Users may still supply their own tests via the advanced path.

**Behavioral tests:** different briefs yield different plans; negated/unmatched/conflicting requests never become unrelated fixtures; no finished solution leaks into worker context; empty discovery and broken test harness rejected; conditional model calls are reserved/accounted; mandatory quality reserves survive shaping; meaningful ambiguity preserves a draft without executing; no user-authored JSON needed for a supported scenario.

**Gate:** deterministic guided Python task and static-product draft pass intake without an expert assembling internal files. Runtime broadening stays separately gated. Effort: large, split into guided contract then acceptance preparation.

## REF-06 — one workflow facade and useful terminal progress

**Outcome:** one consistent command experience across supported repository, fixture and product paths.

**Owners/seams:** frontend owner; `__main__.py`, `terminal_workflow.py`, pinned OpenHarness protocol/renderer. Version a `RunView` with objective, workflow kind, stage, active assignment, actual last-activity time, candidate summary, failure, acceptance coverage, resource completeness and validated next actions. Protocol migration preserves old consumers and rejects unknown authority fields.

**Deliverable:** guided entry and reconnectable read-only watch; concise plan/status/result views; optional details. Keep existing commands as compatibility aliases/adapters. Replace smoke terminology on productive commands with clear execution consent while preserving legacy flags. Audit before importing any further OpenHarness terminal dependencies; no runtime install or arbitrary backend spawn.

**Behavioral tests:** all supported kinds dispatch to correct existing engine; old CLI commands still work; reconnect never starts work; duplicate starts do not launch duplicates; events cannot authorize execution; cancellation reaches supervised workers; terminal escape injection rejected; narrow/redirected/non-TTY output readable; usage/blocker shown accurately; no fake progress percentages.

**Gate:** an unfamiliar operator can explain plan, current activity and next action from the default view. Validate with a small interaction prototype before building a full-screen TUI. Effort: large, with plain streaming first.

## REF-07 — design-guided product work

**Outcome:** visual/interaction intent survives planning, implementation and critique.

**Owners/seams:** skills/design owner with product adapter owner; new `DesignBrief`, frontend handoff and protected criteria. Use existing brand conventions where available. Offer compact direction choices only when important; routine layout fixes use a stated reversible assumption. Include page structure, typography/spacing/color tokens, component states, touch/keyboard behavior and responsive targets. No compulsory extra “designer call” if one shaping execution can produce the needed result.

**Deliverable:** generic design context for static products, without game/calculator-specific graphs or finished solutions. First validate two unrelated briefs. A later allowed product-manifest extension may permit task-derived local file names/assets, but only after create/delete/mode/export semantics are covered. Until then, explicitly label the existing four-file R5 limit; do not silently broaden writes or dependency installation.

**Behavioral tests:** design handoff reaches real adapter input and is hash-bound; materially different directions produce different coherent specifications; frontend-only revisions trigger relevant rechecks; reviewer marks preference separately from reproducible defect; asset paths/provenance cannot expand authority; refinement rounds share original call/repair limits.

**Gate:** a chosen direction is visible in implementation and evaluated against explicit criteria; no “polished” pass based only on CSS presence. Effort: medium once REF-04/05 exist.

## REF-08 — actual browser acceptance capability

**Outcome:** repeatable browser interaction is available within a declared supported boundary, or the product gate explains exactly why it is unavailable.

**Owners/seams:** browser/runtime owner; current `web_acceptance.py`, snapshot/preview owner, external browser-driver adapter. Select an already available driver when it can satisfy the contract; dependency/browser installation requires separate review and authorization. This ticket does not assume access to the user's existing browser profile.

**Deliverable:** fresh dedicated browser context/profile, controlled loopback snapshot, viewport selection, keyboard and supported touch/pointer actions, console/page-error capture, page-only screenshots, strict run/candidate/session/snapshot receipt and owned-process cleanup. Explicitly document unproven credential/network/descendant boundaries. Tool availability alone does not establish isolation; stop if the required boundary cannot be enforced.

**Behavioral tests:** deterministic static test pages; actual browser operations when supported; stale snapshot/report rejected; credentials/canaries excluded; external navigation/downloads blocked by the validated mechanism where claimed; logs/screenshots exclude unrelated tabs; timeout/cancel cleans owned preview/driver; missing browser returns unsupported without weakening acceptance. Report real touch-device tests separately from emulation.

**Gate:** same candidate passes declared desktop/narrow/keyboard/core-flow checks with browser/version and exact artifact identity. A mock cannot close this gate. Effort: large with capability/installation uncertainty; treat the feasibility result as a deliverable if blocked.

## REF-09 — review-ready result and bounded refinement

**Outcome:** results are understandable and usable without opening raw JSON archives.

**Owners/seams:** frontend/package owner; existing portable-package exporter/verifier, immutable candidate/evidence. Lead with change summary, try-it/replay commands, acceptance matrix and unresolved findings; expose diff, design decisions, usage and provenance next. Optional escaped static HTML artifact must execute no candidate or model-supplied script.

**Deliverable:** one result view with human-readable evidence categories and exact base/head. If preview is allowed before final review, label it diagnostic, create the same protected snapshot and record no approval; do not repurpose it as an acceptance pass. Follow-up refinement creates a bounded assignment linked to previous candidate/design and invalidates affected quality evidence; it never patches the original repository automatically.

**Behavioral tests:** incomplete/wrong-revision evidence prevents approval package; known/unknown/manual checks clearly distinguished; HTML/terminal injection rejected; stale approval invalidated; refinement preserves history and budget; changed candidate invalidates browser/review evidence; preview cleanup independently established; exported hashes verify without executing product code.

**Gate:** a second engineer can identify what changed, what was tested and what remains uncertain without reading provider transcripts. Effort: medium.

## REF-10 — operator acceptance, then measured pilot

**Outcome:** demonstrate the product journey, not another isolated successful inference.

**Prerequisites:** relevant gates passed and executable changes committed; nominated supported tasks; separately authorized finite provider-call and wall-time budgets; authenticated supported CLIs; reviewed host/browser capability. Preserve prior evidence; do not reuse old live allowances.

**Sequence:** (1) offline end-to-end task under one facade; (2) supported Python repository scenario from controlled disposable content, then separately authorized nominated repository if profile allows; (3) fresh product brief whose plan/design is derived by the harness; (4) frozen R4 protocol and consented pilot when ready. Do not manually supply a finished implementation to obtain a pass. Real-repository scope expansion remains gated, so blocked access cannot invalidate completed disposable evidence.

**Record:** exact code/candidate/skill/runtime/model identities, generated graph, actual intervals, all provider/local attempts, failure/recovery path, human interventions, independently measured acceptance, design/visual judgment, redacted outputs and hashes, unknown usage/billing and cleanup. A failed demonstration diagnoses the tested code only; later fixes need their own evidence.

**Gate:** supported journey reaches a candidate-bound local unapproved package without hand-written internal JSON, manual source corrections or database edits. Repeat inference solely to manufacture evidence is prohibited. Pilot success is descriptive until enough real observations exist; do not advertise calibrated routing, productivity or general safety from fixtures.

## Suggested implementation batches

1. **Reliability batch:** REF-00 preparation + REF-01 + failure reporting portion of REF-02 + REF-03. Review this before new agent stages. This delivers immediate value even if browser work remains blocked.
2. **Specialization and intake batch:** REF-04 schemas/skill evaluations + REF-05; frontend REF-06 can develop against agreed fixture events in parallel.
3. **Product experience batch:** finish REF-06, add REF-07/08/09, then close narrow recovery transitions from REF-02 against the complete flow.
4. **Acceptance batch:** REF-10. Refresh provider capabilities at this gate, not repeated billing investigations. Budget for observed task complexity and mandatory quality stages explicitly.

Effort labels compare engineering complexity; they are not promised calendar durations. Browser readiness, safe recovery migration and pilot access are the largest uncertainties. Keep change sets reviewable and pass relevant regressions after each behavior change instead of waiting for one large release.

## Implementation handoff template

```text
Implement REF-<ID> from docs/planning/refinement-backlog.md and the associated
contracts in specialist-skills.md. Refresh integration refs and inspect existing
R4/R5 descendants before branching. Use an isolated branch/worktree; preserve
other work, archived evidence and the verified execution boundary.

Agree the shared schemas before parallel edits. Use deterministic fixtures and
stub only external inference transport when testing real adapter construction.
Run applicable regressions, record implemented/simulated/host/live distinctions,
and update checklist and decisions. Commit locally using the user's command-scoped
Git identity. No live inference, installs, publication or merge unless separately
authorized for this ticket. Stop at the ticket gate and report concrete blockers.
```
