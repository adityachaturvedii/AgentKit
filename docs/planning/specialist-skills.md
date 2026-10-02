# Specialist agents and skills

Status: the versioned specialist/profile foundation and the first four skills are implemented and fixture-tested. Additional specialist performance, `frontend-implementation` and `design-review` remain proposed and are sequenced in the [backlog](refinement-backlog.md).

## Three distinct concepts

- **Role** defines responsibility and the controller's execution/state gate: planning, implementation, repair, verification, review. Deterministic coordination remains controller code.
- **Specialization** selects task-relevant expertise, an output schema and an eligible model/capability profile. It does not create filesystem or spending authority.
- **Skill** is a versioned procedure plus necessary references/helpers. Load only content relevant to the assignment. A skill is neither an executable permission nor an independent agent.

No worker can create another worker, enlarge an allocation, approve a candidate or publish. A specialist may propose a new assignment; the controller must validate the graph, authority, independence and remaining budget before scheduling it.

## Specialist contracts

All specialists receive a structured handoff with requirement/assumption sources, current scope, base or candidate revision, dependencies, relevant evidence, selected skill hashes and remaining allocation. They return schema-validated output; success claims do not change controller state.

| Specialist / activation | Inputs and output | Skills | Tools and scope | Completion / escalation |
|---|---|---|---|---|
| Product shaper — material ambiguity in a product brief | Brief, audience, constraints, inventory → primary user/job, critical flows, assumptions, prioritized scope, observable acceptance proposal | Existing `task-contract`; new `product-shaping` | Structured planning; bounded supplied context; no product writes | A buildable small scope, or one material question; escalate conflicting requirements/authority/cost |
| Tech lead — nontrivial interfaces or decomposition | Frozen intent, inventory, capabilities → assignments, path ownership, interfaces, dependency graph and integration strategy | `system-investigation`, `interface-design`, `change-impact`, as relevant | Structured planning, no shell or arbitrary repository access | Feasible validated DAG; escalate unsupported tools, overlaps, budget insufficiency |
| UX/visual designer — new UI or meaningful interaction change | User flows, brand constraints, design baseline → information hierarchy, chosen visual direction, tokens, layout, states, accessibility targets | New `interaction-design`, `visual-design`; frontend procedure | Model-only design; supplied references must be authorized and hash-bound | Specific implementable design and rationale; escalate material direction choice, not every color |
| Frontend engineer — supported static UI | Design brief, allowed product manifest, technical contracts → HTML/CSS/JS contribution and actual local-check results | `behavioral-testing`, new `frontend-implementation`; relevant design references | Approved web implementation profile; one isolated copy, pinned available tools | Scoped broker-accepted delta; self-check failures reported honestly; no protected-test source |
| Python engineer — supported repository/library work | Scoped source snapshot, contracts, enrolled check recipes → Python change and regression tests | `fault-diagnosis` when debugging, `behavioral-testing`, `change-impact` | Approved Python profile, prepared environment, isolated copy | Scoped delta, nonempty checks; escalate missing dependencies or incompatible interfaces |
| Acceptance engineer — no adequate independent oracle exists | Frozen requirements, public interfaces, approved test runtime → independent acceptance proposal and calibration cases | New `acceptance-design`, existing `behavioral-testing` | Separate test-authoring scratch copy; no candidate implementation, no controller DB/test write access | Positive/negative controls, failure semantics, requirement mapping; controller validates and freezes before use |
| Code reviewer — required quality stage | Immutable integrated snapshot/diff, requirements, tests/evidence → concrete findings by criterion/path/severity or explicit none | `independent-review`, relevant domain/impact references | Existing model-only independent-review profile, bounded supplied code; no mutation | Evidence-backed actionable findings; escalate incomplete review context or required independence unavailable |
| UX/accessibility reviewer — material user-facing work | Design brief, exact candidate, trusted browser observations/screenshots → reproducible interaction defects and clearly labeled visual judgment | `browser-verification`, new `design-review`; accessibility references | Read-only evidence/model review; actual browser actions belong to separately controlled driver | Criterion-bound findings; never infer browser success from screenshots or source alone |

