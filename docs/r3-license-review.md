# R3 outbound-license review

Review date: 2026-10-01. This is an engineering distribution review, not legal
advice. The maintainer must make the outbound-license decision and add the
corresponding root `LICENSE` before public open-source distribution.

## Recommendation

Use the **Apache License 2.0** for original AgentKit work, while retaining every
existing MIT notice for adapted material. Apache-2.0 is permissive, includes an
express patent license and patent-termination terms, and requires preservation
of its license and applicable notices. That is a useful default for a toolkit
intended for public use by small engineering teams and for contributions from
multiple parties.

The imported material identified by this repository is MIT licensed. MIT code
can generally be included in an Apache-2.0 project when its copyright and
permission notices remain with the covered material. AgentKit already retains
those texts and maps each adaptation to a pinned source. The root license should
cover only rights held in original AgentKit work; it must not erase or replace
the upstream MIT terms.

The practical alternatives are:

| Choice | Practical effect for this project |
|---|---|
| MIT | Shortest and simplest permissive option; aligns textually with all currently adapted sources, but contains no express patent grant. |
| Apache-2.0 | Recommended permissive option; adds explicit patent terms and more notice obligations. |
| MPL-2.0 | File-level copyleft; modifications to MPL-covered files generally remain available under MPL, adding compliance work and changing the intended permissive model. |
| GPL/AGPL family | Strong copyleft, with AGPL adding network-use source obligations; a material product-policy change for downstream integrators. |
| Proprietary or source-available terms | Can reserve more rights, but should not be described as open source unless the selected terms meet the Open Source Definition. |

No option should be inferred from the repository's visibility, from an upstream
license, or from this recommendation. Copyright ownership and contributor
agreements, trademarks, patents outside the license grant, export rules, and
the terms of separately supplied provider CLIs remain separate questions.

## Current closure

- `audit/sources.lock.json` pins pstack, Matt Pocock's skills, and gstack by
  commit, candidate path, file hash, archive hash, decision, and retained
  notice path.
- Each adapted procedure names its upstream candidate at the pinned commit and
  links `THIRD_PARTY_NOTICES.md`.
- `agentkit/integrations/openharness/adaptation-map.json` pins OpenHarness and
  records the upstream and local hash for each adapted file. The complete
  upstream MIT text is retained at `third_party/openharness/LICENSE`.
- The Python runtime has no declared third-party package dependency. The
  executable terminal slice declares no npm dependency and imports only Node
  built-ins and local modules.
- The optional React/Ink frontend and its 80-package upstream lock are excluded.
  A future bundle needs its own resolved dependency inventory, license texts,
  install-script review, pinned build, and distributable asset review.

The provenance detail and exact notice linkage are summarized in the
[R3 provenance manifest](r3-provenance-manifest.md). Offline tests verify the
retained notice bytes, adaptation hashes, per-procedure source links, and the
dependency-free terminal manifest.

## Release gate

Public open-source distribution remains blocked until the maintainer:

1. selects the outbound terms and adds the exact root `LICENSE` text;
2. updates the README and this review from “unselected” to the chosen terms;
3. confirms the copyright holder/name and any contributor policy;
4. builds the distribution artifacts and verifies that the root license,
   `THIRD_PARTY_NOTICES.md`, `notices/`, `third_party/openharness/LICENSE`,
   `audit/sources.lock.json`, and the OpenHarness adaptation map are included;
5. reruns the offline distribution-license tests against the built artifacts.

Signing, notarization, package-index publication, and the optional full-screen
frontend are separate gates and are not implied by selecting a license.
