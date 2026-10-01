# R3 terminal workflow

The `workflow` command is a small, versioned frontend for an **existing Phase 4 controller-created disposable workflow**. It exposes the same controller actions in plain text, structured JSON, protocol JSONL and the dependency-free one-shot terminal renderer. It does not submit a task, execute a general repository, approve a candidate, publish, merge or deploy.

Create the workflow with the existing offline task intake, then use the frontend:

```sh
python3 -m agentkit task submit \
  --root /tmp/agentkit-task \
  --task-id calculator-demo \
  --project calculator \
  --request "Repair the calculator fixture"

python3 -m agentkit workflow status \
  --root /tmp/agentkit-task \
  --task-id calculator-demo

python3 -m agentkit workflow start \
  --root /tmp/agentkit-task \
  --task-id calculator-demo \
  --format terminal

python3 -m agentkit workflow package \
  --root /tmp/agentkit-task \
  --task-id calculator-demo \
  --format json
```

`status`, `start`, `resume`, `cancel` and `package` are allowlisted protocol operations. `package` returns a bounded summary of the local approval package. To create the portable P11 review folder, use the separate `package export` command documented in the [portable-package guide](r3-portable-package.md).

Every action accepts `--format plain|json|events|terminal`:

- `plain` is the default and reports task state, next action, usage, assignment counts, attention and package identity when present.
- `json` emits one object containing the validated backend events.
- `events` emits protocol-v1 JSONL, one bounded event per line.
- `terminal` passes the same JSONL to the adapted one-shot Node renderer. It requires Node.js 18+ and does not install packages, launch a backend or retain a session.

This is a one-shot command interface, not an interactive full-screen TUI. Re-running `status` reads current controller state. It does not replay `start` or `resume`.

## Live execution authorization

The deterministic fixture path is offline by default. A live provider start or resume requires both flags on that invocation:

```sh
python3 -m agentkit workflow start \
  --root /tmp/agentkit-task \
  --task-id calculator-demo \
  --live \
  --authorize-subscription-smoke
```

The same construction-time flags apply to `resume`. Task text, model output, transcript items, stored events and renderer controls cannot set live mode or grant subscription authorization. The backend validates the request against the constructor-bound task identifier and delegates lifecycle checks to the durable controller. Read-only status and package summary, and cancellation, do not accept live authorization flags.

Live mode uses already installed official CLIs and their existing subscription state. The command does not add API keys, purchase credits, change login methods or authorize publication. Ordinary tests and the examples above use deterministic providers and make no inference calls.

## Boundaries

P12 covers the existing Phase 4 disposable fixture workflow and the strict protocol projection of its controller state. General repositories, R2 repository-delivery execution, static-web product workflows, remote workers, server/RBAC features and application of a package to an original checkout remain outside this command.

The controller database remains authoritative. Plain, JSONL and terminal text are views. An event may describe an action or contain model text, but it cannot expand paths, budgets, provider permissions, approval or publication authority. Usage remains `unknown` when providers do not report it. A local approval package remains unapproved until a separate authorized system records a decision; this frontend has no approval operation.
