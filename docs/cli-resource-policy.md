# CLI integration resource policy

This policy separates four concerns that had previously been mixed together:

1. the operator-authorized task budget;
2. controller allocations to planning, implementation, verification and review;
3. provider-specific CLI controls; and
4. usage observed after a CLI launch.

The resolution order is **explicit task override → configured role policy → provider default**. Every resolved controller allocation records its value, source, enforcement class and rationale. `python3 -m agentkit resource-policy` prints the executable policy.

`provider default` means the harness leaves the setting unset. It does not mean unlimited. The effective provider ceiling, internal request count and internal turn count may remain unknown.

## Installed capability audit

The corrective audit used local `--version` and `--help` output from Codex CLI `0.154.0` and Claude Code `2.1.220`. The official references consulted were:

- [Codex non-interactive mode](https://developers.openai.com/codex/non-interactive-mode)
- [Codex configuration reference](https://developers.openai.com/codex/config-reference)
- [Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
- [Claude Code settings and permissions](https://docs.anthropic.com/en/docs/claude-code/settings)

| Control | Codex 0.154.0 | Claude Code 2.1.220 | Harness treatment |
|---|---|---|---|
| Model | `--model` | `--model` | Requested value is passed; provider-reported value stays separate. |
| Effort | No `exec --effort` in installed help | `--effort` with five advertised values | Codex rejected by the tested contract; Claude passed as best-effort requested configuration. |
| Structured result | `--output-schema` is advertised; JSONL events are used | `--json-schema` is advertised; stream JSON is used | Provider output remains untrusted and controller validation is required. |
| Generated-output tokens | No supported `exec` control | No supported flag in installed help | Unset for productive work. The old Claude environment variable is observable-only and cannot be a productive policy. |
| Turn limit | No supported control | Official material has described `--max-turns`, but installed 2.1.220 help does not expose it | Unset for productive work on this host. |
| Retry limit | No supported built-in subscription control | No supported flag in installed help | Provider default; controller wall time bounds the CLI launch. Internal attempts remain unknown. |
| Timeout | No provider flag used | No provider flag used | Enforced by the controller against the process group. |
| Tool permissions | CLI sandbox/config plus external Seatbelt | `--tools`, settings permissions plus external Seatbelt | Provider permissions are best-effort; the tested filesystem boundary is enforced independently by Seatbelt and broker validation. |

`tool_output_token_limit` in Codex configuration concerns retained tool output, not generated model output. It is not used as a task token or cost limit.

## Capability profiles

| Profile | Mode | Provider-visible tools | Approved local commands |
|---|---|---|---|
| `structured-planning` | model-only | none | none |
| `code-implementation` | owned-code | Read, Edit, Write, Bash | `python3 -B -m unittest…` |
| `web-product-implementation` | owned-code | Read, Edit, Write, Bash | `node --check…`, `npm run build…`, `npm test…` |
| `independent-review` | model-only | none | none |
| `smoke-model-only` | model-only | none | none; Claude's historical 512-output/one-turn/zero-retry environment is confined here |

The Claude settings allow specific Bash patterns, never the broad `Bash` permission. Codex does not expose an equivalent command allowlist through the tested noninteractive interface. Its model-generated commands remain inside the external owned-workspace Seatbelt profile, and the Git broker rejects files outside the assignment scope. Network/tool separation and comprehensive credential isolation remain unsupported.

## Recovery and accounting

An actual provider output-exhaustion error is distinct from the controller's byte capture limit. A structured result truncated by either condition is rejected.

The controller may retry once only when all of these are true:

- a controller-imposed generated-output override actually exhausted;
- the task retains call and elapsed-time capacity;
- removing that override produces a different request; and
- the same adjusted failure has not already occurred.

The retry removes the unjustified override and returns to the provider default. It does not guess a larger universal number, repeat an identical provider-default failure or switch providers. Every CLI launch and its reported usage is recorded. One CLI process may make several provider requests or turns; those internal counts are `unknown` unless the CLI reports them reliably.

Call counts and process deadlines are enforced. Provider token categories and cost are observations. A Claude `total_cost_usd` field is retained as an estimate, never billed cost. Subscription billing and paid-overflow state remain unknown, so neither token nor dollar spend has a hard controller guarantee.

Each persisted productive result includes the sanitized argument array, environment key names and set/unset markers for the three historical Claude limit variables. Environment values, prompts, credentials and authentication transcripts are excluded. This makes direct-versus-adapter restrictions reviewable without turning evidence into an environment dump.
