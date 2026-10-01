# R0 OpenHarness reuse validation

Date: 2026-10-01. Planning base: `e5d870b8be6fe1d6eae1d9a41e2cf318acfc109a`. Tested executable revision: `c27f0a28bc7120b0166bdd695fc0fcb402692c87`. Branch: `implementation/r0-openharness-reuse`. This milestone contains no provider inference, login, credential access, dependency installation, execution-profile expansion or publication.

## Result

R0 passes its acceptance gate for architecture option B: substantial selected OpenHarness behavior is adapted around the existing AgentKit controller without importing the upstream runtime. One deterministic calculator task passed implementation, controller-owned verification and independent deterministic review, reached `awaiting_pr_approval`, and rendered its exact candidate through the adapted event/terminal seam. Usage remained unknown and approval remained false.

Command:

```sh
python3 -m agentkit reuse-demo --output /tmp/agentkit-r0-demo
```

The command requires a fresh output path and Node 18+ already present. It does not install Node packages. It writes a private event stream, rendered terminal, metadata and the existing workflow's controller/evidence/package artifacts.

The final acceptance run at `/private/tmp/agentkit-r0-acceptance-final-20261001` completed in 2.057 seconds and delivered candidate `b8a4b8face7c7ef8c9a515f4e44038046ddd9eda` from base `882b2ecd71a60927933cd3592732e20c341f3a78`. These disposable revisions identify that generated fixture only. The event hash was `a78b1c558bb68021266a04bba270dec64c6a059d3797d651b8d59e46936c0414`, and terminal hash was `b4241c424ef3338e66a06f0eae7365d8fdfb59239d0d8c8966d45c8ca0f599ce`.

## Implemented and tested

- Public provider profiles adapted from upstream settings, with content-hash enrollment and profile → role → task provenance. Authentication, endpoint, tool, retry, turn, timeout and token fields are rejected.
- Root-bounded AGENTS/CLAUDE instruction discovery adapted from `claudemd.py`, including hashes, explicit limits, advisory labeling and symlink/encoding rejection.
- A versioned, size-bounded UI protocol adapted from upstream protocol types. The frontend can request snapshot, deterministic demo, cancellation or shutdown; it cannot submit prompts, grant tool permission, record approval or publish.
- Strict private atomic writes adapted from upstream filesystem helpers. Permission failure does not silently weaken the result.
- A runnable Node terminal renderer adapted from StatusBar/TranscriptPane/session behavior. It presents lifecycle warnings, unknown usage and candidate/package identity without React/Ink installation.
- A thin backend that invokes the existing `Phase4Workflow` with deterministic providers, then projects authoritative status into display-only events. Repeating the start is rejected.

Changed-profile rejection, root escape, symlink sources, malformed/oversized messages, authority-expanding commands, unknown usage, cancellation, authentication wait, stale candidate and unapproved package behavior have direct regression coverage.

## Verification

| Check | Result |
|---|---|
| Focused Python R0 suite | 10 passed |
| Dependency-free Node terminal suite | 4 passed |
| Complete AgentKit suite | 192 total: 190 passed; 2 skipped inside the managed outer sandbox |
| Separate host execution of the two skips | 2 passed: constrained verifier boundary and loopback preview lifecycle |
| `python3 -m agentkit check` | Passed: 10 skills, 7 domains, 10 examples, 3 foundation sources |
| Python 3.9 compilation | Passed with an isolated bytecode cache |
| Upstream MIT license bytes | Exact SHA-256 match: `dcb4464b75fbeec7fe5e9b13eeadf37a1e813ded33392c6303f091c37da6fa20` |

The original upstream Pytest/React suites were not run wholesale: their broad runtime and package dependencies were deliberately not installed. Applicable behaviors from `test_settings.py`, `test_claudemd.py`, UI protocol/backend tests and terminal component tests were ported into the focused standard-library/Node suites. This is adaptation coverage, not a claim that all upstream tests pass.

## Measured integration difficulties

| Finding | Observed consequence | Resolution |
|---|---|---|
| Upstream protocol imports Pydantic plus task, state, MCP and bridge runtime types | Importing it would pull authority-unrelated state into the UI seam | Ported the data shapes into a strict standard-library protocol |
| Settings mix public model profiles with credentials, endpoints, runtime defaults, hooks and permissions | Direct reuse could override auth/resource policy | Retained public routing concepts only and fail closed on authority fields |
| Context discovery walks to filesystem root | Neighbor/global instructions could enter worker context | Added explicit root, source hashes and bounds |
| Frontend hook spawns arbitrary configured backend with inherited environment and passes unprefixed logs | Credential/environment and transcript boundary is too broad | One-shot fixed renderer reads only strict event files under a byte cap |
| React/Ink terminal lock contains 80 packages | Full TUI adoption adds build/license/install work unrelated to proving the seam | Executable R0 renderer uses Node built-ins; full UI remains a reviewed optional artifact |
| Upstream filesystem helper may silently ignore chmod failure | Evidence/config confidentiality could be weaker than reported | Private mode is mandatory and directory metadata is flushed |
| First port used Python 3.10 union syntax | Toolkit's Python 3.9 baseline failed at import | Added postponed annotations and retained current compatibility |

The implementation did not require changes to controller schema, task transitions, authentication, budgets, provider adapters, sandbox profiles or evidence rules. That is the key architecture result.

## Retain, adapt, drop

| Surface | Decision after R0 | Evidence |
|---|---|---|
| Terminal status/transcript concepts | Retain/adapt | Runnable event renderer and Node tests; expand to React/Ink only after packaging gate |
| Frontend/backend protocol | Adapt | Strict event seam works; generic permission/prompt/session commands remain excluded |
| Provider profile concepts | Retain/adapt | Hash-bound resolution works without auth/runtime defaults |
| Readiness/presentation helpers | Retain selectively | Thin status projection is useful; complete CLI/runtime construction is not |
| Context and skill discovery | Adapt | Root-bounded AGENTS/CLAUDE discovery works; global/plugin discovery remains excluded |
| Atomic file helper | Adapt | Private durable writes are useful with stricter failure behavior |
| Upstream authoritative state/controller | Drop for this architecture | Current SQLite controller already carries stronger tested lifecycle semantics |
| Credential bridge, API clients, agent engine, tools, worker Git, channels/plugins/autopilot | Drop/defer | No R0 need; each would expand authority, dependencies or spending boundaries |
| OpenHarness sandbox/container backend | Defer | Requires separate real tool, credential, mount and lifecycle validation |

## Remaining boundary

R0 validates reuse feasibility, not general repository work. The UI is a one-shot executable slice rather than an interactive React/Ink application. It does not authenticate users, run a server, inspect personal repositories or establish hostile-code safety. The next planned gate is R1 read-only enrollment and repository inspection; it must execute no project code, hooks, filters, installs or inference.
