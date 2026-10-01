# R1 read-only project intake

R1 lets an operator inspect and hash-enroll a clean, explicitly named Python library repository, then generate a revision-bound non-executing task plan. It does not run repository code or authorize repository execution. R2 remains required before an enrolled project can be imported into an implementation workspace.

## Supported boundary

- A standalone Git repository with a `.git` directory, SHA-1 object format, an attached branch and a clean committed baseline.
- At most 2,000 tracked files, 16 MiB of tracked content, 2 MiB per file and 1,000 visible untracked files under the default policy.
- UTF-8 portable paths, regular files and the existing macOS Python-library execution-profile proposal.
- A controller state directory outside the project.
- Proposed `python3 -m unittest` or `python3 -m pytest` check recipes. R1 records these vectors but never executes them.

The inspector hashes raw working-tree bytes and compares them with index objects. Its Git metadata commands disable optional locks, hooks, fsmonitor, untracked cache, global configuration, system configuration, terminal prompts and pagers. It does not call `git status`, apply attributes, invoke filters, run hooks, inspect remotes or contact the network.

Before any Git command, intake rejects configuration includes, linked/shared metadata, alternate object stores, metadata symlinks and excessive Git metadata. It then reports or rejects detached heads, dirty index/worktree state, submodules, symlinks, LFS pointers, transform attributes, configured filters, unsupported modes and object formats. Secret-like and binary tracked paths must be explicitly excluded by the enrolled profile. Filename screening is a warning layer and is not proof that source contains no secrets.

Ignored untracked paths are classified with a small controller-owned parser over tracked `.gitignore` files. Complex negation, `**` and character-class rules remain visible warnings and are not trusted to hide files. Repository-local `.git/info/exclude` and user-global ignore files do not expand enrollment scope.

## CLI

Inspect a named repository:

```sh
python3 -m agentkit project inspect /absolute/path/to/project
```

Create a starting profile and review it:

```sh
python3 -m agentkit project profile-example > /tmp/agentkit-python-profile.json
```

Enroll a ready project into a separate local state directory:

```sh
python3 -m agentkit project enroll /absolute/path/to/project \
  --profile /tmp/agentkit-python-profile.json \
  --state-root /absolute/path/to/agentkit-state
```

Use the returned project ID to inspect the immutable record or generate a read-only plan:

```sh
python3 -m agentkit project show \
  --state-root /absolute/path/to/agentkit-state \
  --project-id project-0123456789abcdef

python3 -m agentkit project plan \
  --state-root /absolute/path/to/agentkit-state \
  --project-id project-0123456789abcdef \
  --request "Fix documented empty-input behavior"
```

Planning re-inspects the repository and blocks on a changed root, inode, branch, revision, manifest or dirty state. The output always has `execution_authorized: false` and names `repository_execution_requires_R2` as a blocker. Model calls, dependency installation and project commands remain zero.

## Unsupported in R1

Linked worktrees, bare/shallow/SHA-256 repositories, submodules, Git LFS, clean/smudge or working-tree transforms, alternates, symlinked metadata or tracked content, dirty baselines, arbitrary stacks, shell recipes, installation, network access, provider calls, import, implementation, verification and publication are unsupported. AgentKit reports these modes without repairing or changing the repository.
