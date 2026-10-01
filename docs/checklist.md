# Implementation checklist

## Phase 0

- [x] Read and preserve the supplied implementation specification.
- [x] Create a fresh repository, dedicated branch and linked worktree; no remote.
- [x] Pin all three candidate skill repositories to full commits and archive hashes.
- [x] Inspect candidate files, referenced procedures, licenses, manifests and install surfaces.
- [x] Record per-file hashes and adopt/adapt/reject decisions; retain MIT notices.
- [x] Define Phase 1 requirements and threat model; distinguish future enforcement.

## Phase 1

- [x] Ten portable core skills with narrow triggers, prerequisites, outputs and stop conditions.
- [x] Seven initial domain procedures, loaded only when relevant.
- [x] Structured, versioned JSON handoffs and fail-closed offline validation.
- [x] Offline catalog, explicit intent selection, skill rendering and package checks.
- [x] Disposable synthetic tasks, negative contract cases and independent forward evaluation.
- [x] Document adaptations, tested platform, limitations and local PR proposal.

## Phase 2 — feasibility implementation

- [x] Verify exact `72a3ccd` base, clean prior tree and all 29 foundation tests; create separate branch/worktree.
- [x] Read-only doctor with version/feature/auth/sandbox states; no global config changes.
- [x] Provider-neutral v1 records, separate wire adapters, redacted raw evidence and nullable usage.
- [x] Bounded process supervision, cancellation and same-group child cleanup.
- [x] Disposable failure fixtures and independent output oracle; no deliberate live quota exhaustion.
- [x] Real fake-credential, symlink, sibling, common Git metadata, loopback and process canaries.
- [x] One Claude live subscription call; accepted by corrected offline replay, original false-positive record retained.
- [x] Attempt Codex smoke under restrictions; preserve startup failure without relaxing guard.
- [x] Matrix, usage limitations, evidence, decisions and Phase 3 recommendation.
- [x] Both engines complete a disposable live coding task under the follow-up external filesystem guard.
- [ ] Tool-enabled credential/egress isolation: **unsupported**, not implied by native CLI sandbox flags.

## Phase 2 execution follow-up

- [x] Verify clean exact `6bfb981670a1f4e553c870995414452f2ce06b21`; create `implementation/phase-2-execution` in a dedicated worktree.
- [x] Diagnose Codex startup to its writable lock on literal `~/.codex/installation_id`; verify unchanged hash/size/mode.
- [x] Diagnose and narrowly contain Claude session-env and temporary-state writes without changing auth or global settings.
- [x] Complete both live disposable coding tasks and independently verify the exact test command, changed-file manifest and immutable test.
- [x] Deny read/write access to sibling workspace, fake credentials and controller state under the exact external profile.
- [x] Verify timeout, cancellation and TERM-resistant same-group child cleanup under that profile.
- [x] Preserve failed attempts and nullable usage; distinguish Claude CLI cost estimates from billing.
- [x] Approve trusted disposable-workspace mode for Phase 3 design on the tested host.
- [ ] Tool-network separation, comprehensive credential isolation and hostile/untrusted local execution: **blocked**.
- [ ] Detached descendants, remote cancellation and controller crash recovery: **unsupported**.

See [detailed Phase 2 checklist](phase2-plan.md) and [validation report](phase2-validation-report.md).

## Phase 3 — minimum durable delivery workflow

- [x] Verify exact `39afb7feac0bde09fc390b85c4d8c8db83bea0b3`, preserve the clean Phase 2 tree and create `implementation/phase-3` in a dedicated worktree.
- [x] Persist validated task transitions, append-only events, dependencies, revisions, executions, evidence and next actions transactionally in SQLite.
- [x] Keep controller authority out of worker data; worker output cannot change state, reserve budget or record approval.
- [x] Create one controller-owned repository, task branch and worktree; give the implementer a plain tracked-file copy without `.git` and apply only contract-allowed changes through the Git broker.
- [x] Bind verification, review and the local approval package to the candidate revision; revision changes stale prior evidence and approvals.
- [x] Integrate either existing provider adapter as implementer and the other as model-only reviewer; keep deterministic adapters as the default test path.
- [x] Enforce two repairs at most and stop repeated identical findings with a durable checkpoint.
- [x] Reserve calls, concurrency, timeout and elapsed allocations before launch; preserve unknown usage and distinct cached-token categories.
- [x] Reconcile active executions after restart as blocked when process ownership cannot be established; never launch a silent replacement.
- [x] Produce a local summary, diff, revisions, checks, review findings, limitations, resources and proposed PR text, ending at `awaiting_pr_approval` with no recorded approval.
- [x] Test illegal transitions, duplicate/immutable events, concurrent reservations, stale evidence/approval, authority forgery, repair limits, cancellation and restart reconciliation.
- [x] Complete and archive a deterministic disposable workflow through `awaiting_pr_approval`.
- [x] Attempt one bounded live cross-provider workflow: Codex implementation and independent test passed; Claude review failed closed on an expired OAuth token, with no approval package.
- [ ] Complete a live cross-provider workflow through review after the operator independently restores Claude subscription authentication.
- [ ] Crash-safe process containment, detached descendants and remote cancellation: **unsupported**.
- [ ] Broad repositories, hostile code, tool-network separation and comprehensive credential isolation: **blocked**.

