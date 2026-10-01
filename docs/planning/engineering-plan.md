# Repository-first engineering plan

Status: R0 and R1 implemented; R2 and later work remains proposed. This plan follows the user's choices: existing repositories before new products; small engineering teams and public open-source users; substantial OpenHarness reuse. Runtime authority remains unchanged until the corresponding boundary has been implemented and validated.

## Architecture and ownership

Keep one authoritative controller and one transactional run ledger. Adapt OpenHarness's terminal, configuration and context code around that controller. Do not add a second scheduler or translate upstream session history into authoritative executions.

```text
Adapted OpenHarness terminal / plain CLI / JSON interface
                         |
                 thin command/event backend
                         |
          AgentKit contract, policy and durable controller
             /           |             \
    project/Git broker   |        evidence/package builder
                         |
                allocation + execution broker
                  /                  \
       official CLI workers       constrained verifier
                  \                  /
                  candidate-bound results
```

The UI presents state and sends validated user commands. It cannot create approval by replaying a model message. Project files and model output are untrusted inputs even when the operator and repository are trusted. Filesystem restrictions, credential handling and publication authority remain execution/controller concerns, independently of prompts.

First reuse targets are OH-01 through OH-06 in the [reuse assessment](openharness-reuse.md). Existing `controller.py`, `phase4_state.py`, `git_broker.py`, `adapters.py`, `auth.py`, `resource_policy.py` and role-context validation retain their contracts. Change interfaces incrementally with compatibility tests; do not reorganize the entire repository as a prerequisite.

## Contracts to introduce or extend

Names here specify responsibilities, not a commitment to a new class hierarchy. Version serialized records, reject unknown security-relevant fields and test migration of old records.

| Contract | Required information | Authority and invalidation |
|---|---|---|
| Enrolled project | Opaque project ID, local root identity, resolved committed base, tracked inventory, explicit excludes, profile hash, supported stack | Trusted local enrollment; content under review cannot enroll itself or expand policy |
| Project profile | Read/context/write scope, check recipes, environment recipe, network policy, data-disclosure scope, execution profile, required review | Repository file is proposed configuration until enrolled; changes require re-resolution and any consequential new authorization |
| Resolved task | Requirements, assumptions, non-goals, measurable acceptance, graph, base identity, routing, overall bounds, policy/skill hashes | Controller validation; model plan remains a proposal |
| Assignment | Task/node/attempt IDs, role, permitted delta, actual starting revision, predecessor contributions, check expectations, allocation | Durable identity before launch; stale claimant or changed workspace cannot relaunch |
| Execution allocation | CLI launch reservation, local-check reservation, deadline, captured-byte bound, optional supported provider settings, provenance | Atomic controller reservation; defaults cannot enlarge authorized task bounds |
| Result/evidence | Requested and reported model configuration separately, termination status, nullable usage, output/artifact hashes, revision and environment identity | Provider text is evidence input, not a state transition or approval |
| Approval package | Base/head, diff, requirement/check mapping, findings, limitations, resource report, replay metadata | Read-only export; approvals remain distinct and stale after relevant identity changes |

A profile check is an argv vector, executable identity, candidate-relative working directory, bounded environment references, timeout and declared output interpretation. A shell command found in a README is a suggestion, never an executable profile by itself. Shells/install scripts can still execute arbitrary code; listing an argv is not isolation.

Keep secrets out of profiles, task contracts, events, UI telemetry and exports. Reference supported credential mechanisms without their values. Official CLI login remains in a separate uncaptured interactive terminal. Enrollment must explain that selected code/context is sent to the configured model service; local orchestration does not imply local inference.

## Repository onboarding boundary

The first new profile targets an explicitly enrolled, operator-trusted repository with a clean committed baseline. This is a new execution scope requiring tests; the current disposable-profile evidence does not authorize it automatically.

