# R4 exploratory pilot protocol

Status: interface and collection protocol specified; comparative collection has not started.

This protocol evaluates whether AgentKit's evidence changes the total human work and observed defect outcomes for small repository tasks. It compares a competent direct provider-CLI workflow with AgentKit on tasks declared before either condition begins. It is an exploratory pilot, not a powered benchmark. Its output may describe this cohort and these runs; it cannot establish statistical superiority, general productivity, causality, or performance on untested repositories.

The strict machine-readable `pilot init` input is [`examples/pilot-protocol.json`](examples/pilot-protocol.json). It uses synthetic identities, validates against the current offline ledger, and grants no authority for model calls, repository access, or artifact publication. The richer measurement, consent, and privacy rules below govern collection records and operator procedure rather than adding unchecked fields to that closed input schema.

## Freeze before collection

`pilot init` validates one protocol and writes a private frozen record. The frozen identity covers the complete strict document: pilot identity, title, randomization seed, consent version, provider-disclosure and retention-policy hashes, two conditions, consented pseudonymous participants, and tasks with project, base, task-contract, protected-acceptance, stratum, and follow-up-window identities. Each condition freezes provider, model, effort, execution profile, call limit, and time limit. A recorded observation binds the frozen protocol and its generated assignment before it can be accepted.

After the first assignment exists, changing a covered field creates a new protocol and identity. It never updates collected runs in place. A changed repository base, request, acceptance oracle, environment, allowance, provider, model, or effort marks the affected pair as a deviation. The run remains in the complete denominator, but it cannot silently enter a matched summary.

Acceptance is maintained independently of both implementation conditions. Neither implementer receives protected expected patches, hidden checks, planted-defect labels, or another condition's result. The same oracle and adjudication rule apply to both members of a pair. The oracle hash is frozen before assignment; changing it after observing a result invalidates the match.

## Deterministic assignment and fair comparison

The assignment unit is a participant-task. A frozen seed, task stratum, and deterministic balanced assignment choose condition, participant, and within-task order. The assignment ledger is created before execution and is retained even when a run never launches. For each task the two conditions are assigned to distinct participants, so the same person does not solve that task twice. A future nonrandom allocation requires a new protocol and an explicit limitation; it cannot be substituted into this ledger after initialization.

A matched pair has the same task, project, base, task contract, protected acceptance, provider, model, effort, execution profile, call limit, and time limit. The initializer rejects unequal condition configuration. Requested and reported provider settings remain separate. A requested mismatch is rejected; a non-null reported provider/model/effort that differs from the frozen request is counted as a deviation, while an unavailable reported value remains missing. AgentKit must not receive free calls, review, repair, or operator work that is omitted from the direct condition's accounting.

The workflows may differ by design. AgentKit can produce structured evidence and the direct workflow need not mimic its internals. Both conditions still face the same outcome oracle and total declared allowance. Workflow-specific setup, review, repair, and packaging work is measured rather than normalized away.

## Complete denominator and measurement

Every observed allocated run ends with one explicit outcome: `completed`, `failed`, `blocked`, `cancelled`, `withdrawn`, `timed_out`, `authentication_required`, or `not_run`. An allocated assignment without an observation remains an explicit missing denominator cell. Authentication can also be an individual attempt status and does not become invisible merely because a later retry completes. Environment, provider, tool, operator, and policy failures remain in the ledger. Every retry and provider launch is a separate attempt; retaining a successful retry never removes the failed attempt that preceded it.

The report shows assigned denominators, observations, missing cells, terminal outcomes, attempts, acceptance, requested-versus-reported setting deviations, and call/time-limit deviations for each condition. It reports first-pass acceptance separately from final acceptance and merge status. An unaccepted candidate uses `not_assessed` where acceptance was not assessed. An observation without completed follow-up has escaped defects unknown, not zero.

Human effort records active setup, operator-intervention, review, and human source-edit minutes separately, plus an intervention count. Operators use the common timer procedure in the consented study materials; automated execution and waiting belong in wall time, not active human time. Values cannot be negative, and unsuccessful runs count all work already spent. A measured zero is distinct from an unavailable duration, which uses a null value and reason where the schema permits it.

Finding and repair totals are operator-classified observations: true positive, false positive, unresolved, repair-cycle, and unnecessary-repair counts. The current minimal ledger does not store finding-level evidence links or repair-level identities, so these aggregates are not independently traceable and must not be represented as adjudicated audit records. It accepts one immutable final observation per assignment and has no amendment API. Collection therefore submits that record after the predeclared escaped-defect window; until then the assignment remains visibly missing rather than reporting zero defects. A completed follow-up is accepted only for a completed candidate with passing protected acceptance and UTC timestamps proving that the frozen task-specific window elapsed.

