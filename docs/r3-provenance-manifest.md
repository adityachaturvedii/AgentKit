# R3 provenance manifest

Review date: 2026-10-01. This manifest describes material distributed from this
repository. Machine-verifiable source facts remain in the linked JSON ledgers;
this document does not replace them.

| Material | Provenance record | Required notice | Distribution status |
|---|---|---|---|
| Adapted pstack procedures | `audit/sources.lock.json` → `pstack`; local source links in five procedure files | `notices/pstack-LICENSE.txt` (`bc957ca6bee02792566a1a028d105e02e247c6e77cf057061674273da77b200e`) | Included |
| Adapted Matt Pocock procedures | `audit/sources.lock.json` → `matt-skills`; local source links in three procedure files | `notices/matt-skills-LICENSE.txt` (`0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5`) | Included |
| Adapted gstack procedures | `audit/sources.lock.json` → `gstack`; local source links in two procedure files | `notices/gstack-LICENSE.txt` (`e56fbb5b3d95756f3fa1cfefa24732ec79f18ece1ad08a4e79e00df57e8b198c`) | Included |
| Adapted OpenHarness Python and terminal files | `agentkit/integrations/openharness/adaptation-map.json`, pinned at `9b2efd795c6aa09f88b0c257d269a9e518da6ae7` | `third_party/openharness/LICENSE` (`dcb4464b75fbeec7fe5e9b13eeadf37a1e813ded33392c6303f091c37da6fa20`) | Included |
| Original AgentKit Python, contracts, domains, evidence formats, and local tests | Repository history and the original-work determinations in `docs/source-audit.md` | Root outbound license, pending maintainer decision | Included for review; public open-source distribution blocked |
| Optional React/Ink terminal and upstream npm lock | `docs/r0-dependency-license-audit.md` | Unresolved per-package notice bundle | Excluded |
| Provider CLIs and SDKs | `docs/cli-source-review.md` | Separately supplied vendor terms | Excluded; no executable or SDK redistributed |

The source lock records twelve adapted upstream candidates that map to nine
local procedure files. Shared targets are deliberate: pstack `how` and `why`
both contribute to `system-investigation`; two Matt sources contribute to
`task-contract`; and pstack plus gstack contribute to `independent-review`.
Every target has a pinned source link and a link to the central notices.

The OpenHarness map has multiple source-to-one-target entries for the terminal
renderer because status and transcript components were adapted into one local
dependency-free renderer. Each entry retains its distinct upstream path and
hash. Local hashes bind the current adapted bytes; changes to those files must
update the map as part of the same review.

The package metadata, when present, must carry all of the following into every
source or binary distribution: the selected root `LICENSE`, this notice file,
the three files under `notices/`, `third_party/openharness/LICENSE`,
`audit/sources.lock.json`, and
`agentkit/integrations/openharness/adaptation-map.json`. Repository presence is
not proof that a built wheel, source archive, npm bundle, or standalone archive
contains them; built-artifact inspection is the release check.