**Conditional overlays:** security review for concrete new trust/data boundaries; performance analysis for measured latency/resource requirements; documentation/release writing for substantial public usage changes. Reuse `change-impact`, `measured-optimisation`, `delivery-evidence` and relevant domain procedures. Defer separate autonomous agents until evidence shows their benefit. Do not inject ML/CUDA guidance into ordinary web work just because the catalog contains it.

**Chief of staff and manager:** deterministic intake/status/escalation and scheduling/accounting. They do not consume ceremonial model calls. Product shaper and tech lead may share one bounded planning execution when their deliverables fit; the controller records that explicitly. An independent reviewer must remain separate from implementation even if the same session could answer both prompts.

## Skill work

Preserve the ten existing audited skills and their source/license attribution. Do not rename `interface-design` into a visual-design skill: it currently describes caller contracts and ownership and is useful in that role. Distinguish it in the UI as “API and interface contracts.” New skills below are proposals, not catalog entries yet.

| Proposed skill | Non-obvious guidance to include | Forward-test outcome |
|---|---|---|
| `product-shaping` | Convert vague ambition into a specific user/job, critical journey, assumptions, exclusions and observable acceptance; distinguish material ambiguity from reversible choice | Two materially different briefs yield different justified scopes; contradictory brief asks one useful question; no invented product requirements |
| `interaction-design` | Map primary flow plus empty, invalid, loading when applicable, success and recovery states; specify keyboard/focus and responsive behavior | Flow is executable by an implementer, with no omitted reset/error/focus semantics |
| `visual-design` | Derive hierarchy, typography, spacing, color, layout and component behavior from audience and visual intent; use existing brand if present | Different chosen directions remain distinguishable; outputs are concrete tokens/components rather than “make it polished” |
| `frontend-implementation` | Implement design contracts within the actual prepared profile; semantic HTML, deliberate responsive behavior, local asset/runtime constraints | Real worker input contains design and scope; generated delta honors them and reports checks actually run |
| `acceptance-design` | Derive expected results independently; validate nonempty discovery; distinguish runtime/test-harness/product failures; handle cross-realm JS objects/errors | Known-good control passes, intentional defect fails, broken harness errors distinctly; no expected-patch leakage |
| `design-review` | Compare exact candidate observations with chosen direction; separate usability/accessibility defects from preference and suggested scope additions | Reviewer cites actual elements/flows/evidence; missing viewport/focus evidence stays unknown; no ungrounded “looks good” pass |

The first three plus acceptance design are now bundled and hash-verified in worker context. Existing behavioral/frontend procedures remain in use until implementation and review gaps justify separate `frontend-implementation` or `design-review` skills. Skill count is not a success metric. Combine or drop a proposed skill if forward tasks show no useful distinction.

Bundle new files within the AgentKit repository, never the operator's global skills directories. Audit any imported material for source pin, license/dependency closure, adaptations and tests before adoption. The planning methodology uses the local skill-creator guidance (concise discriminating triggers, progressive disclosure, behavioral validation); no global skill content is copied into the runtime by this plan.

## Proposed serialized records

Add these as versioned validated records with size/type/path bounds and unknown-field rejection where authority is involved. Names are schema design, not current APIs.

`SpecialistProfile`: ID/version; base role; specialization; activation criteria; required capabilities; output schema ID/version; eligible model profiles; default skill IDs; context policy; completion and escalation rules. Tools are references to controller-owned capability profiles, never executable commands from model output.

`SkillBinding`: skill ID/version; relative source path; SHA-256; source/license reference; selected role; reason; loaded references and their hashes; encoded byte count. Persist the exact loaded bundle identity. Resolve only regular contained files, reject symlinks/path escapes, and rehash at dispatch and supported resume. A changed bundle requires explicit context/plan re-resolution; never quietly load new content into an old assignment.

`DesignBrief`: intended audience/job; prioritized flows; selected direction and rationale; token/component/layout/state specifications; responsive/accessibility criteria; required local assets with provenance; assumptions; non-goals; acceptance IDs. Cosmetic choices are reversible assumptions unless the user's brief makes them requirements. Do not require two designs for a routine UI fix. Where direction is consequential, show at most a small inspectable set before implementation.