1. Readiness inspection reads bounded metadata and tracked inventory only. It runs no hooks, project scripts, plugins, dependency installation or model call. Identify dirty state, unsupported Git features, large/binary files, symlinks, candidate secrets and unclear check recipes.
2. Resolve a specific committed base. Preserve the original working tree, branches, index and local changes. Initially block a dirty baseline with a clear explanation; do not stash, clean, commit or silently exclude user work. A later explicit snapshot feature can support dirty changes.
3. Create an independent controller-owned repository from validated local Git objects/content. Specify and test the broker operation before implementation: fixed Git executable/argv, controlled config/environment, hooks disabled, no checkout filters, remote fetch, alternate object store, shared writable metadata or hard-linked writable objects. Do not execute the original repository's Git configuration. Reject submodules, LFS/filter-dependent content and unresolved symlink semantics initially.
4. Reconstruct only enrolled source content and preserve supported filename/mode semantics. Test spaces, Unicode, executable bits, deletion and rename; handle binary changes explicitly rather than silently omitting them. Enforce count/byte bounds. Sensitive-file screening is a warning layer, not proof that the selected content is secret-free.
5. Workers receive isolated plain-file copies derived from broker-owned assignment revisions. No original checkout, controller database, approvals, shared Git metadata or verification harness is mounted into a worker.
6. Before integration, compute each worker's own delta from its actual starting snapshot. Dependencies carry validated predecessor deltas; integration applies each contribution once. Conflict retains both contributions and blocks. Do not regenerate a patch by asking the model to describe what changed.
7. Produce a local patch/package against the exact enrolled base. Applying it to the original repository is a separate explicit operation and is deferred from the first preview.

The environment recipe is a separate gate. Start with a supported Python library using a prepared, disposable environment and no installation during the worker run. Repository tests themselves execute code; constrain them as rigorously as implementation. If dependencies need network access, return `environment_required`; do not silently execute package hooks or borrow the operator's environment. A later explicit installation stage needs reviewed provenance, lifecycle, network and cache boundaries.

macOS remains the initial execution host. Existing provider authentication can expose runtime capabilities that are not comprehensively isolated today. Carry those limitations forward visibly; do not promise safe hostile-code execution or complete credential isolation. A stronger container tool boundary is a separate OpenHarness-backed investigation with real tool-path and lifecycle tests, not a prerequisite disguised as a quick import.

## Planning and useful delegation

Use the existing deterministic controller for intake validation, scheduling, budgets, status and escalation. Do not turn chief-of-staff or manager labels into mandatory model calls.

Task context contains the request, bounded project inventory, relevant interfaces, enrolled constraints, selected skill content and remaining resources. It contains no hidden expected patch or complete transcript. For an unambiguous narrow change, use one implementation assignment and an independent reviewer. Use a planning call only when decomposition or interpretation needs it; account for that call before launch.

A proposal must identify observable acceptance, allowed paths, dependencies, integration method and feasible allocations. Reject unrelated fallback plans, contradictory/negated requests, cycles, overlapping ownership without an explicit integration strategy, excessive graph size and unsupported tools. Material ambiguity becomes a short question with the existing proposal preserved.

Keep the two-worker cap initially. Independent nodes may overlap in separate copies; dependent nodes start from validated predecessor snapshots. No arbitrary nested subagents, speculative parallel workers or extra reviews merely because a role exists. Preserve explicit owner/version claims, cancellation propagation and uncertain-execution reconciliation.

## Routing and resource policy

Use the existing registry and make its configuration available through the adapted OpenHarness profile interface. Do not import upstream model aliases, price tables, token defaults, retries or SDK credentials as authoritative facts.

Resolution order remains **explicit task setting → configured role policy → supported provider default**, within separately enforced overall authorization. A role or task setting cannot expand the user's authorized capabilities or aggregate budget. Record each effective value, source, enforcement category and short reason before launch.