## Phase 3 corrective review

- [x] Verify all five review findings against exact commit `17eba897c2cada2957642c36a4c5ddfb5d967a7b`; create `implementation/phase-3-review-fixes` in a separate worktree.
- [x] Attach controller-generated JSON feedback to repair prompts, including structured review findings or bounded failed-test output and acceptance criteria.
- [x] Prove feedback-dependent repair behavior for both failed verification and review findings.
- [x] Run independent tests from a controller-created copy with controller-owned test content under a read-only, no-network Seatbelt profile.
- [x] Scrub the verification environment, replace `HOME`, deny the invoking home plus controller, approval, evidence, repository and worktree paths, and compare both candidate and verification-copy manifests after execution.
- [x] Pass the host boundary regression with disposable controller, approval, Git, worktree and fake-credential canaries; never inspect real credential contents.
- [x] Bind implementer, repair, verification and reviewer reservations/starts to their valid task states; reject terminal and unresolved tasks.
- [x] Add explicit reconciliation resolution that releases the held reservation while leaving the uncertain task blocked.
- [x] Reject Boolean, nonnumeric, zero/negative where invalid, NaN and infinity in controller budget, timeout, elapsed and cost observations.
- [x] Namespace repair/failure event IDs by task and test two tasks with the same signature.
- [ ] Complete a new live cross-provider workflow: **still blocked/unverified because the retained Claude attempt ended with expired OAuth; no authentication change or live rerun was performed in this corrective pass**.

## Phase 3 authentication recovery

- [x] Start from exact `b7ce31826803f640330bd21f879523508d32c0ff` on `implementation/phase-3-auth-recovery` in a dedicated worktree.
- [x] Verify installed Codex and Claude Code login/status help against official provider documentation.
- [x] Support Codex browser/device login and Claude subscription browser login with its official manual code handoff.
- [x] Keep official login in an attached controller-side terminal; never capture its input, output, authorization codes or transcript.
- [x] Reuse working subscription auth and exclude API-key/provider override variables without logging out, moving or reading credential contents.
- [x] Persist a secret-free authentication checkpoint bound to provider, interrupted stage, failed execution, candidate revision and evidence references.
- [x] Coordinate one login per provider/account context, allow two attempts, and keep waiting outside model execution and repair accounting.
- [x] Resume only implementer, repair or reviewer state after subscription status, execution finality, candidate, evidence and reconciliation checks pass.
- [x] Test existing/missing/expired auth, successful stage resume, cancelled/failed/timed-out login, duplicate login, restart, uncertainty, stale evidence, non-auth failures, secret exclusion and accounting preservation.
- [x] Complete the bounded live Codex implementation → constrained verification → Claude review → local approval package demonstration without repeating a successful inference for evidence.
- [ ] Other platforms, remote terminal handoff, custom credential stores and complete login-process credential isolation: **unverified/unsupported**.

## Phase 3 authentication recovery corrective review

- [x] Start from exact `cc7d7587b6f282a8220df1cf159eb04b55314eea` on `implementation/phase-3-auth-recovery-fixes` in a dedicated worktree.
- [x] Replace the per-task checkpoint uniqueness constraint with historical checkpoints plus one active checkpoint per task; migrate schema v2 transactionally.
- [x] Exercise sequential Codex implementation and Claude review authentication failures, preserving both checkpoints and bounded attempts.
- [x] Persist login process ownership and require explicit still-running, confirmed-ended or uncertain reconciliation; never reclaim on elapsed time alone.
- [x] Handle Ctrl+C and launcher failure without starting a duplicate login, preserving uncertain termination when cleanup cannot be established.
- [x] Bind checkpoints to the controller-owned repository, worktree, branch, HEAD, clean status and file-manifest digest and recompute them before resume.
- [x] Reject a dirty candidate before restoring reviewer state or producing an approval package.
- [x] Preserve completed work, resource accounting, secret exclusion and the existing worker/verifier sandbox boundaries.
- [x] Run disposable fixture regressions only; spend no live inference quota.
- [ ] Interactive provider login recovery remains fixture-tested; the successful live delivery reused existing authentication and did not exercise browser login.

## Phase 4 — task intake and selective orchestration

