# R3 distribution and offline onboarding

Status: P13 provides Python wheel/sdist metadata plus source-checkout and isolated-wheel onboarding. AgentKit is **not a public distributable release** because the repository has no outbound `LICENSE`. Artifact construction and private validation do not grant redistribution rights. There is no npm release or full-screen frontend package.

## Clean offline source-checkout procedure

Acquire the complete source tree through a separately authorized channel before disconnecting the target environment. Public redistribution is not licensed yet. On the offline macOS target, substitute the verified source path once, then run:

```sh
SOURCE=/absolute/path/to/verified/AgentKit
TARGET=/private/tmp/agentkit-offline-checkout
RUNTIME=/private/tmp/agentkit-offline-runtime

test -d "$SOURCE/agentkit"
test -f "$SOURCE/README.md"
test ! -e "$TARGET"
test ! -e "$RUNTIME"
cp -R "$SOURCE" "$TARGET"
mkdir -m 700 "$RUNTIME"
cd "$TARGET"

env -i \
  HOME="$RUNTIME" \
  TMPDIR="$RUNTIME" \
  PATH=/usr/bin:/bin:/usr/local/bin \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 -m agentkit check

env -i \
  HOME="$RUNTIME" \
  TMPDIR="$RUNTIME" \
  PATH=/usr/bin:/bin:/usr/local/bin \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s tests -v
```

These commands copy files and run offline checks from the checkout. They install no Python or Node packages, contact no provider, and perform no model inference. The full regression suite uses disposable fixtures and can report expected skips when macOS Seatbelt or loopback preview initialization is unavailable inside a parent sandbox.

The Node renderer is optional. If a separately supplied Node.js 18+ executable is already present, validate it without installing dependencies:

```sh
cd /private/tmp/agentkit-offline-checkout/frontend/agentkit-terminal
env -i HOME=/private/tmp/agentkit-offline-runtime PATH=/usr/bin:/bin:/usr/local/bin \
  node --test test/*.test.mjs
```

The frontend `package.json` is private and has no runtime dependencies. `npm install` is neither needed nor part of the tested path.

## Isolated offline wheel installation

Build artifacts only from a verified complete source tree with already installed `setuptools` and `wheel`. `--no-isolation` prevents the build frontend from creating an environment that might fetch build requirements:

```sh
SOURCE=/absolute/path/to/verified/AgentKit
ARTIFACTS=/private/tmp/agentkit-offline-artifacts

test -d "$SOURCE/agentkit"
test ! -e "$ARTIFACTS"
mkdir -m 700 "$ARTIFACTS"
cd "$SOURCE"
python3 setup.py sdist --dist-dir "$ARTIFACTS"
python3 -m pip wheel --no-index --no-deps --no-build-isolation \
  --wheel-dir "$ARTIFACTS" .
```

Transfer the wheel only through an authorized private channel while outbound licensing remains unresolved. On the offline target, install it into a fresh virtual environment and run outside the source tree:

```sh
ARTIFACTS=/absolute/path/to/verified/private/artifacts
VENV=/private/tmp/agentkit-offline-venv
RUNTIME=/private/tmp/agentkit-installed-runtime

test ! -e "$VENV"
test ! -e "$RUNTIME"
python3 -m venv "$VENV"
mkdir -m 700 "$RUNTIME"
set -- "$ARTIFACTS"/agentkit_controller-*.whl
test "$#" -eq 1
WHEEL=$1

env -i \
  HOME="$RUNTIME" \
  TMPDIR="$RUNTIME" \
  PATH="$VENV/bin:/usr/bin:/bin:/usr/local/bin" \
  PIP_CONFIG_FILE=/dev/null \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  "$VENV/bin/python" -m pip install --no-index --no-deps "$WHEEL"

cd /private/tmp
env -i HOME="$RUNTIME" TMPDIR="$RUNTIME" \
  PATH="$VENV/bin:/usr/bin:/bin:/usr/local/bin" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV/bin/agentkit" check
```

The wheel bundles the runtime resources, pinned source lock, attribution material and dependency-free Node renderer under `agentkit/_resources`; it does not install Node, provider CLIs or credentials. Historical `audit/evaluations` records and the regression tests remain source-tree material and are not bundled in the installed distribution.

To uninstall only the installed Python distribution while retaining the virtual environment for inspection:

```sh
env -i HOME="$RUNTIME" PATH="$VENV/bin:/usr/bin:/bin:/usr/local/bin" \
  PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 \
  "$VENV/bin/python" -m pip uninstall -y agentkit-controller
if "$VENV/bin/python" -m pip show agentkit-controller; then exit 1; fi
```

Remove the exact disposable virtual-environment and runtime directories only after inspection.

## Running and removing a source checkout

Run Python commands from the checkout root so Python resolves the local `agentkit` package:

```sh
cd /private/tmp/agentkit-offline-checkout
python3 -m agentkit --help
python3 -m agentkit workflow --help
```

The source path resolves resources beside the `agentkit` package. An installed wheel instead provides an `agentkit` console script and resolves immutable bundled resources from site-packages. Copying only the Python package from the checkout remains incomplete.

To uninstall this source-checkout deployment, first verify the two exact disposable paths, leave the checkout, then remove only those paths:

```sh
test "$TARGET" = /private/tmp/agentkit-offline-checkout
test "$RUNTIME" = /private/tmp/agentkit-offline-runtime
cd /private/tmp
rm -r -- "$TARGET"
rm -r -- "$RUNTIME"
```

This removal does not touch global Python, Node, Git, Codex, Claude Code, shell, Keychain, or provider configuration because onboarding did not modify any of them. The wheel procedure changes only its named virtual environment. Workflow roots or portable review packages created elsewhere are retained data and must be reviewed and removed separately by their owner.

## Release blockers and unsupported distribution paths

- No outbound `LICENSE`: review access and private artifact testing do not grant permission for public redistribution.
- No package-index publication, signed release, automatic update or rollback channel.
- No npm release, bundled Node runtime, React/Ink dependency closure, or full-screen interactive TUI.
- No signed artifacts, authenticated publisher identity, notarization, code signing, SBOM, archive importer, or update channel.
- No support claim for Linux, WSL2, Windows, containers, remote workers, GPU workers, or general repository execution.

Compatibility details are in [R3 compatibility](r3-compatibility.md). Runtime/provider boundaries and retained data are in [R3 data flow](r3-data-flow.md).
The [outbound-license review](r3-license-review.md) and [provenance manifest](r3-provenance-manifest.md) define the remaining license gate and files that artifacts must retain.
