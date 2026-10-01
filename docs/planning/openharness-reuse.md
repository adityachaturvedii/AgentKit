# OpenHarness reuse assessment

Status: the original assessment below informed the completed R0 component port. Selected adapted behavior is now offline-tested; this remains neither a security certification nor validation of the complete upstream runtime. No dependencies were installed, no credential store was inspected and no inference was launched. See the [R0 validation report](../r0-validation-report.md).

## Reproducible source base

Repository: `https://github.com/HKUDS/OpenHarness`.

Pinned commit: `9b2efd795c6aa09f88b0c257d269a9e518da6ae7`; its package declares version `0.1.9`. The [source inventory](openharness-source-inventory.json) records 50 candidate/context/test files with SHA-256, size and static direct-import information. Inventory coverage is broader than detailed review; the observations below name the portions actually inspected. Python was parsed as source text/AST only, never imported. Test names and selected source were inspected; no upstream pass count is claimed.

The top-level [MIT license](https://github.com/HKUDS/OpenHarness/blob/9b2efd795c6aa09f88b0c257d269a9e518da6ae7/LICENSE) carries `Copyright (c) 2025 OpenHarness Contributors`. Adopted substantial portions must retain the applicable copyright/license. Before copying, inspect each selected file's provenance and the licenses of its import/build closure. A top-level license is not a completed supply-chain audit.

## Architecture options

| Option | What we reuse | Cost and risk | Recommendation |
|---|---|---|---|
| A: Full OpenHarness fork; move AgentKit gates into it | Runtime, UI, providers, tools, memory, configuration and sandbox machinery | Must replace or interpose authoritative state, auth, retries, accounting, worker spawning, Git effects and auto-discovery; large surface to revalidate | Keep as a measured alternative, not the default migration |
| B: Substantial component port around AgentKit delivery core | Terminal frontend/components, selected profile/settings code, readiness helpers, context/skill loaders; later sandbox and optional API worker | Explicit compatibility layer and patch maintenance; preserves current delivery invariants | Recommended starting architecture, subject to a working reuse spike |
| C: Run OpenHarness as an optional leaf engine | Broad agent loop and tools through a process boundary | Adds an engine and potentially API spend, new credential and tool boundaries; nested requests/agents must be controlled | Later only if user tasks need a capability the existing CLIs cannot supply |
| D: Reimplement equivalent infrastructure | Ideas only | Maximum duplicate engineering and maintenance | Reject unless a named component cannot be adapted economically |

B is a substantial reuse proposal, not permission to rewrite every upstream component behind a new interface. The first spike must render a real AgentKit run using adapted upstream frontend code and resolve a profile using adapted upstream configuration code. Track retained modules, changed interfaces, eliminated dependencies and upstream tests preserved. If extraction needs most of the original runtime anyway, compare A and C with concrete dependency/test evidence before proceeding.

The current controller is retained because it already enforces the required semantics, not because it is proprietary or irreplaceable. A replacement is acceptable after equivalent regressions pass; historical artifacts and live-run identities must remain readable.

## Module-level reuse map

Paths below are relative to the pinned upstream repository. `ADAPT` means a real source port with notices and a patch ledger; `REUSE` is a candidate for minimal or unchanged reuse after tests; neither means adopted today.

| ID | Upstream source / tests | Disposition and intended replacement | Required adaptation or proof |
|---|---|---|---|
| OH-01 | `frontend/terminal/src/components/{StatusBar,ModalHost,TranscriptPane,MarkdownText,PromptInput,SelectModal}.tsx`, themes and related component tests | ADAPT as AgentKit terminal shell and progressive status UX | Task/evidence-first views; treat model text as display data; separate questions from approval actions; no generic full-auto or publish command |
| OH-02 | `frontend/terminal/src/hooks/useBackendSession.ts`, `src/openharness/ui/protocol.py`, `tests/test_ui/test_react_backend.py` | ADAPT frontend transport and request/event models; add a thin AgentKit controller backend | Strict versioned events, size/shape checks, explicit controller command allowlist, sanitized environment, no raw login stream; UI reconnection cannot relaunch workers |
| OH-03 | `src/openharness/config/settings.py` (`ProviderProfile`, profile materialization/override code), `tests/test_config/test_settings.py` | ADAPT profile resolution and configuration UX; replace duplicate routing-profile loading through an adapter | Separate public profile from auth material, explicit provider/account default, no ambient auth/base URL override, preserve task resource provenance and strict numeric checks |
| OH-04 | `src/openharness/cli.py` (`_evaluate_dry_run_readiness`, `_format_dry_run_preview`, selected setup helpers) | ADAPT readiness and presentation code into enroll/doctor/plan | Extract pure logic; do not invoke its complete runtime/plugin/auth construction path; report status observations separately from live auth success |
| OH-05 | `src/openharness/prompts/claudemd.py`, `skills/{loader,_frontmatter,types,registry}.py`, prompt/skill tests | ADAPT discovery, parsing and metadata; integrate with AgentKit's existing hash-verified role assembly | Stop at explicit project root; explicit source list, file-size and symlink handling; AGENTS.md support; project instructions are advisory data, never permission |
| OH-06 | `utils/fs.py`, `utils/file_lock.py`, related utility/locking tests | REUSE/ADAPT atomic artifact/config writes where needed | Explicit private mode; avoid silent chmod failure where required; destination validation, bounded lock behavior and durability semantics. Do not replace SQLite transactions with JSON locks |
| OH-07 | `sandbox/{adapter,docker_backend,docker_image,path_validator,session}.py`, `tests/test_sandbox/` | ADAPT as a later execution backend, not just design inspiration | Require sandbox; pin image/runtime; constrain mounts/env; remove automatic build/download; real stop reconciliation; no controller/credentials inside untrusted tool runtime |
| OH-08 | `tools/{base,file_read_tool,file_write_tool,file_edit_tool,glob_tool,grep_tool}.py`, core-tool tests | ADAPT if the optional OpenHarness/API engine is selected; use pure bounded helpers for inventory where appropriate | OS boundary plus path policy, byte limits and race tests; no direct mutation of broker worktrees; tools not registered globally |
| OH-09 | `api/{client,openai_client,errors}.py`, API tests | ADAPT in a separately authorized API engine increment | Strip CLI-token bridge; reserve/observe each API attempt; reviewed SDK behavior; provider-specific required fields; nullable usage; official endpoints and credential references |
| OH-10 | `engine/{query_engine,query,messages,stream_events}.py`, engine tests | CONDITIONAL substantial runtime reuse, only if C or API execution is justified | One bounded worker role; inject narrow registry and brokered execution; disable memory side jobs, subagents, hooks and extra inference unless explicitly budgeted |
| OH-11 | `api/usage.py`, `engine/cost_tracker.py` | RETAIN AgentKit usage/accounting instead | Upstream defaults missing input/output to zero and aggregates only those fields; incompatible with current unknown/cache/cost semantics |
| OH-12 | `state/store.py`, task/session storage | REUSE only as disposable UI/session view state; RETAIN AgentKit authoritative store | `AppStateStore` is an in-memory view/listener store, not a transactional task ledger; session history is not process reconciliation |
| OH-13 | `auth/external.py`, subscription clients | EXCLUDE from AgentKit subscription paths | Reads/refreshes CLI credentials itself; keep official CLI status/login and no token extraction |
| OH-14 | `tools/enter_worktree_tool.py`, commit/push/PR tools | EXCLUDE from worker registries; retain broker | Worker-driven Git actions conflict with controller ownership; existing Git broker still needs real-repository hardening |
| OH-15 | `ui/runtime.py`, `ui/backend_host.py`, `ui/react_launcher.py` | ADAPT selected host/protocol pieces, do not import full runtime wholesale | Runtime imports engine, auth, hooks, plugins, MCP and tools; launcher can install npm dependencies and inherits environment. New trusted launch boundary must remove these implicit effects |
| OH-16 | ohmo, channels, autopilot, cron, voice, broad plugins/MCP and swarm management | DEFER/EXCLUDE from first release | No current product need; importing these would introduce unrelated authority, networking, state and dependencies |

This plan deliberately reuses a significant user-facing/configuration/context subsystem. It does not add a second file-editing or model loop just to increase the amount of copied code while Codex/Claude already provide those capabilities.

## Confirmed incompatibilities at the pin

1. **Resource defaults:** `config/settings.py:566` has `max_tokens=16384`, `timeout=30`, `max_turns=200`; `api/client.py` separately defaults `max_tokens=4096` and declares retries. These are upstream application choices, not universal provider constraints. Preserve AgentKit's productive CLI defaults and policy resolution. A future API requiring `max_tokens` must receive a provider-validated role allocation, not an invented unset default or global constant.
2. **Sandbox defaults:** settings have `enabled=False` and `fail_if_unavailable=False`. The sandbox adapter may return the original command when configured to do so. AgentKit-managed execution must refuse unavailable isolation; there is no unsafe compatibility switch.
3. **Container lifecycle:** Docker `stop()` clears `_running` in `finally`, and stop exit status is not sufficient proof of removal. Adapted code must query owned container identity/state and preserve uncertainty after timeout/error. A detached container lifecycle differs from a supervised process group.
4. **File boundary:** file read/write/edit tools use Python host filesystem operations; their explicit sandbox path check is conditional on the Docker session being active. Do not assume putting Bash in a container protects every file tool. Path resolution by itself also does not prove race-free file access.
5. **Context discovery:** `prompts/claudemd.py` walks toward the filesystem root, and project skills are enabled by default in settings. Discovery in an enrolled project must stop at that project and never import neighboring/global instructions without explicit enrollment.
6. **Credential bridge:** `auth/external.py` reads `auth.json`, credential JSON or Keychain, and can refresh/write Claude OAuth credentials. Exclude this path entirely from subscription support, including indirect imports through diagnostics.
7. **Unknown usage:** `api/usage.py` has integer-zero defaults; `engine/cost_tracker.py` sums them. Translating those zeros into authoritative AgentKit usage would falsely erase unknowns. Preserve raw provider presence information before normalization.
8. **UI coupling:** the frontend protocol imports upstream application/task/bridge types; backend host invokes the full runtime. Reuse requires a deliberate API boundary, not renaming the executable in a launcher. Login must continue to use a separate uncaptured terminal.
9. **Installation:** React launcher runs `npm install` when dependencies are absent. AgentKit releases should ship reviewed built assets or use an explicit setup step, never install implicitly when opening status.
10. **Git and supervision:** `enter_worktree_tool.py` gives tool callers branch/path inputs; bridge session termination supervises its direct process. Neither replaces our Git authority model or establishes detached-process cleanup.

These findings identify required integration work. They are not a comprehensive vulnerability audit of OpenHarness, and tests using mocked subprocesses are not host boundary evidence.

## Dependency and packaging plan

The pin declares Python >=3.10 and 19 required Python dependencies, including provider SDKs, UI/config libraries, MCP and four messaging families. Dependency requirements are broad lower bounds. The tree contains frontend npm lockfiles; no Python dependency lockfile was found in this pin's tracked-file inventory. AgentKit currently runs on Python 3.9 with the standard library.

Recommended packaging:

- Keep the authoritative core and current CLI adapters usable independently.
- Isolate attributed ports under `agentkit/integrations/openharness/` (proposed path) and terminal code under a separately built frontend directory. Record source paths and local patch IDs rather than pretending copied modules are original work.
- Introduce a small reviewed config/context dependency set only if extraction genuinely needs it; do not rewrite working upstream parsers merely to retain a standard-library-only slogan.
- Offer the adapted TUI as an optional install extra/artifact. JSON/plain CLI remains fully usable without Node. Build and lock its dependency tree during release, not at run time.
- API SDKs, MCP and messaging dependencies do not enter the default install unless their corresponding capability is deliberately adopted.
- Prefer a maintained slim upstream package if extraction demonstrates a clean supported interface. Otherwise vendor pinned portions with notices and an explicit update patch series. A git submodule alone does not solve import coupling or runtime downloads.
- Confirm a supported Python target during the spike. Python 3.11+ is a reasonable proposal for the integrated package, but upgrading the user's interpreter is not authorized here. Existing core compatibility and public-user install needs must inform the decision.

Before adoption: generate a resolved dependency inventory, verify selected licenses, review install hooks, run upstream component tests in an isolated development environment, and run AgentKit compatibility tests. No dependency is approved solely because its name appears here.

## Reuse spike deliverables and decision rule

One timeboxed implementation spike, estimated 3–5 engineering days after plan acceptance:

1. Copy the selected terminal components, profile model/resolution portion and root-bounded context loader with original notices and a machine-readable adaptation map.
2. Drive a deterministic AgentKit task through adapted UI → thin backend → existing controller → event/status/package rendering. No model call, credentials, install-at-runtime or sandbox expansion.
3. Demonstrate changed-profile rejection, candidate-stale status, unknown usage, cancellation and authentication-wait display. Display waiting does not require a login flow.
4. Run the applicable upstream tests and AgentKit integration tests; measure direct/transitive dependencies and imported runtime surfaces.
5. Record a retain/adapt/drop decision per file, actual integration effort and remaining work. Do not invent a percentage cost saving or line-count target.

Choose B if this vertical slice can run without importing unrestricted runtime initialization and most UI/config behavior survives. If source extraction repeatedly drags in engine/auth state, explicitly compare a maintained slim fork (A) and a process-isolated optional worker (C). Do not silently turn the spike into a controller rewrite or begin a parallel homemade UI.

## Ongoing maintenance

Each adopted package needs an owner, upstream pin, file hashes, license notices, dependency lock, patch list, imported tests, behavior differences and rollback instructions. Upstream updates land on an integration branch, rerun compatibility and boundary checks and never alter an active run. Cost/model tables from upstream are configuration evidence to verify, not facts to trust automatically. Report upstream fixes where appropriate only with separate authorization for external posting.
