# Third-party notices

AgentKit contains adaptations of the MIT-licensed material listed below. Each
linked file retains the complete upstream copyright and permission notice. These
notices apply to the identified adaptations; they do not supply an outbound
license for original AgentKit work.

| Upstream | Pinned revision | Adapted AgentKit surface | Complete notice |
|---|---|---|---|
| [Lauren Tan / pstack](https://github.com/backnotprop/pstack) | `157aae39a733135e93d8b5b19ff62c6a84b0ad56` | `system-investigation`, `interface-design`, `change-impact`, `measured-optimisation`, and `independent-review` procedures | [MIT license](notices/pstack-LICENSE.txt) |
| [Matt Pocock / skills](https://github.com/mattpocock/skills) | `74ca5fe077456a0b3b2f5310cf9430999fd0b5fd` | `task-contract`, `behavioral-testing`, and `fault-diagnosis` procedures | [MIT license](notices/matt-skills-LICENSE.txt) |
| [Garry Tan / gstack](https://github.com/garrytan/gstack) | `a6b3a57512ca6d5c6aa5b68f74f736195021f96e` | `independent-review` and `browser-verification` procedures | [MIT license](notices/gstack-LICENSE.txt) |
| [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) | `9b2efd795c6aa09f88b0c257d269a9e518da6ae7` | provider-profile, context-discovery, frontend-protocol, private-write, backend-seam, and terminal-presentation adaptations | [MIT license](third_party/openharness/LICENSE) |

The exact source candidates, archive and file hashes, decisions, and notice
paths for the procedure adaptations are recorded in
[`audit/sources.lock.json`](audit/sources.lock.json). Their dependency boundary
and changes are described in the [source audit](docs/source-audit.md), and every
adapted procedure links its upstream file at the pinned revision.

OpenHarness file-to-file provenance, upstream hashes, local hashes, and change
summaries are recorded in
[`agentkit/integrations/openharness/adaptation-map.json`](agentkit/integrations/openharness/adaptation-map.json).
The associated dependency review is in the
[OpenHarness license audit](docs/r0-dependency-license-audit.md).

No upstream scripts, binaries, package locks, installed dependencies, or
complete plugin bundles are redistributed. The shipped terminal slice uses
only Node built-ins and local files; the optional React/Ink frontend is not part
of this distribution. Delivery-evidence, domain procedures, schemas, and helper
code identified as original in the audits are original AgentKit work. No
endorsement by an upstream author is implied.

An outbound license for original AgentKit work has not yet been selected. Until
the maintainer adds one, the retained third-party licenses apply only to their
respective upstream material and the repository is not ready for public
open-source distribution. See the [R3 license review](docs/r3-license-review.md).