- [x] Start from exact `fa288720c2f1c5e85b33e5ed8a00d88c240f1a77` on `implementation/phase-4` in a dedicated worktree.
- [x] Add a coherent `task` CLI for fixture discovery, intake, plan inspection, execution, status, cancellation, authentication resume and local package reading.
- [x] Preserve the original request separately from explicit assumptions; reject non-fixture targets and authority expansion.
- [x] Define chief-of-staff, tech-lead, manager, implementer, verifier and reviewer responsibilities without starting unnecessary management models.
- [x] Persist bounded graph nodes/edges and require acyclic dependencies, completed prerequisites, isolated specialist worktrees and controller-owned integration.
- [x] Route implementer/repair/reviewer through configurable Codex/Claude account-default profiles, preserving unknown model, effort, relative price and availability.
- [x] Protect separate verification and review call reserves; enforce calls, concurrency, elapsed allocation, timeout, subtasks, repairs, graph size and output bounds.
- [x] Hash and record only selected audited skill/domain content and use structured bounded handoffs instead of transcripts.
- [x] Preserve authentication checkpoints, candidate/evidence revalidation, cancellation and restart uncertainty behavior.
- [x] Test the minimal task path, decomposed integration, invalid graph/authority plans, routing, reserves, repairs, auth recovery, stale revisions, cancellation and unknown usage.
- [x] Include an adversarial worker fixture whose unauthorized file change is rejected by the broker.
- [x] Complete and archive one bounded Codex implementation → constrained verification → Claude review demonstration at the exact integrated candidate, with two inference calls and no repair.
- [ ] General repository onboarding, Linux/GPU workers, dashboards, GitHub publication and broad autonomous execution remain unsupported.

## Phase 4 corrective review

- [x] Start from exact `af807914dc39ef3f9527461ef97e888b860b494d` on `implementation/phase-4-review-fixes` in a dedicated worktree.
- [x] Align the live implementer cancellation interface and exercise actual adapter/request construction with only external transports stubbed.
- [x] Persist decomposed assignment identity before provider launch; validate and reuse it after authentication while preserving completed siblings.
- [x] Cover authentication failure in either text-metrics subtask and reject a changed assignment before restoring task state.
- [x] Propagate requested model and supported Claude effort through implementer, repair and reviewer paths; reject unsupported effort settings.
- [x] Separate requested configuration from nullable provider-reported configuration in execution status and evidence.
- [x] Rehash and assemble bounded role-relevant skill/domain contents into actual provider prompts; reject changed sources and omit unrelated skills.
- [x] Correct scope claims: decomposition is fixture-defined, execution is sequential, management roles are deterministic and routing is not calibrated optimization.
- [x] Preserve the prior live archive unchanged and label it historical evidence for `af80791` rather than validation of the corrected revision.
- [x] Complete the 137-test repository suite with status `OK` and one expected nested-Seatbelt skip, pass that boundary regression separately at host level and pass `agentkit check`.
- [x] Validate exact executable revision `342423ea27700e7d46a977d47e3307bd8fa58c23` in one fresh bounded live calculator workflow: one Codex implementation, one constrained verification and one Claude review reached a candidate-bound local package with no repair or approval.
- [x] Archive sanitized prompts, redacted provider records, controller state, verification, candidate identity/diff, usage and package in a 28-file SHA-256 manifest distinct from the historical `af80791` archive.

## Phase 4 — request-driven planning and bounded concurrency increment

- [x] Start from verified evidence-bearing descendant `41290944ca3a6048e0ed7c3eb85331d028f18a43` with executable baseline `342423ea27700e7d46a977d47e3307bd8fa58c23` on dedicated branch `implementation/phase-4-dynamic-scheduling`.
- [x] Add inspectable request-driven proposals bound to a path/hash/interface inventory, with user requirements separated from assumptions and expected patches excluded.
- [x] Add controller-created small, parallel, ordered and conflicting-requirement project scenarios, including independently testable request-selected subsets.
- [x] Deterministically reject stale inventory, changed acceptance, unsafe paths, cycles, excessive fan-out, overlapping independent writes and call/time infeasibility before execution.
- [x] Launch up to two ready provider assignments concurrently with atomic reservations, separate worktrees/copies, persisted owner identity and controller-only integration.
- [x] Preserve completed siblings through authentication pause; propagate cancellation to both active workers; block uncertain ownership and conservative integration conflicts.
- [x] Add portable routing-registry JSON, dated exact-model evidence, explicit defaults, node/risk/difficulty policies and independent-review exclusion across implementation/repair providers.
- [x] Propagate configured model, supported effort, per-stage timeout and output bounds through actual adapter requests while keeping provider-reported metadata separate.
- [x] Track total/provider/planning calls transactionally and preserve total and provider review capacity under concurrent implementation pressure.
- [x] Extend structured handoffs with interfaces, dependencies, exact revision, evidence references and remaining allocation; retain role-bounded hash-verified skills.
- [x] Add status groups for ready, active, waiting and completed assignments with routing reasons and remaining total/provider budgets.
- [x] Pass 16 focused request-planning/concurrency tests, then the 154-test repository regression suite after the shell-runtime correction (`OK`, one expected nested-Seatbelt skip), and pass `python3 -m agentkit check`.
- [x] Attempt the separately authorized live demonstration against exact executable `b22020c`: two Codex implementations overlapped for 43.367214 seconds; one contribution committed, one produced no change after sandboxed Git/heredoc failures, and the controller blocked before integration, verification, review or packaging without retry.
- [x] Preserve sanitized requests, redacted events, results, controller state, contribution diff, usage and preflight in a hash manifest; record that no approval was created.
- [x] Correct the narrow owned-code compatibility gap at `b9df1ad` by routing zsh `TMPPREFIX` into the disposable runtime and allowing only the literal `/dev/null` sink; pass a host no-inference canary while retaining protected-path denial.
- [ ] Complete a future bounded concurrent live workflow against the corrected executable. The `b22020c` attempt does not validate `b9df1ad`, and no additional inference was authorized or used for the correction.
- [ ] General repositories, detached-process containment, Linux/GPU/remote workers, dashboards and publication remain unsupported.

