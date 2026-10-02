# Realistic focus-board product trial

Date: 2026-10-02. Executable revision: `fcaf591466b2d40c690cb304d3eadc9fb0e7cef3`. Evidence: [`evidence/refinement-realistic-focus-board`](../evidence/refinement-realistic-focus-board/manifest.json).

## Purpose and boundary

This was a live product-use trial rather than a fixture demonstration. The request asked AgentKit to plan and deliver a polished, persistent daily focus board from a plain product brief. Controller-owned acceptance covered task mechanics, persistence, keyboard and touch interaction, responsive layout, accessible instructions and local operation.

The declared allowance was four provider launches total, one concurrent worker, at most one repair, 300 seconds per provider stage, 30 seconds for local verification and 1,200 seconds overall. The run used existing subscription authentication only. The corrected executable was clean and unchanged throughout both attempts. No push, PR, merge, deployment, API key, billing change or provider substitution occurred.

## Result

The workflow **did not complete end to end**. It stopped during planning after two Claude CLI launches. No Codex implementation, candidate revision, local verification, browser interaction, independent review or approval package exists.

The first planning launch ended after 3.214 seconds with an actual 401 response stating that the OAuth access token had expired. The preceding official status command had reported a verified Claude subscription. AgentKit classified the failure as authentication and stopped, but its guided login command had no force-refresh option and would have reused the stale status result. The operator completed the official `claude auth login --claudeai` flow directly. No login URL, code, credential or raw interactive transcript is retained.

Because planning failed before a task contract and authentication checkpoint existed, AgentKit could not resume that stage. A fresh controller root was required. The second planning launch completed after 88.654 seconds. Claude returned a detailed single-assignment plan, but appended prose after the JSON fence, so the strict normalizer produced no structured object. Independently, the fenced object added a second record labeled as a user requirement. The controller requires `requirements` to equal the original brief exactly, so the proposal would still have been rejected after extraction. AgentKit correctly did not reinterpret or silently edit untrusted model output.

Two authorized launches then remained while planning, implementation and independent review still required three provider launches. The controller did not start another process.

## Harness findings

### Confirmed working

- Exact executable revision and a clean validation worktree were checked before live execution.
- The macOS Seatbelt diagnostic and subscription-only CLI preflights passed on the corrected revision.
- Planning ran with no tools or MCP servers, ignored provider configuration sources, used a bounded 300-second process deadline and retained redacted raw events plus normalized records.
- The failed authentication launch was counted and its zero reported usage was preserved.
- The controller rejected malformed and authority-changing planner output before creating a project or worker assignment.
- The total live-launch allowance was respected; no retry, repair or substitution occurred.
- No publication approval was recorded.

### Product defects exposed

1. **Authentication readiness is too weak.** Claude's status command can say authenticated while the first inference request returns an expired-token 401. The guided command trusts that status and lacks an explicit operator-requested refresh path.
2. **Planning authentication is not resumable.** Failure occurs before the durable product contract and authentication checkpoint, forcing a new controller root rather than resuming the interrupted stage.
3. **Structured planning is prompt-dependent.** The adapter advertises Claude's `--json-schema` capability but the product planner does not use a provider-enforced schema. A useful plan was lost because the response added trailing prose.
4. **The model changed requirement provenance.** It restated controller constraints as a second `source: user` requirement. The validator correctly rejected this, and future recovery must not delete or relabel it silently.

The smallest corrective batch is to add explicit forced official-login recovery, create a planning-stage authentication checkpoint, wire a verified structured-output schema into planning, and add behavioral regressions for trailing prose, changed requirement provenance, and exact-stage resume. Another live trial requires separate authorization after those changes pass offline validation.

## Usage and cost

| Attempt | Outcome | Elapsed | Input | Output | Cached input | Cache creation | Estimate | Billed |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Claude planning 1 | expired authentication | 3.214 s | 0 | 0 | 0 | 0 | USD 0 | unknown |
| Claude planning 2 | provider success; controller rejection | 88.654 s | 2 | 6,896 | 0 | 8,703 | USD 0.25944 | unknown |

These are provider-reported categories. Internal provider requests are unknown. The second stream emitted an allowed rate-limit warning at 79% seven-day utilization with overage reported false; it did not report quota exhaustion. Estimated cost is not a bill, and actual account billing impact remains unknown.

## Product and security coverage

Product correctness is untested because no product files were generated. The protected mechanics test did not run. Browser usability, responsive behavior, storage, keyboard/touch behavior and visual quality are all unverified.

Security evidence is limited to the tested planning path: external macOS guard initialization, a model-only Claude invocation with no tools or MCP servers, sanitized persisted output and no recorded login material. No worker filesystem boundary, candidate verification boundary, browser boundary or cross-provider review boundary was exercised in this trial.

The manifest hashes 24 retained evidence files. Controller SQLite databases and authentication state are excluded. The archive includes the brief, protected acceptance, protected mechanics test, request metadata, redacted streams, normalized results, controller projections, versions and usage summary.