`AcceptanceSpec`: requirement IDs and source; checks classified as existing repo / agent-proposed / protected independent / browser / manual; expected values/origin; runtime/profile; allowed argv and bounds; oracle version/hash; positive/negative controls; coverage gaps. Model-written tests remain untrusted proposals until controller validation and independent calibration, and that validation is not proof of universal correctness.

`SpecialistHandoff`: task/node/attempt, base role/specialization, requirement/design/acceptance hashes, workspace identity, own starting revision and predecessor contributions, allowed paths/tools, interfaces, selected skill bundle, relevant findings/evidence, allocation ID and next action. Include summarized decisions, not complete transcripts. Workers get public acceptance criteria and interface examples, not the hidden independent oracle or fixture solution.

Durable memory is initially task-scoped decisions and evidence plus trusted enrolled project conventions. Agent summaries are advisory and traceable to source artifacts. Do not add automatic cross-project transcript memory or let a remembered preference become authorization. A skill revision based on observed outcomes is a separately reviewed repository change, not a worker silently rewriting its instructions during a run.

## Controller-enforced team selection

1. Classify supported target and required capabilities deterministically; ambiguous interpretation may consume one reserved shaping/planning call.
2. Select the minimum set of responsibilities. Small Python bug: Python engineer + protected verifier + independent reviewer. Material static product: shaping/design (combined when feasible), frontend implementation, protected mechanics/browser checks, independent code review; visual critique only if needed and budgeted.
3. Validate paths, graph, mandatory stages, model availability and contribution-based review independence. Preserve up to two concurrent providers and two implementation assignments. Two jobs overlap only with independent writable scopes; downstream workers receive actual predecessor output.
4. Reserve every launch atomically. Design critique and escalation cannot consume mandatory verification/review capacity. At most two repair invocations initially within the same total allowance; repeated identical evidence stops. A provider change needs an eligible configured route and must preserve independence, never paid fallback.
5. Validate structured output and broker observed changes. Completed artifacts are reusable only while their candidate/requirements/context identities remain valid.

Model choice uses required capability/context, task complexity, risk, configured preference, availability and remaining budget. Task outcomes are recorded per specialist+skill+model+runtime identity. Do not attach “cheap,” “best designer” or “most capable” labels without comparable dated evidence. Requested model/effort remains separate from what the provider reports.

## Acceptance ownership and recovery

Acceptance preparation must finish and be frozen before implementation. A model can propose tests in a separate scratch assignment, but only the controller can install a validated immutable version. The acceptance engineer cannot mark its own tests passed, edit the implementation or silently change success criteria. For new behavior absent from the seed, use separately controlled positive examples and intentional counterexamples; requiring the unfixed seed to pass is wrong.

Failure classification distinguishes implementation defect, test-harness/runtime error, authentication, quota, permission/isolation, timeout, cancellation and unresolved process ownership. An ambiguous assertion stays unclassified rather than being assumed a product defect or automatically weakening the oracle.

Correcting an oracle is not an ordinary worker repair. Preserve the failed artifact; create a controller-authorized new oracle version with a reason and reviewed delta, calibrate it, revalidate the actual clean candidate and all referenced identities, and invalidate affected verification/review/approval. Re-execute only necessary quality stages within remaining authorized budget. Requirements must remain unchanged; a change to acceptance semantics requires a new contract revision and meaningful user decision. Never add a generic unblock operation, reset retry history or promote external diagnostic results to authoritative passes.

## Skill evaluation and graduation

Each proposed skill needs positive, negative-trigger, ambiguous and adversarial fixtures; strict output validation; actual assembled-request coverage; changed-hash rejection; bounded context tests; no secret/authority expansion; and an independent forward exercise whose expected answer is withheld from the specialist. Fixtures should include the last VM oracle defect and the unavailable-worker-Node condition.

Compare skill-guided and unguided work on predeclared held-out tasks when live evaluation is separately authorized. Record all attempts, revisions, provider/model/effort, checks, human corrections, irrelevant context, clarification burden and concrete defects. Blind visual comparison can assess design preference, but it does not substitute for interaction/accessibility checks. Retain/drop decisions are qualitative until there is adequate comparable evidence.

Promotion levels: authored → structurally validated → behaviorally fixture-tested → host-tested where tools apply → live-tested on named revisions → pilot-supported. Display these labels in the skill registry and avoid blanket “expert agent” claims.
