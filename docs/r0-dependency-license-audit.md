# R0 OpenHarness dependency and license audit

Audit date: 2026-10-01. Upstream pin: `9b2efd795c6aa09f88b0c257d269a9e518da6ae7`. This is a selected-component closure, not approval of the complete OpenHarness runtime.

## Adopted runtime closure

The R0 Python adapters import only the Python standard library and existing AgentKit modules. They do not import Pydantic, PyYAML, provider SDKs, HTTP/WebSocket clients, MCP, Textual, Typer, messaging integrations, OpenHarness authentication, tools, agent loop or sandbox code.

The executable terminal slice imports only Node built-ins. It ports status/transcript behavior out of the React/Ink application so the vertical slice runs without installing packages. It never installs dependencies, launches an arbitrary backend, inherits the controller environment or accepts an approval command.

| Adopted surface | Direct runtime dependencies added | License/provenance |
|---|---:|---|
| Python profile/context/protocol/fs adapters | 0 | OpenHarness MIT plus AgentKit original adaptations |
| Node event renderer | 0 | OpenHarness MIT plus AgentKit original adaptations |
| Deterministic backend | 0 | Existing AgentKit standard-library core |

The exact retained source paths and hashes are in `agentkit/integrations/openharness/adaptation-map.json`. The upstream MIT text is retained in `third_party/openharness/LICENSE`.

## Evaluated optional terminal closure

The pinned upstream terminal lock contains 80 package entries. Its lock metadata declares 77 MIT, one ISC, one Apache-2.0 and one `(MIT OR CC0-1.0)` package. The direct runtime packages are Ink, ink-text-input, marked, React and string-width; TypeScript/tsx and type packages are build dependencies. This metadata check does not replace retaining each dependency's license text in a distributed bundle.

R0 does not copy the upstream package lock or ship those packages. Before the optional React/Ink TUI is adopted, P01 remains open for that optional artifact: review all resolved packages and install scripts, retain required texts, build from a pinned lock in an isolated release job, ship reviewed assets, and verify the supported Node baseline. Runtime `npm install` is prohibited.

## Rejected closure

The full upstream Python package declares 19 required dependencies and Python 3.10+. Most enter through provider clients, channels, MCP, broad CLI/UI runtime and configuration types rather than the selected R0 behavior. Pulling them into AgentKit would expand install, network, authentication and execution surfaces without serving this spike. They are excluded, not silently vendored.

No dependency, plugin, CLI setting or global package was installed or changed during R0. The existing toolkit retains its current Python compatibility; the adapted modules avoid syntax or library requirements above that baseline.