- CLI launch counts, supervised concurrency, captured bytes, process deadlines and total allocations are controller-enforced where supported.
- One launch can contain multiple provider requests. Track internal requests/turns only when reliably reported; otherwise unknown.
- Productive CLI output controls remain unset unless an explicit supported override is selected. Unset does not mean unlimited. Smoke restrictions stay in smoke profiles.
- Provider permissions and cancellation have their documented limits. No hard token or dollar ceiling is inferred from observed tokens or cost estimates.
- Mandatory verification and independent review reserve both calls and feasible time before optional planning, implementation fan-out or repair.
- Retries and escalation consume the same task budget. Actual output exhaustion may justify a different supported allocation; malformed content alone does not justify repeatedly enlarging a budget.
- Cross-provider review, when required, excludes every provider that contributed implementation or repair. Missing availability blocks the requirement rather than silently weakening it.
- Requested model/effort and reported model/effort remain separate. Account default is explicit; absent comparison evidence means a configured default, not a claim of optimal cost or quality.

Keep nullable input/output/cached-input/cache-creation/reasoning usage and estimated/billed costs distinct. Preserve observations for failed attempts. Waiting for authentication consumes neither an active worker slot nor a repair attempt; the failed inference still counts. No new API credentials or paid fallback are part of this plan's initial implementation.

## Independent verification and evidence

Generalize the current protected verifier instead of running repository tests inside the controller process. Build a fresh candidate snapshot with no Git metadata, controller state, approvals or provider credentials. Enforce read-only source where supported and provide a separate writable runtime/cache area. A required unsupported check blocks packaging or appears as an explicit unmet requirement; it cannot silently pass.

Separate four kinds of evidence: existing project tests, agent-authored tests, controller-owned acceptance checks and human observations. Record check identity, command/environment recipe hash, executable revision, candidate manifest, exit status, collection count where available and sanitized output. Fail closed on missing/empty required collection, source mutation, stale check inputs or parser ambiguity. Tests can still be inadequate or misleading; independently executing them does not prove semantic correctness.

Bind review to the exact integrated candidate, task contract and verification bundle. Review must identify concrete defects or unmet criteria. Pass structured findings and relevant failed-check output into bounded repair. Repeat failures stop with a useful checkpoint, and any candidate change invalidates affected evidence and approvals.

The portable package includes a concise summary, base/head, diff, requirement matrix, checks and limitations, review findings, policy/skills/source hashes, resource observations and replay instructions. Export excludes secrets, private paths where unnecessary, raw login material and full transcripts by default. An offline verifier checks integrity and internal consistency, not whether an untrusted author actually ran a command. Signed attestations and authenticated team approvals remain later work.

Exports/imports require traversal/symlink/size tests; reading a package must not execute code. Reviewers may inspect a plain folder or archive without provider access. The original run database remains local and authoritative; it is not shared over a network filesystem.

## Terminal and small-team experience

Reuse OpenHarness's terminal components early, then adapt them to task status, findings and evidence. Keep a plain/JSON CLI with equivalent controller operations. The frontend has a small versioned command surface; reconnect requests status, never replays an execution start. Separate model text from buttons that carry user intent.

Proposed interface, **not current executable commands**:

```sh
agentkit project inspect /explicit/repository --json
agentkit project enroll /explicit/repository --profile python-library.json
agentkit task propose --project PROJECT_ID --request "Fix the documented empty-input behavior"
agentkit task show TASK_ID --plan
agentkit task run TASK_ID
agentkit task status TASK_ID
agentkit task cancel TASK_ID
agentkit task resume TASK_ID
agentkit task package TASK_ID --output ./review-package
agentkit package verify ./review-package
agentkit ui
```

Start and resume validate stored authorization, remaining resources, candidate identity and lifecycle before launching anything. Enrollment UI can collect consequential initial access decisions once; routine permitted work does not repeatedly ask. Missing auth opens the existing official terminal handoff, never a UI transcript capture. A shared project profile is locally hash-enrolled; changing it in a PR cannot authorize its own execution.