## Phase 4 — dependency, claim and request correction

- [x] Assemble each dependent assignment from validated predecessor deltas in deterministic graph order and record its actual starting revision plus dependency revisions.
- [x] Measure worker changes against that assembled start and integrate each assignment's own delta once, preserving dependent overlays while rejecting independent conflicts.
- [x] Add a behavioral regression whose downstream worker succeeds only after reading predecessor content created at runtime.
- [x] Atomically claim an exact pending/failed implementation selection with status, version, attempts, dependency, cancellation and ownership checks.
- [x] Remove the generic direct `succeeded → running` transition and retain explicit quality-stage resets.
- [x] Add a synchronized stale-selection regression proving one provider invocation and preservation of the winning result.
- [x] Reject unmatched requests rather than falling back to fixture tasks; require clarification for negated or contradictory matched requirements.
- [x] Pass 19 focused dynamic-scheduler tests, all 41 Phase 4 tests, the 157-test repository suite (`OK`, one expected nested-Seatbelt skip), and `python3 -m agentkit check`; use no live inference.

## Phase 4 — bounded static-web product acceptance

- [x] Add one accounted provider tech-lead planning path for a product brief, protected acceptance, bounded inventory, capabilities, verified planning context and resource limits.
- [x] Reject planner authority expansion, changed requirements/acceptance, stale inventory, unsafe paths, unsupported operations, inconsistent interfaces/dependencies, cycles, excessive fan-out, independent path overlap and infeasible calls/time.
- [x] Create a fresh dependency-free static project separate from harness source, controller state, evidence, approval data and controller-owned acceptance.
- [x] Reuse the durable scheduler, dependency snapshots, isolated assignments, integration, routing, authentication recovery, cancellation, bounded repair and usage accounting without a product-specific task graph.
- [x] Pin the installed Node executable, copy it into the verifier runtime, run the documented syntax build plus protected mechanics test in a separate candidate copy and confirm the candidate remains unchanged.
- [x] Gate packaging on exact-revision browser observations covering every predeclared criterion and on confirmed cleanup of the owned loopback preview.
- [x] Add `product submit|plan|start|status|cancel|resume|preview-serve|browser-record|package` and document the exact live budget interface; the foreground preview retains one owner through Ctrl+C.
- [x] Pass nine focused product tests; the loopback lifecycle case is explicitly skipped inside the managed outer sandbox and passes separately at host level with confirmed foreground cleanup.
- [x] Commit reusable executable `70070e293c890a5c47bbb448b99a9b7cf34f8237` before inference and declare the eight-call, two-worker, two-repair, 180-second-per-provider and 1,200-second overall ledger.
- [x] Attempt one bounded Breakout trial. The sole Claude planning invocation ended after 29.313421 seconds because its response exceeded the adapter's 512 generated-output-token allocation; stop without retry or provider substitution.
- [x] Retain sanitized planning request/result/events, controller state, inputs, versions, usage and failure diagnosis in a hash-manifested archive; no browser/game artifacts exist because planning was not accepted.
- [x] Apply the original interim planner correction at 8,192 and classify output-limit text before allowed rate metadata; this allocation is superseded by the later CLI resource-policy audit below.
- [ ] The corrected product planner remains live-unvalidated. Do not use the failed `70070e2` attempt as validation or repeat inference without new authorization.
- [ ] Dependency installation, general repositories, hostile inputs, arbitrary builds, browser credential/egress isolation and crash-safe preview containment remain unsupported.

## Phase 4 — CLI integration and resource-policy correction

