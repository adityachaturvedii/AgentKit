# R3 compatibility matrix

This matrix separates declared language compatibility, locally exercised versions, and managed execution support. A successful offline command on another host does not extend the live execution boundary.

| Component or path | Declared requirement | Exercised evidence | Support statement |
|---|---|---|---|
| Python offline CLI and tests | Python 3.9+; standard library runtime | Python 3.9.6 on Darwin 25.6.0 arm64 | Source checkout and isolated wheel are supported on the tested host; other Python 3.9+ platforms remain unverified |
| Git-backed fixture workflows | System Git available | Exercised by deterministic repository tests on the tested macOS host | Required for controller repositories/worktrees; project Git configuration is not inherited as authority |
| One-shot terminal renderer | Node.js 18+; no installed packages | Node.js 22.19.0 on Darwin 25.6.0 arm64 for P13 documentation checks | Optional; plain, JSON and protocol-event views do not need Node |
| macOS managed live execution | `/usr/bin/sandbox-exec`, reviewed CLI and exact policy prerequisites | Historical Darwin 25.6.0 arm64 evidence | Only trusted controller-created disposable workspaces; evidence remains revision-specific |
| Codex CLI live adapter | Separately installed compatible CLI and existing subscription login | Historical Phase 2/4 runs used 0.154.0; offline compatibility seams cover the finite reviewed set 0.159.3 and 0.160.0 | Not distributed; current productive calls require a reviewed version, `--no-daemon`, `--strict-config` and explicit live authorization |
| Claude Code live adapter | Separately installed compatible CLI and existing subscription login | 2.1.220 in the recorded Phase 2/4 evidence | Not distributed; productive calls require explicit live authorization |
| Linux, WSL2 and Windows managed execution | No supported guard | Not validated | Unsupported |
| Full-screen terminal UI | No reviewed dependency/build package | Not implemented | Unsupported; the shipped terminal view is one-shot |
| General repository execution | No general execution profile | Narrow fixture and experimental Python-library slices only | Unsupported |

## Source checkout versus installed paths

From a source tree, AgentKit runs from the repository root with `python3 -m agentkit`. The complete checkout supplies Python modules, skills, schemas, notices, frontend files, tests and controller assets. The Python distribution is named `agentkit-controller`; an isolated wheel install supplies the `agentkit` console command and bundled immutable resources under `agentkit/_resources`.

The checkout import path is the working tree. The wheel import path is its virtual environment's site-packages, and it must be tested from outside the checkout to avoid accidentally importing source files. The optional Node renderer is bundled as a Python resource and invoked by AgentKit; it is not globally linked and Node itself is not installed. There is no supported editable install, Homebrew formula, npm release or system-wide installation procedure.

## Compatibility checks

Use read-only or offline checks before any live run:

```sh
python3 --version
git --version
python3 -m agentkit check
python3 -m agentkit doctor
node --version
```

`doctor` observes installed CLIs, authentication status and sandbox capability. It does not install tools, change login, run inference or prove future token validity. A CLI version outside the reviewed compatibility constants blocks managed execution rather than silently falling back.

Live evidence cited here is historical and revision-bound. P13 ran no provider calls, login, network installation or sandbox expansion.

Use this matrix with the [offline distribution procedure](r3-distribution.md) and [data-flow boundaries](r3-data-flow.md).
