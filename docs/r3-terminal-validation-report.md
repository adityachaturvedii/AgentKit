# R3 P12 terminal-workflow validation

Date: 2026-10-01. Branch `implementation/r3-terminal-workflow`, dedicated worktree `/Users/aditya/agentic/agentkit-r3-terminal`, stacked on P11 revision `43f1863cbfb84b3b460ff8df08d526eda1640b90` while its integration PR is reviewed.

## Result

P12 adds one strict frontend over existing controller-created Phase 4 disposable workflows. `status`, `start`, `resume`, `cancel` and `package` produce equivalent bounded protocol events rendered as plain text, structured JSON, JSONL or a dependency-free one-shot terminal view. Status reconnect and package inspection do not relaunch work. Unknown usage remains unknown, cancellation uses the existing durable lifecycle, and package output identifies the exact branch/base/head while keeping approval false.

The request protocol contains only version, operation and the constructor-bound task identifier. It rejects paths, live flags, provider settings, permissions, budgets, approval and unknown fields. Live mode and its existing subscription authorization can enter only through explicit CLI construction flags for `start` or `resume`. Backend events reject unknown fields, authority expansion, invalid usage/routing shapes and terminal-control characters before plain/JSON output; the Node renderer independently repeats those checks.

## Validation

| Check | Result |
|---|---|
| Terminal workflow, CLI and R0 compatibility | 23 Python tests passed |
| `node --test frontend/agentkit-terminal/test/*.test.mjs` | 8 passed |
| `python3 -m unittest discover -s tests -v` | 248 total: 245 passed, 3 expected managed-environment skips |
| `python3 -m agentkit check` | Passed: 10 skills, 7 domains, 10 examples and 3 pinned sources |
| `PYTHONPYCACHEPREFIX=/tmp/agentkit-r3-terminal-pyc python3 -m compileall -q agentkit tests` | Passed |
| `git diff --check` | Passed |

The three skips are unchanged host-context checks: two nested macOS Seatbelt initializations and one loopback preview bind. P12 changes display/command projection, not those execution boundaries, so earlier host evidence is not promoted to this revision. No provider call, authentication flow, network access or live inference was used.

Behavioral coverage includes read-only repeated snapshots, deterministic start, exact candidate/package projection, authentication checkpoint resume without restarting completed work, cancellation before launch, package inspection before and after completion, constructor-bound authorization, wrong-task rejection, unknown usage, format equivalence, routing/next-action rendering, authority-expanding events and terminal-control injection.

## Limits and next gate

The terminal is a one-shot renderer using Node built-ins, not a full-screen interactive React/Ink application. P12 operates existing Phase 4 disposable fixture workflows; it does not add general repository execution, an R2 repository-delivery launcher, product/browser orchestration, remote access, RBAC, approval, GitHub publication, merge or deployment.

P13 remains open for distribution, compatibility and data-flow documentation, including the unresolved outbound-license decision and any separately audited optional frontend dependency bundle.
