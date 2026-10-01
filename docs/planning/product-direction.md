# Product direction for the first usable release

Status: proposal informed by the user's audience and sequencing choices. This is not a claim that the planned capabilities exist.

## Promise

Agentkit helps small engineering teams and open-source maintainers turn coding-agent changes into review-ready work, with controlled execution, independently executed checks and portable evidence tied to the exact candidate revision.

The user can ask for a change in an enrolled repository, inspect the scope and resource allocation, run it, and receive a concise package explaining the change, its verification and remaining uncertainty. A different engineer can inspect that package without reading the agent's conversation history.

Existing repositories come first. Creating products from briefs remains a first-class destination: it uses a fresh managed repository and the same contract, implementation, verification, review and packaging pipeline. The Breakout brief remains a later web acceptance case, not a prerequisite for the first repository release.

## Users and first work

The initial audience is a small team with trusted local operators plus a limited public open-source preview. Operators and approvers may be different people; the first version supports exchanging evidence, not a shared mutable run database or authenticated organizational RBAC.

Start with small bug fixes, regression tests, narrowly scoped features and maintainability changes with observable acceptance. Default recommendation: one Python library profile first, followed by one JavaScript/TypeScript profile based on actual pilot projects. Language order is provisional; it can change before onboarding implementation without changing the architecture.

Exclude production credentials, production databases, deployment, repository-wide modernization, destructive migrations, remote/GPU work and unattended publication from the first release. A one-line authorization to work on a repository does not authorize every script, network endpoint or local file it can reference.

## What the user should experience

1. Enroll an explicitly named repository. Readiness inspection explains what is recognized, what is excluded, which checks could run and which capability is missing.
2. Supply a task. The proposed contract separates requirements from assumptions and shows acceptance, permitted changes, provider routing, limits and potential provider data exposure.
3. Start once. Routine actions inside the enrolled scope proceed without repeated permission dialogs. Material ambiguity or required authority expansion produces one actionable checkpoint.
4. See stage, current assignment, observed usage, remaining allocation and the next action. A lost terminal does not imply safe replacement of a possibly running process.
5. Receive a package: exact base/head, changed files and diff, requirement/check mapping, review findings, resource observations, limitations and replay instructions.
6. Share the package for review. PR creation and merging remain separately authorized actions; the preview has no live publication integration.

## Product claims and limits

| Say | Do not imply |
|---|---|
| Local controller, workspaces and evidence | Hosted-model context never leaves the computer |
| Independent execution of declared checks | Tests prove every requirement or establish universal correctness |
| Separate reviewer, optionally a different provider under policy | Different providers have independent errors or guarantee detection |
| Evidence bound to a revision and policy | Hashes authenticate an untrusted operator or prove commands really ran |
| Explicit authorization and measured resource use | Exact monetary or token ceilings through unsupported CLI controls |
| Portable artifacts | Portable live sessions, universal crash containment or cross-platform isolation parity |
| Review-ready result with uncertainty visible | Every change is safely reducible to one blind approval click |

Acceptance tests are an engineering problem, not something we can outsource to the implementer's self-report. Existing repo tests, agent-proposed tests, protected acceptance and manual observations must remain distinguishable. A passed but empty test discovery is not sufficient acceptance.

## Small-team scope

Implement a portable project-policy file and immutable resolved policy snapshot per run. Repository policy is proposed data until a local trusted operator enrolls its content hash. A worker cannot approve a modified policy. Peers can share the profile, task brief and evidence package; each machine independently validates its local execution capability and provider settings.

Record operator/approver labels accurately as unauthenticated local identities until stronger identity is implemented. Do not advertise central enforcement: a machine owner can alter local software. Signed organizational policy, multi-user authorization, central scheduling and enforced company-wide gates are later capabilities.

Public users need installation that makes no silent global changes, a no-inference example, actionable compatibility errors, clear data-flow documentation, supported-version information, attribution and a license that matches the chosen distribution model. Decide the original-code license before public distribution; OpenHarness's MIT license does not settle our own licensing choice or every bundled dependency's terms.

## Reuse-first commitment

OpenHarness is a substantial source foundation. Prefer porting its usable UI, configuration, context and execution infrastructure over designing equivalents from scratch. Keep a file-level source/adaptation ledger and import upstream tests with adapted components. Upstream updates are pinned, reviewed changes, never automatic updates inside a running task.

Reuse is measured by working subsystems and reduced maintenance work, not by a quota of copied lines. Existing Agentkit mechanisms may also be replaced if a reused implementation passes the same behavioral contract with lower maintenance cost. Neither codebase has automatic priority over the product requirements.

## Evaluation and success

The first success is a new operator completing a supported repository task without developer intervention, followed by another engineer understanding the package and identifying its limitations. A successful fixture or attractive game is insufficient evidence of this outcome.

Pilot evaluation compares competent direct-CLI work with Agentkit on predeclared tasks and matched provider/model configurations where possible. Record:

- First-pass acceptance without human source edits; label this separately from actual merge rate.
- Active reviewer minutes, setup time, operator interventions and total human time per accepted task.
- Completion/failure/blocked rates, wall time and all provider attempts including failures.
- Escaped defects, false-positive findings and unnecessary repairs.
- Reported usage categories, cost estimates and unavailable billed costs.
- Runtime, policy, skills, acceptance and candidate identities, including omitted or manual checks.

Randomize assignment/order where practical, avoid the same person solving the same task twice, retain failures in the denominator, and distinguish exploratory pilot findings from a powered benchmark. Freeze the evaluation method before collecting comparative results. Public code is not permission to upload private task data or transcripts; contribution of evaluation artifacts is explicit and opt-in.

Recruit a few pilot users during onboarding design, then expand toward ten weekly users if early results justify it. Do not postpone discovery until Linux is complete. If reviewers cannot explain what they trust in the package, improve acceptance and presentation before increasing autonomy.

## Corrections to the supplied vision

The vision's assurance focus is retained; these corrections prevent unsupported roadmap decisions:

- Bounded concurrent scheduling already exists in Agentkit; multi-user/RBAC/CI support does not. See the current controller and Phase 4 evidence.
- API credentials are a future explicit mode, not the present supported default. Existing permission to use subscriptions is not permission to add paid fallback.
- First-party provider neutrality is not an exclusive differentiator: GitHub publicly supports Claude and Codex in Agent HQ. [Official announcement](https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/).
- Current Anthropic guidance distinguishes end-user login to the unmodified Claude Code binary from credential intermediation and third-party product/API use. Recheck exact terms at implementation/release; do not extract CLI tokens or infer authorization from another project's implementation. [Official guidance](https://code.claude.com/docs/en/legal-and-compliance).
- The 2025 Stack Overflow primary results report 33% trust, 66% frustration with nearly correct output and 45% time-consuming debugging. These survey observations do not establish willingness to buy Agentkit. [Survey](https://survey.stackoverflow.co/2025/ai).
- METR's follow-up reported new estimates with serious selection/measurement limitations. Use it to motivate careful evaluation, not a universal productivity claim. [Research update](https://metr.org/blog/2026-02-24-uplift-update/).
- Source-available with a non-compete restriction is not the same licensing choice as open source. [OSI definition](https://opensource.org/osd).

Funding figures, market size, competitor valuations and willingness-to-pay remain outside the engineering baseline. We are not adopting them as verified facts.
