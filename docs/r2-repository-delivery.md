# R2 safe repository delivery

R2 adds an offline-tested delivery path for an explicitly enrolled, operator-trusted Python library. The source repository remains an immutable input. AgentKit reconstructs verified tracked bytes in a new controller-owned Git repository, gives implementation and review roles plain-file snapshots, runs independently controlled acceptance, and stops at an unapproved local package.

This path does not make R1 enrollment executable by itself. The workflow constructor requires separate controller-side execution authorization. Repository text and model output cannot supply it.

## Boundary

The importer rereads the enrolled root, branch, HEAD, inventory and clean state before and after reconstruction. It reads regular tracked files directly, checks their Git blob IDs, sizes and executable modes, and creates a new repository without clone, remotes, alternate object storage, hard links or inherited templates. Spaces and Unicode names and executable modes are preserved. Tracked content covered by an exclusion is rejected instead of silently disappearing from the candidate.

The initial change broker accepts content modifications to already tracked regular files. Additions, deletions, renames, symlinks and mode changes fail visibly. Applying the resulting patch to the enrolled source remains a later explicit operation.

The prepared-environment gate resolves the installed `python3`, validates the enrolled argv recipes and statically inventories imports. A dependency outside the prepared standard-library/local-module set returns `environment_required`; AgentKit does not install it or enable network access. Static import inspection is conservative and can require a more explicit environment recipe for dynamic or unusual packages.

The native verifier creates a fresh plain-file candidate snapshot with no Git metadata. Existing enrolled checks and a controller-owned acceptance test execute under the established macOS read-only/no-network Seatbelt profile. The enrolled source, registry, controller state, evidence, managed Git repository, implementation worktree and real home are denied. A clean environment supplies a fresh home and writable runtime. Required tests must collect at least one test when their declared parser supports collection counts. Candidate, protected-check and revision identities must remain unchanged.

The deterministic fixture verifier executes the same check/acceptance contract for offline workflow tests, but it provides no operating-system isolation evidence. Reports label it simulated.

## Task and evidence contract

The deterministic task resolver grounds request terms in the enrolled filenames and bounded UTF-8 content. It returns clarification for unrelated or contradictory requests. An implementation handoff contains the user objective, relevant and writable paths, starting revisions, checks, acceptance, dependencies and explicit absence of network, install and publication authority. It contains no expected patch or protected acceptance source.

The workflow reuses `ControllerStore` for validated transitions, atomic execution reservations, append-only events, nullable usage and revision-bound evidence. It reuses `GitBroker` for the branch, worktree, snapshots, scope enforcement and commit. Verification and review bind the committed candidate. The package records both the original enrolled revision and the independent managed base, the exact head, diff, evidence references, limitations and `approval.recorded: false`.

R2 tests use deterministic implementation/review adapters and disposable repositories only. Live Codex/Claude execution, guided authentication recovery through this new adapter, personal repositories and provider data disclosure remain unverified for this path. The existing controller authentication and lifecycle regression families still pass, but that does not turn the new deterministic path into a live-tested provider workflow.

## Current use

R2 exposes a Python integration seam in `agentkit.repository_delivery`; the complete end-user terminal workflow and portable package verifier are R3 work. The supported test construction is:

```python
workflow = RepositoryDeliveryWorkflow(
    fresh_run_root,
    ProjectRegistry(state_root),
    project_id,
    implementer,
    reviewer,
    verifier,
    execution_authorized=True,
)
result = workflow.run(task_id, request, controller_owned_acceptance_source)
```

Passing `execution_authorized=True` represents a trusted controller decision. A frontend must never derive it from task text, a profile file or worker output.

