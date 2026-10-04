# Codex 0.159.3 compatibility record

The first realistic refinement-product trial stopped before inference because the installed Codex CLI was 0.159.3 while AgentKit accepted only the earlier 0.154.0 contract. That fail-closed result is retained on the separate validation branch at `0ba4947`; it consumed zero provider launches.

The corrective review checked the installed `codex --version`, root help, `codex exec --help`, guarded doctor result and the real owned-code adapter boundary with only external provider transport stubbed. It also consulted the official Codex 0.159 releases and configuration source. The reviewed execution contract requires:

- exact Codex CLI 0.159.3;
- JSONL output, ephemeral execution, ignored user configuration and project rules;
- strict configuration validation;
- a per-launch `--no-daemon` selection, preventing reuse or startup of the shared local app-server daemon;
- the existing external Seatbelt boundary, subscription-authentication check and controller time/output capture bounds.

The executable launcher hash observed during host doctor was `61b0194f3bb6534439c8d26a3ed57d0805f84b884588b761795323eeb92fcf70`. This hashes the resolved launcher file, not every nested native component. Help output proves advertised syntax, and the adapter seam proves request construction. Neither proves provider behavior, isolation against every credential path, quota, billing state or productive correctness. Those remain properties of the separately bounded live trial.

Historical 0.154.0 evidence is unchanged and must not be presented as validation of this correction.