- [x] Start from merged `main` revision `c894a7e2977d09362fcf425fa9cc46e2144046c0` on dedicated branch `correction/cli-resource-policy` and isolated worktree.
- [x] Audit installed Codex CLI 0.154.0 and Claude Code 2.1.220 help plus official CLI/configuration documentation.
- [x] Remove the productive Claude 8,192 output setting and confine the historical 512/one-turn/zero-retry environment to `smoke-model-only`.
- [x] Remove the universal 300-second request/transport ceiling; keep finite positive controller deadlines bound by each task's authorized overall allocation.
- [x] Resolve task overrides, role policies and provider defaults with persisted source, enforcement class and rationale.
- [x] Keep captured bytes distinct from generated tokens and provider token/cost observations.
- [x] Record one CLI launch separately from unknown internal provider requests and turns.
- [x] Add bounded output-exhaustion recovery that changes/removes an imposed control, consumes the same call/time ledger and refuses identical/provider-default retries.
- [x] Add explicit structured-planning, code-implementation, web-product-implementation and independent-review capability profiles.
- [x] Allow Claude file creation while granting only role-specific Bash patterns; retain external Seatbelt, broker, credential and publication boundaries.
- [x] Add focused offline tests for policy precedence, request construction, capability selection, parsing and recovery; pass 177 repository tests with two expected managed skips, then pass both checks separately at host level and pass `agentkit check`.
- [x] Attempt and archive the authorized direct-versus-adapter checkpoint: both Codex planning paths passed; both Claude implementation paths failed with expired OAuth; stop after four of six launches without retry, login, provider substitution, review or game inference.
- [x] Preserve complete terminal usage/retry/turn observations after monitored failures in offline-tested revision `1c0008c`; do not promote that correction to live-tested status.
- [x] Bind all 22 retained checkpoint files by SHA-256 and pass the final 182-test suite with two expected managed-environment skips plus `python3 -m agentkit check`.
- [ ] Complete Claude implementation and independent-review comparison under a future bounded authorization after authentication is restored.
- [ ] The Breakout product trial remains the next acceptance milestone after provider integration completes; no game inference was spent during this checkpoint.

## Repository-first product planning — 2026-10-01

- [x] Preserve corrective baseline `ddf6145002efd0bd59b85d54996263f6edb7f675` in dedicated `planning/reuse-first-product` worktree.
- [x] Record the user's priorities: both existing repositories and new products, existing repositories first; small engineering teams and some public open-source users.
- [x] Review the supplied product vision against current implementation and primary sources; separate supported claims from proposed positioning.
- [x] Pin OpenHarness to `9b2efd795c6aa09f88b0c257d269a9e518da6ae7`; inventory 50 source/config/test files without importing or executing upstream code.
- [x] Produce a module-level substantial-reuse map, license/dependency adoption gates, architecture alternatives and a working reuse-spike specification.
- [x] Draft repository enrollment, policy, verification, evidence, team UX, migration, milestone and ticket contracts in the [engineering plan](planning/engineering-plan.md).
- [x] Separate user decisions, engineering recommendations and remaining decisions in the [planning register](planning/decisions.md).
- [x] Implement and evaluate P01–P04 as R0: attributed profile/context/protocol/fs ports, dependency-free terminal renderer and a deterministic existing-controller vertical slice.
- [x] Preserve the complete OpenHarness MIT text, file hashes, adaptation decisions and selected dependency/license closure without installing upstream packages.
- [x] Demonstrate complete, cancelled, authentication-wait, candidate-stale and unknown-usage presentation; reject changed profiles and UI authority expansion.
- [x] Pass 10 focused Python tests, 4 Node tests, the 192-test repository suite (190 passed, two expected nested-environment skips), both skipped checks separately at host level, and `agentkit check`.
- [ ] Build the optional React/Ink TUI only after reviewing its complete locked license/install closure; R0 ships an executable dependency-free terminal slice.
- [ ] Validate real-repository onboarding and execution before exposing it; existing disposable macOS limitations remain.
- [ ] Complete remaining provider integration under a future declared authorization; no live inference belongs to this planning task.
- [ ] Select the distribution license and pass packaging/dependency gates before public distribution.

The [new product plan](planning/README.md) proposes repository-first sequencing. The older phase list below is retained as historical roadmap context; it is not a requirement to build a GPU worker before repository onboarding. Breakout remains a later new-product acceptance case, following the user's updated priority.

R0 accepts architecture option B: a component port around the durable AgentKit controller. R1 implements the read-only repository-intake boundary on disposable fixtures. It does not validate repository import or execution; R2 is the next planned boundary.

## R1 read-only repository intake

