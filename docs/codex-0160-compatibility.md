# Codex 0.160.0 compatibility record

Date: 2026-10-05. The next product-validation preflight stopped before inference because the installed official `@openai/codex` package had moved from reviewed 0.159.3 to 0.160.0. AgentKit's exact-version gate correctly treated it as unreviewed.

The local audit inspected the installed package metadata, `codex --version`, root help and `codex exec --help`. The package identifies version 0.160.0, Apache-2.0 licensing and the official `openai/codex` repository. The installed help still advertises every control required by AgentKit:

- root `--no-daemon` and `--strict-config`;
- exec `--json`, `--output-schema`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules` and `--sandbox`;
- the existing `--skip-git-repo-check`, noninteractive color and working-directory controls used by the adapter.

The root-help SHA-256 observed here was `4a7f0188d4d6e6d812c5cfbcf82468336b899acd5e437de7450421a403c0071e`; exec help was `0e82cfde0122715250e93dc65866caa956b2ac5b9d0b20ec4ad4f9e81486509e`. These hashes record this host's advertised interface, not executable provenance or a guarantee of runtime behavior. The resolved launcher hash observed by doctor remained `61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70`; nested native components are outside that hash scope.

AgentKit now accepts the finite reviewed set 0.159.3 and 0.160.0. Other Codex versions continue to fail managed preflight. The adapter arguments, subscription-only authentication, external macOS boundary, ignored configuration/rules, disabled optional surfaces, controller deadline and capture bounds are unchanged.

This milestone uses installed-help inspection and offline adapter tests only. The 48 focused runtime/readiness tests passed. The complete repository suite ran 346 tests in 278.768 seconds: 343 passed and the same three host-context checks were skipped. `python3 -m agentkit check` passed 14 skills, 7 domains, 14 examples and 3 pinned sources. The managed development session could not initialize nested Seatbelt, so it does not add host execution, authentication or live inference evidence. The product trial remains blocked until the exact executable is exercised from the supported host context under a separately bounded run.