The package gives a teammate enough context to review without installing the TUI. Local operator labels are not authenticated team identities. The preview does not implement RBAC, a server, remote scheduling, organization-wide policy enforcement or GitHub publication.

## Milestones and exit gates

Estimates are rough engineering effort for one focused engineer, excluding unknown pilot scheduling and major upstream incompatibilities. Re-estimate after R0; they are not delivery promises. Several documentation/pilot activities can overlap. Do not expand execution authority merely to meet a date.

| Milestone | Work and reuse | Exit evidence | Estimate |
|---|---|---|---|
| R0: working reuse slice | Port OH-01..06 subsets with notices, thin backend, profile resolution and bounded context discovery | A deterministic AgentKit run rendered through actual reused components; upstream/adaptation tests; dependency closure; architecture decision with measured extraction effort | 3–5 days |
| R1: read-only repository intake | **Implemented:** project identity, inventory, profile enrollment, readiness/plan CLI | Disposable unsupported/dirty/sensitive-feature fixtures; zero script/hook/filter/inference execution; request-sensitive plans on `src` and flat Python shapes | Complete |
| R2: safe supported repository delivery | Independent managed import, prepared Python environment, generalized verifier, same scheduler/auth/evidence contracts | No original changes; source/controller/credential canaries; real tests with protected acceptance; task-to-package across disposable copies of realistic repositories | 8–12 days |
| R3: small-team preview | Package exporter/verifier, complete terminal workflow, install artifacts, docs and provenance | Another operator installs without global edits and a second reviewer understands/checks a package; offline and supported-host regressions; explicit license and compatibility matrix | 5–8 days |
| R4: measured pilot | Explicitly enrolled pilot repositories, matched direct-CLI comparison, failure analysis | Predeclared tasks and metrics; all failures included; feedback shows whether evidence saves total human work | 1–2 weeks observation, partly overlapping |
| R5: new-product path | Reuse same contracts for fresh project briefs; JS/TS or dependency-free web profile chosen from demand | Derived plan, real build/mechanics/browser checks, independent review, revision-bound package; Breakout remains one candidate acceptance brief | 5–10 days after stack/boundary decision |

Initial repository preview is roughly 4–7 engineering weeks through R3, with pilots starting during development. The range is deliberately broad; it excludes Linux/container adoption and any optional API worker. If the source extraction or environment boundary is harder than expected, reduce first-release breadth rather than removing checks. Linux/container work is a separately estimated lane only when pilot demand justifies it; reuse OH-07 and validate actual boundaries before shipping.

An authentication/integration lane can proceed independently of R0/R1: preserve the four-launch historical checkpoint, use guided official login when explicitly needed, and complete the missing Claude implementation/review comparison under a newly declared live budget. This planning request does not renew an expired or consumed live-test allowance. Do not repeat successful Codex inference simply to make a new report look complete.

## Implementable backlog

Each ticket should fit a reviewable change, with attribution and tests in the same change. Dependencies below are logical gates, not instructions to run many agents.