- [x] Add bounded standalone Git identity, revision, inventory and raw clean-state inspection without `git status` or project execution.
- [x] Reject config includes, alternates, shared/symlinked metadata, dirty baselines, submodules, symlinks, LFS, transforms and unsupported object formats.
- [x] Add a strict Python-library profile schema whose checks are proposals and whose execution flag must remain false.
- [x] Persist private enrollment records outside the project, bound to root, inode, branch, revision, inventory and profile hashes.
- [x] Revalidate actual repository state before producing request-sensitive read-only plans; stale enrollment blocks.
- [x] Test hooks/filters not executing, authority expansion, tampering, bounded input, multiple repository shapes and CLI behavior using disposable fixtures.
- [x] Pass 10 focused R1 tests, the 204-test suite with two expected outer-sandbox skips, both host checks separately, 4 terminal tests, `agentkit check`, Python 3.9 compilation and diff hygiene.
- [x] Implement the R2 independent importer, prepared environment and generalized verifier on disposable enrolled repositories.
- [ ] Validate an explicitly authorized real repository separately; disposable fixtures do not establish general compatibility.

## R2 safe repository delivery

- [x] Reconstruct enrolled bytes and executable modes in an independent controller-owned repository without clone, remotes, alternates, inherited templates or hard links.
- [x] Reinspect source identity/content before and after import; reject stale state and tracked excluded content without touching the original.
- [x] Require separate controller-side execution authorization; keep R1 enrollment and task/model text non-authoritative.
- [x] Resolve prepared Python/check recipes without installation or network and block unprepared third-party imports.
- [x] Ground narrow requests in enrolled filenames/content and require clarification for unmatched or contradictory requests.
- [x] Supply revision-bound structured handoffs without expected patches or protected acceptance source.
- [x] Run existing checks plus protected acceptance, reject empty collections, stale candidates and source/check mutation, and bind evidence to the exact head.
- [x] Produce a deterministic local approval package through the existing transactional controller and Git broker with approval unset.
- [x] Preserve dependency, stale-claim, cancellation and authentication-history regression families.
- [x] Pass 11 focused tests, the 215-test repository suite (212 passed, 3 expected managed-environment skips), all three skipped checks separately at host level, 4 terminal tests, `agentkit check`, compilation and diff hygiene.
- [ ] Validate live Codex/Claude execution and guided authentication recovery on the repository-delivery adapter under a separately declared allowance.
- [ ] Add the complete plain/JSON/terminal package workflow in R3; no original-repository application or publication exists in R2.

## AgentKit brand rename

- [x] Adopt **AgentKit** as the product and display name in active documentation, CLI help and the adapted terminal.
- [x] Preserve the `agentkit` command, Python module, artifact paths and temporary prefixes as stable lowercase technical identifiers.
- [x] Preserve historical worktree/repository references and the versioned `urn:portable-agentkit:handoff:1` schema identifier.
- [x] Rename the separately authorized GitHub repository to `adityachaturvedii/AgentKit`, update `origin`, and verify the former name resolves to the canonical repository.
- [ ] Select the outbound license before public distribution; the brand rename does not resolve licensing.

## R3 portable package

- [x] Export an exact-revision `awaiting_pr_approval` R2 result to a fresh private plain folder without recording approval or publication authority.
- [x] Include a sanitized summary, full diff, requirement matrix, passed verification/review records, limitations, resource observations, provenance and replay guidance.
- [x] Verify hashes, sizes, paths, file inventory, revision bindings, evidence status/kind, requirement mapping and diff consistency offline without executing candidate code.
- [x] Reject tampering, extra files, symlinks, traversal, stale/missing/failed evidence and malformed internal JSON in disposable regressions.
- [x] Pass 8 focused package tests, the 235-test suite (232 passed, 3 unchanged managed-environment skips), structural checks, compilation with a workspace-safe bytecode cache and diff hygiene; use no inference.
- [x] Complete P12's equivalent plain, JSON, protocol-event and dependency-free one-shot terminal workflow for existing Phase 4 disposable tasks.
- [x] Keep start/resume authority in CLI construction flags; reject live mode without explicit authorization and prevent task text or frontend events from granting it.
- [x] Expose status, start, resume, cancellation and bounded package summary through one allowlisted frontend without adding approval, publication or replay authority.
- [x] Document that the terminal is one-shot rather than a full-screen interactive TUI, and preserve unknown usage and explicit next action across views.
- [x] Pass 23 focused Python workflow/protocol tests, 8 dependency-free Node tests and the 248-test suite (245 passed, 3 unchanged managed-environment skips), plus structural checks, compilation and diff hygiene; use no inference.
- [ ] Complete P13 distribution/compatibility work and any separately audited optional full-screen TUI.
- [ ] Add signed provenance or authenticated team approvals; manifest integrity is currently unauthenticated.

## Later phases (historical plan, not implemented)

- [ ] Phase 5: hardware domain validation and optional GPU worker.
- [ ] Phase 6: GitHub broker, installation/update/rollback and machine handover.
- [ ] Phase 7: held-out matched baseline evaluations and calibrated release.

