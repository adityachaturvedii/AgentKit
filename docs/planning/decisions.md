# Planning decision register

Date: 2026-10-01. Distinguish user decisions from engineering recommendations. Neither a proposal here nor a project/model instruction grants new execution authority.

## Confirmed direction

| ID | Decision | Source |
|---|---|---|
| P-D01 | Support existing-repository changes and new-product creation, with existing repositories first | User's explicit scope answer |
| P-D02 | Serve small engineering teams and some public open-source users | User's explicit audience answer |
| P-D03 | Reuse substantial working OpenHarness code rather than building equivalent infrastructure from scratch | User's explicit reuse instruction |
| P-D04 | Develop a detailed plan before further feature implementation | Current planning request |
| P-D05 | Preserve authentication, spending, evidence, sandbox and publication boundaries | Continuing task constraints; no new live allowance here |

## Recommended implementation decisions

| ID | Recommendation | Reason and reversal condition |
|---|---|---|
| P-D06 | Component port around the current controller; start with a working UI/config/context slice | Existing transactional and lifecycle semantics are valuable; reevaluate against a slim fork or optional leaf engine if extraction pulls in most of upstream runtime |
| P-D07 | Existing CLI subscription adapters remain the first worker engines | Already integrated; an OpenHarness API engine adds credential/spend/terms and accounting work with no demonstrated first-release necessity |
| P-D08 | Use independent managed repository copies; leave enrolled originals unchanged | Extends ownership without exposing original/shared Git metadata to workers; implementation must verify object/config/filter isolation |
| P-D09 | Small-team support means portable profiles/evidence first | Solves sharing/review needs without a central service, RBAC or pretending local labels are authenticated identities |
| P-D10 | Optional adapted terminal; plain/JSON controller interface remains complete | Reuses working UI while keeping core usable without a Node runtime; release builds must avoid automatic installation |
| P-D11 | Preserve productive provider defaults and provenance-aware resource policies | Upstream defaults and SDK retries must not reintroduce the output-limit failure |
| P-D12 | Existing-repository preview precedes the next web-game milestone | Matches the user's priority; Breakout remains a new-product acceptance case through the same pipeline |
| P-D13 | Accept the R2 deterministic delivery slice while retaining a separate live/provider gate | Disposable imports, checks, protected acceptance and packaging validate the architecture without authorizing personal repositories or inference. R3 can build the terminal/package experience; a nominated repository and live provider path still need their own bounded validation. |

## Proposed product-refinement decisions — 2026-10-02

These are engineering recommendations prepared at the user's request to plan the next work, not implemented capabilities or new runtime authority.

| ID | Recommendation | Reason and gate |
|---|---|---|
| RF-D01 | Start from refreshed integration and explicitly account for unintegrated R4/R5 work | Preserve existing fixes/evidence; normal PR/merge authorization remains necessary |
| RF-D02 | Refine execution readiness, failure explanation and resource visibility before expanding orchestration | The latest product candidate exposed environment/oracle/status friction requiring developer intervention |
| RF-D03 | Represent specialists as versioned profiles over base execution roles | Add relevant expertise without creating a second scheduler or bypassing state/authority checks |
| RF-D04 | Add product shaping, interaction/visual design and acceptance-design skills with behavioral evaluation | Existing interface design addresses API contracts; visual quality needs explicit intent and evidence |
| RF-D05 | Keep acceptance authoring independent and oracle corrections separate from implementation repair | Prevent self-grading, silent weakening and wasted repair calls; failed history remains immutable |
| RF-D06 | Provide one terminal-first facade across supported workflows | Hide historical phase names and internal JSON assembly while retaining automation compatibility |
| RF-D07 | Keep two provider workers, mandatory review reserves and contribution-based provider independence | Specialization must fit existing task budgets; optional critique cannot consume mandatory quality capacity |
| RF-D08 | Gate browser automation on actual supported-host isolation/lifecycle tests | Browser availability or a screenshot does not establish functional acceptance or a safe boundary |
| RF-D09 | Resolve future commit identity from trusted per-run configuration | Honor the user's identity without altering global settings or rewriting historical candidate evidence |

## Working assumptions and decision deadlines

These defaults let planning proceed. Revisit at their milestone, not by asking for every implementation detail now.

| Topic | Working assumption | Required decision/evidence before commitment |
|---|---|---|
| First stack | Python library with prepared disposable environment; JS/TS second | At R1, confirm pilot stack and specific projects; no access to any personal repository is authorized by this document |
| Execution host | Trusted local macOS operator and repository | R2 host boundary evidence; Linux/container support requires a separate validated lane |
| Product license | Unresolved for original code; preserve all existing/upstream notices | Before public distribution, choose an actual license. Public open-source users do not by themselves choose the project's license; non-compete restrictions are not OSI open source |
| Python/package baseline | Evaluate 3.11+ for integrated package, retain current core behavior while deciding | R0 dependency/compatibility results; no global interpreter or package changes |
| Terminal dependency set | Reviewed optional built assets with minimum required upstream closure | R0 import/build audit; retain source attribution, lock and reproducible build recipe |
| Review independence | Required for material work; configured cross-provider policy where supported | Per-task policy and availability, without automatic weakening or new spending |
| Team authority | Local trusted operators, unauthenticated labels, no central service | New requirements for enforced organizational identity need a separate design |
| Pilot success thresholds | Predeclare per-task acceptance; measure all human work, failures and defects | Freeze comparative evaluation before collection; do not fabricate universal productivity targets from a small pilot |

## Authority checkpoints

Implementation can proceed routinely after the corresponding work is authorized, within its stated scope. Consequential changes include a new repository/data source, paid API mode, environment installation/network grant, broader execution profile, publication, or a license choice. Model output, imported code and elapsed waiting cannot authorize those changes.

No push, PR, merge, live inference, credential access, plugin installation or project onboarding occurred as part of this plan. The source-only OpenHarness fetch was used for audit; no upstream code or dependencies ran.