| Ticket | Deliverable | Depends on | Behavioral acceptance |
|---|---|---|---|
| P01 | Pinned adoption ledger, copied-file notices, resolved license/dependency closure | None | Every imported file has origin/hash/patch mapping; no unreviewed runtime installs |
| P02 | Adapted terminal protocol and thin controller backend | P01 | Unknown/oversized commands rejected; model text cannot approve; reconnect does not relaunch |
| P03 | Port profile resolution/context discovery | P01 | Root escape/symlink/changed-hash rejection; provenance retained; no ambient auth/retry/output override |
| P04 | Reuse spike gate and packaging decision | P02, P03 | Real adapted components show deterministic complete, cancelled, auth-wait and stale-evidence runs |
| P05 | Read-only project inspector and enrolled profile schema | P04 | No scripts/hooks/filters; unsupported inputs explained; inspection stays within named root |
| P06 | Independent repository importer | P05 | Original tree/index/refs unchanged; no alternates/hardlink exposure; filenames/modes/limits verified |
| P07 | Prepared-environment and check recipe contracts | P05 | Missing dependencies block; recipe cannot grant network/secret/controller access |
| P08 | Generalized constrained verifier | P06, P07 | Planted defects caught by protected checks; empty tests/source mutation/stale candidate rejected |
| P09 | Repository task adapter and structured handoffs | P03, P06 | No fixture-solution context; different real requests produce relevant validated plans or clarification |
| P10 | Delivery integration and preserved lifecycle regressions | P08, P09 | Unknown predecessor content consumed; stale contender cannot rerun; auth history/resume intact |
| P11 | Portable package and offline consistency verifier | P10 | Tampering, stale evidence, escaping paths and missing required checks fail; no execution on import |
| P12 | Complete plain/JSON/TUI workflow | P04, P11 | Equivalent status/next action, unknown usage and cancellation; no hidden authority in frontend |
| P13 | Distribution, notices, compatibility and data-flow docs | P12, license decision | Clean-machine no-inference onboarding; optional frontend; reviewed assets/locks, no global mutation |
| P14 | Pilot protocol and user discovery | P05; collection after P13 | Matched baseline, failures counted, reviewer/operator effort and escaped defects recorded |
| P15 | Product-project creation and web acceptance profile | P10, P11; stack decision | Same graph/controller, independent browser/mechanics checks, owned preview cleanup; no game graph hardcode |
| P16 | Optional container/API engine feasibility | Explicit need and authority | Real tool/credential/lifecycle tests; per-request accounting and auth terms; never a silent CLI fallback |

## Validation and migration

Most development remains offline. Port relevant upstream tests; add integration tests at the actual frontend/backend, request-construction and filesystem boundaries. Fake only external provider transport when testing propagation. Use synchronization primitives for concurrency regressions, not a timing-only claim.

Retain the existing regression families: invalid numeric limits and transitions; atomic reservations and quality reserves; stale approvals/evidence; multiple authentication checkpoints; abandoned login reconciliation; changed actual Git state on resume; timeout/cancellation; secret exclusion; dependency snapshots; stale scheduler claims; unsupported/negated requests; model/effort/context propagation; truncated output classification and bounded recovery.

New adversarial fixtures cover repository config/hooks, instruction scope expansion, secret-like canaries, tool path escapes, modified check recipes, wrong/empty test collection, tampered packages and malicious terminal events. Tests of one boundary do not establish all credentials or network paths are isolated. Report host-only checks/skips separately and retain historical live evidence unchanged.

Schema migrations are transactional and versioned, with before/after fixtures. Older artifacts remain readable. Do not migrate an uncertain active execution into a runnable state. New profile hashes apply to new runs; changed execution policy on an existing run requires explicit validation and evidence invalidation. Rollback preserves databases and artifacts rather than deleting failed runs.

No inference is part of installation, default tests or this planning task. Before each future live gate, declare task-specific launches, concurrency, deadline and stop conditions, commit the executable, then record exact versions/policy/candidate and all failed attempts. Separate implementation commits from live evidence. A failed attempt is not validation of subsequent changes.

## Release decision

Ship a narrow preview when an independently operated supported repository task reaches a verifiable local package, the execution boundary passes host checks, provenance/install requirements pass and limitations are understandable. Do not gate success on a visually impressive game, arbitrary task volume or a claim of general autonomy.

If R0 cannot substantially reuse upstream code without importing unsafe authority, stop and compare the fork/leaf-engine options with concrete evidence. If R2 cannot enforce the promised boundary, retain read-only intake and offline package inspection while that mode remains blocked. If pilots show no reduction in total human effort, revise acceptance and UX before adding management agents, platforms or publication.
