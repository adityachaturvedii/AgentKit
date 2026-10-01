# R3 P11 validation report

Date: 2026-10-01. Branch `implementation/r3-portable-package`, dedicated worktree `/Users/aditya/agentic/agentkit-r3-package`, based on integration revision `d54d1da815352d9fa0fdda3a45117b07b2bfda1f`.

## Scope and result

This milestone implements only P11: export of an R2 `awaiting_pr_approval` result to a portable plain folder and offline consistency verification. It does not complete P12's task terminal, distribution, signing, shared identity, import/application, publication or general repository support.

The exporter checks authoritative task state, absence of approval, exact head revision, nonempty verification requirements, passed current evidence and intact controller artifacts before creating the folder. The verifier performs bounded regular-file reads and checks its inventory, hashes, sizes, revision bindings, evidence kinds/statuses, requirement mapping and duplicated diff. Neither path runs candidate code or grants approval.

## Evidence

| Check | Result |
|---|---|
| `python3 -m unittest tests.test_portable_package -v` | 8 passed |
| `python3 -m unittest discover -s tests -v` | 235 total: 232 passed, 3 expected managed-environment skips |
| `python3 -m agentkit check` | Passed: 10 skills, 7 domains, 10 examples, 3 pinned sources |
| `PYTHONPYCACHEPREFIX=/tmp/agentkit-r3-pyc python3 -m compileall -q agentkit tests` | Passed |
| `git diff --check` | Passed |

The three full-suite skips are unchanged host checks: two macOS Seatbelt boundary cases cannot initialize beneath the managed outer sandbox, and loopback preview binding is unavailable there. P11 changes no execution boundary, so their earlier revision-specific host evidence is not promoted to this revision. No provider call, login, network access or live inference was used.

Focused disposable cases cover a complete deterministic Git/Python delivery, CLI verification, subprocess-disabled import, private-path removal, secret-pattern redaction, changed bytes, undeclared files, symlinks, package-root aliases, traversal, stale/missing evidence, missing source artifacts, removed verification requirements, malformed JSON and requirement drift.

## Security and interpretation

The package excludes controller storage, managed-repository paths, raw provider events, captured environments and raw login material. Known secret patterns in ordinary records are redacted, while a candidate diff containing such a pattern blocks export rather than silently changing review content. This is defense in depth, not comprehensive secret detection. Files use private creation modes. Bounds are 100 declared content files, 5 MiB per file and 20 MiB total content.

SHA-256 manifest verification detects changes relative to the included manifest. Because the manifest is not signed or anchored in an authenticated service, a party can replace both content and manifest. The offline result therefore means internally consistent and non-executing; it is not proof of authorship, command execution or approval. The local controller database and its content-addressed artifacts remain authoritative.

## Gate

P11 meets its acceptance gate: tampering, stale or missing evidence, escaping paths and missing required verification fail, and package verification executes no candidate code. P12 and P13 remain the next R3 work. The supported runtime scope remains the R2 trusted, enrolled, standalone Python-library fixture path on the tested macOS profile; arbitrary repositories and original-checkout application remain unsupported.