## Project documentation

- [x] Preserve the historical public README redesign from `afad0a7` in branch ancestry; its layout predates the current mainline documentation and is not a claim about the active README format.

## Exit status

Phase 0 complete. Phase 1 offline foundation complete on the observed macOS/Python environment. All ten procedures were exercised across invoice, independent-review and optimisation development cases. Review found two outcome contradictions; both were fixed and independently rechecked. Required browser/GPU/provider boundaries remain explicitly unverified and are later-phase gates, not Phase 1 passes. The external skill-creator validator was unavailable due to missing PyYAML; local pack checks passed.

Phase 2 implementation and authorized feasibility experiments are recorded. Both engines now pass the trusted disposable-workspace coding fixture on the tested macOS host. No merge, push, PR, global CLI edit, plugin installation, GPU connection, API-key introduction or billing change occurred in the follow-up. Phase 3 may begin only for that narrow mode; untrusted or broad local execution remains blocked.

Phase 3 now implements the minimum local delivery graph for that narrow mode. R3 P11 additionally exports its exact-revision result as a sanitized, offline-verifiable review folder; complete terminal workflow and distribution work remain open. After the corrective review, the deterministic workflow reaches a revision-bound `awaiting_pr_approval` package and the regressions cover controller, Git, repair feedback, constrained verification, budget, numeric, lifecycle, restart and evidence invariants. The bounded live attempt validated Codex implementation plus an independent test, then blocked when Claude reported an expired OAuth token. No reauthentication was attempted, no billing fact was inferred, and no live approval package was created. Phase 4 should wait for a successful cross-provider live review and remains limited to trusted controller-created disposable repositories.

The authentication-recovery follow-up supersedes that live gate: guided first-party subscription recovery is implemented and 107 tests pass, including the host macOS boundary test. One fresh bounded live workflow reached `awaiting_pr_approval` with Codex implementation, constrained local verification and Claude review. Existing authentication worked, so no interactive login was launched. A strict offline correction accepted Claude's single fenced JSON result after verifying its archived stream hash, provider-success terminal, candidate and snapshot, avoiding any repeat inference. Phase 4 may begin only for the same trusted disposable macOS mode; all broader limitations remain.

Phase 4 now provides fixture-only natural-language intake, a reviewable plan, selective persisted role graphs, configurable account-default provider routing, separate verification/review reserves, active cancellation and a terminal status/package experience. The final suite passed 131 tests with one nested-sandbox skip, and the host boundary regression passed separately. One live two-inference-call workflow reached a clean revision-bound local package. General repositories, additional platforms, GPU/remote workers, dashboards and publication remain future gates.

The Phase 4 corrective review fixes the live cancellation interface, decomposed authentication resume, requested model/effort propagation and verified worker skill context. The corrected revision completes its 137-test repository suite with status `OK` and one expected nested-Seatbelt skip; the skipped boundary test passes separately at host level. The earlier live package remains historical evidence for `af80791`. No live inference was used for the correction, so the corrected live implementation → verification → review path still needs one future bounded validation.

The corrected Phase 4 live gate is now complete for exact executable revision `342423ea27700e7d46a977d47e3307bd8fa58c23`. Under a three-call/130-second controller budget, one Codex implementation, one constrained verification and one Claude review reached `awaiting_pr_approval` at disposable candidate `ee3f6ffc260f6cf1ee5537db1913debb0f4168ff`. Only `calculator.py` changed, both prompt hashes matched the recorded role-specific contexts, verification and review passed, no repair/login/publication ran and no approval was recorded. Broader platforms, repositories and isolation claims remain unchanged.

The next Phase 4 increment replaces fixture-ID-only sequential decomposition with request/inventory-bound plans and a two-worker scheduler. Offline behavioral coverage proves synchronized overlap, dependency gates, duplicate-controller suppression, sibling authentication progress, two-worker cancellation, conservative conflict blocking, provider-review reservation and actual adapter-request propagation with only external transports stubbed. Its executable revision still requires the separately authorized bounded live parallel demonstration; the earlier calculator archive is not repeated or promoted to validate this increment.

The bounded concurrent live attempt used exact executable `b22020c` and launched only its two authorized Codex implementation calls. The executions overlapped, proving the live scheduler path, and the word contribution was broker-committed. The line worker then produced no change because zsh heredoc temporary files and Git's `/dev/null` sink were denied by the owned-code profile. The controller blocked safely with the main candidate unchanged; verification and Claude review did not run, no package or approval was created, and no repair/retry/escalation occurred. The narrow correction is committed at `b9df1ad` and passes 154 tests plus a host no-inference boundary canary, but remains live-unvalidated.