Usage keeps requested and observed model settings, every provider attempt, wall time, nullable token categories, estimates, and billed cost separate. A provider that omits usage produces a null value counted explicitly by the report. The minimal schema records an unavailability reason for total wall time, but not for every nullable provider or human-effort field; that missing provenance is a collection limitation. Unknown native retries or billed costs remain unknown and never become zero.

## Participant discovery, consent, and privacy

Consent is required before repository inspection, task capture, or provider use. The record identifies the consent text version and discloses the selected source/context sent to the provider, local retention, provider-side processing and retention, any recording, and the withdrawal route. Repository/task authorization and evaluation-artifact sharing are separate choices. Publicly readable code is not permission to upload task data or transcripts. Declining artifact sharing blocks portable or public evaluation export while leaving only the retention explicitly covered by consent.

Discovery interviews ask whether a new operator can complete the supported flow and whether another reviewer can explain what they trust, distrust, and still need to inspect. Interview observations remain distinct from task performance. Missing consent blocks collection and is not recorded as a task failure.

Real credentials, production data, login transcripts, and authorization codes are prohibited. Before collection, an external authorized preflight must cover selected tracked content and secret-like filenames; ignored/untracked content, symlinks, task text, prompts, outputs, diffs, filenames, notes, and exports also require explicit exclusion or sanitization as applicable. Exclusion must be bound to the protocol/run identity, and retained or exported artifacts must be checked for synthetic canaries. The P14 ledger neither inspects repositories nor performs these scans, so their evidence remains a prerequisite outside this implementation. Even completed checks reduce accidental capture; they do not prove comprehensive secret or credential isolation.

## Implemented offline CLI contract

The P14 command group implements the offline frozen ledger and descriptive report interface. The executable commands and deterministic fixtures exercise initialization, status, immutable observation and feedback records, and reporting. They do not launch a provider, inspect a repository, run project code, publish artifacts, or grant collection authority.

```console
python3 -m agentkit pilot init --root /private/tmp/agentkit-pilot --protocol docs/examples/pilot-protocol.json
python3 -m agentkit pilot status --root /private/tmp/agentkit-pilot
python3 -m agentkit pilot record --root /private/tmp/agentkit-pilot --observation /absolute/path/run-record.json
python3 -m agentkit pilot feedback --root /private/tmp/agentkit-pilot --feedback /absolute/path/feedback-record.json
python3 -m agentkit pilot report --root /private/tmp/agentkit-pilot
```

`init` validates and freezes the protocol, including local-evaluation and artifact-sharing choices, creates its assignment ledger, and fails if the root already exists. `status` is read-only and displays the frozen identity, assignment/observation/feedback counts, missing observations, and deviation count without changing or launching a run. `record` appends one validated immutable observation from `--observation`; it rejects mutation, an unknown or already-recorded assignment, stale bindings, and fields outside the closed schema. `feedback` appends one structured consent-scoped discovery or reviewer record from `--feedback`. `report` reconciles expected assignments with all records and prints a descriptive JSON report; its denominators and missing counts prevent an incomplete ledger from appearing complete, and its deviation counts keep a changed reported configuration visible.

All five operations are local. State and reports are private by default. Export or publication remains a separate future action and requires the participant's artifact-sharing choice plus explicit publication authorization.

## Reporting rules

Immutable observation files preserve each run. The derived report displays matched-resource deviations, missingness by metric and condition, and denominators beside every rate. It includes failures and work spent before failure. Summaries never filter to accepted tasks without labeling that subset, convert missing observations to zero, infer billed cost, or treat an incomplete defect window as zero escaped defects.

This pilot predeclares no significance test and no universal success threshold. Small differences are observations for product discovery. Report text uses terms such as “in the recorded pilot runs” and names limitations. It does not use “statistically significant,” “proved,” “superior,” “X% more productive,” or causal language. A later powered study would require a new protocol, sample-size rationale, independent cases, and an analysis plan frozen before collection.

## Current authority and limits

No actual pilot collection, live inference, credential access, personal or real-repository onboarding, participant recruitment, recording, provider upload, public artifact sharing, or publication was performed or authorized by this documentation work. The example uses synthetic identities. Existing historical evaluations remain historical evidence and are not retroactively converted into P14 pilot observations.
