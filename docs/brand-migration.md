# AgentKit brand migration

**AgentKit** is the product and display name from this revision forward.

This is a compatibility-preserving brand rename. It does not change execution authority, authentication, budgets, provider behavior, evidence semantics or supported platforms.

## Current names

| Surface | Name | Status |
|---|---|---|
| Product and documentation | **AgentKit** | Canonical display name |
| CLI invocation | `python3 -m agentkit` | Stable |
| Python package | `agentkit` | Stable |
| Terminal package | `agentkit-openharness-terminal-slice` | Private internal package |
| GitHub repository | `adityachaturvedii/AgentKit` | Canonical remote name |
| Handoff schema ID | `urn:portable-agentkit:handoff:1` | Stable v1 compatibility identifier |

Historical evidence, branch names, filesystem paths, source-input filenames and recorded repository URLs are not rewritten. Their exact spelling is part of their provenance. Temporary-directory prefixes and serialized technical identifiers remain lowercase `agentkit`.

The GitHub repository was renamed after separate user authorization. GitHub resolves the former `adityachaturvedii/portable-agentkit` name to `adityachaturvedii/AgentKit`, and the local `origin` uses the canonical URL. Historical records keep the old spelling as provenance. A new handoff schema name would require a new schema version plus migration and dual-read compatibility; it must not silently replace the v1 URN.

## Validation

- The focused branding and OpenHarness integration suite passes 12 tests.
- The dependency-free terminal suite passes 4 tests and asserts the canonical display name.
- The complete Python suite contains 194 tests. In the managed command sandbox, 192 pass, the loopback preview check cannot open its host socket, and the nested macOS Seatbelt check skips because `sandbox_apply` is unavailable there. Both host-bound checks pass separately in their documented execution context.
- `python3 -m agentkit check` passes its offline structural checks.

These checks validate the local brand migration and compatibility choices. The later repository rename was verified separately through GitHub and does not alter runtime behavior.