The dependency/claim/request corrective milestone is committed at `dd8da0e`. The next local increment adds only the bounded dependency-free static-web profile described above. Offline evidence establishes proposal validation, protected mechanics verification, revision-bound browser gating and adapter request construction. It does not yet establish that the live Breakout trial, browser interaction or host preview succeeds; those remain separate validation steps against the committed executable revision.

The first authorized Breakout trial tested exact executable `70070e2` and consumed one Claude planning call. Claude generated partial plan text but terminated with an API error after exceeding the adapter's 512 generated-output-token allocation. The task failed closed in `blocked` before a plan, workspace or candidate existed. No Codex call, local verification, repair, review, preview, browser interaction, package, approval or publication occurred. The adapter recorded the failure as `rate_limit` because an allowed rate metadata event appeared in the same stream; retained terminal evidence establishes an output-allocation failure instead. The provider reported 8 input, 2,048 output, 25,570 cached-input and 9,678 cache-creation tokens, plus a USD 0.160805 estimate. Reasoning tokens and billed cost remain unknown.

Publication follow-up, 2026-09-19: the user subsequently authorized creating a private GitHub repository and pushing all committed toolkit branches. This supersedes the local-only publication restriction without changing the Phase 2 findings or granting PR/merge permission. See D025 in the [decision log](decisions.md).

## Integration branch reconciliation

- [x] Compare every local/remote branch tip and check all AgentKit worktrees for uncommitted work.
- [x] Prepare a normal merge of `origin/main` (`3ea1416`) into a dedicated branch based on `origin/implementation/phase-2` (`2d0a078`), retaining R0–R2 and the older documentation history.
- [x] Resolve documentation conflicts without reverting the AgentKit name or later capability documentation; preserve the earlier colliding decision as D111.
- [x] Record feature PR → `implementation/phase-2` → separate release PR → `main` in AGENTS.md.
- [x] Independently review the staged reconciliation with GPT-5.6 Sol at medium reasoning; verify all files except AGENTS.md and these checklist/decision records equal `origin/main`.
- [x] Run offline validation: 215 regression tests, 212 passed and 3 skipped (two Seatbelt initialization checks and one loopback preview check unavailable inside this execution environment); structural `agentkit check` and both branding tests passed. No live inference or new sandbox validation claimed.
- [x] Publish and merge the authorized reconciliation PR #10 into `implementation/phase-2` (`ade1103`).
- [x] Merge the authorized release PR #11 from `implementation/phase-2` into `main` (`c932f87`); both trees match the tested reconciliation.
- [ ] Address the R2 review findings; branch reconciliation does not close them.
- [ ] Review/correct `fix/process-group-liveness` separately; its code is not included in this reconciliation.

## R2 corrective gate

- [x] Revalidate the actual managed repository, branch, HEAD and clean worktree after review and before packaging; a reviewer-time candidate commit now blocks without an approval package.
- [x] Enforce `cross-provider` repository profile requirements before creating a task; implementation and review cannot use the same provider or adapter identity.
- [x] Route `LiveImplementer` and `LiveReviewer` through their real request contracts, owned-code boundary/model-only review profile, configured model/effort and explicit `LivePolicy`; tests stub only external transport.
- [x] Create revision-bound authentication checkpoints for implementation and review failures; preserve passed verification as a reviewer-checkpoint evidence reference.
- [x] Add a durable repository-workflow reopen/resume entry point that revalidates private persisted inputs plus the actual candidate, continues only implementation or review, preserves completed verification and counts failed provider attempts within a five-call bound.
- [x] Exercise sequential Codex implementation authentication followed by Claude review authentication across two reopen cycles; retain one verification record, two historical checkpoints and exactly five counted executions.
- [x] Place native verification candidates under a controller-created `/private/tmp` root so denying the real home directory does not deny the candidate itself.
- [x] Inspect standard-library extension modules with the selected prepared interpreter; `math` remains ready while undeclared `requests` remains `environment_required`.
- [x] Run the complete 222-test suite (3 managed-environment skips), then 42 focused repository/Phase 3 regressions after final temporary-root hardening (2 nested-Seatbelt skips); structural checks, Python 3.9 compilation and diff hygiene passed.
- [ ] Perform a separately authorized live repository-provider run after offline resume regressions pass; this change uses simulated provider transports only.

## README presentation restoration

- [x] Restore the public README structure from `afad0a7`, keeping AgentKit branding and incorporating later implementation, resource policies, reuse/intake work and unresolved review findings (D113).
- [x] Verify the documented submit → plan → start → status → package commands using a fresh deterministic calculator fixture; status reached `awaiting_pr_approval`.
- [x] Verify the text-metrics proposal and OpenHarness reuse demo with disposable output; no provider calls.
- [x] Resolve all 32 local README links; pass two branding tests, offline structural checks and whitespace hygiene. Runtime code is unchanged; the earlier 215-test reconciliation result remains historical evidence.
