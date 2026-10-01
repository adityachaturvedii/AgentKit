# R3 portable review package

Status: P11 is implemented and fixture-tested. P12 (the complete plain/JSON/terminal workflow) and P13 (distribution and compatibility) remain open.

AgentKit can export a completed R2 repository-delivery task into a plain, private review folder. Export requires the authoritative controller task to be `awaiting_pr_approval`, its local approval to remain unset, and every required verification, review and package record to be passed, current and bound to the exact candidate revision.

```sh
python3 -m agentkit package export \
  --workflow /absolute/path/to/workflow \
  --task-id TASK_ID \
  --output /fresh/path/review-package

python3 -m agentkit package verify /path/to/review-package
```

The destination must not exist. Export does not approve, publish, apply or execute the candidate. It omits controller storage, raw provider events, captured environments and managed-repository paths. Known secret-like values in summaries and evidence are redacted; a secret-like diff is rejected because changing a diff would make review misleading. Pattern redaction is defense in depth, so operators must still keep secrets out of task input and candidate changes. The folder contains:

- a sanitized approval summary with base/head revisions, full diff, requirements, limitations, review references, resource observations and proposed PR text;
- the same full diff as a separate `candidate.diff` for ordinary review tools;
- passed, revision-bound verification, review and package evidence records;
- an explicit requirement-to-evidence matrix;
- provenance fields and offline replay guidance; and
- a manifest of SHA-256 hashes and byte counts.

The offline verifier reads regular files only. It rejects symlinks, undeclared or missing files, traversal paths, oversized inventories/files, malformed JSON, hash or size changes, inconsistent revisions, missing or failed required evidence, requirement-matrix drift and a diff that differs from the approval record. Import performs no subprocess or candidate-code execution and grants no authority.

Integrity is local and unauthenticated. The verifier establishes that the folder is internally consistent with its manifest; it does not prove who created it or that recorded commands really ran. The original controller database remains authoritative. Signed attestations, authenticated team approvals, archive import, original-checkout application, publication and a polished terminal workflow are later work.

## Fixture validation

Disposable Git/Python workflows cover successful export and CLI verification, import with subprocess creation disabled, local-path removal, secret-pattern redaction, byte tampering, undeclared files, symlinks, stale and absent evidence, escaping manifest paths, malformed internal JSON and inconsistent requirement records. These tests use deterministic providers and a fixture verifier. They spend no inference quota and do not broaden the supported repository or sandbox profile.
