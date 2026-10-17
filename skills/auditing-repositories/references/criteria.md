# Audit criteria

Walk every criterion below. For each one, decide whether it applies, look for evidence, and assign a
status. The guide column links to the section that explains the rule; read it when the criterion
applies and the evidence is not obvious. IDs are stable: they are never renumbered or reused.

## Applicability

| Stage | Expected outcome |
| --- | --- |
| From the start | Reproducible environment, first tested feature, clear structure, and checks appropriate to the stack |
| Before publishing or use | Protected permissions and data, verified delivery, support and recovery where applicable |
| When needed | Contracts between modules, coordination, observability, and measured capacity |

Exposure can bring a control forward: secrets, real data, or external users require the relevant
measures from first use. Determine the security level with the
[proportionate security](standard.md#proportionate-security) table.

A criterion is "not applicable" only with a reason taken from the repository, such as "no persistent
data" or "level 0 experiment". "Not checked" is never a reason: report the criterion as pending
verification instead.

Some conditions live in hosted settings that the audit may not be able to read, such as a merge
queue or branch protection. Decide them from repository evidence. When nothing in the repository
indicates the condition (no `merge_group` trigger, no remote), the criterion is not applicable for
that reason, and the report names the unread settings under Limitations. When the repository
indicates it, for example a pull request workflow for a shared branch, report pending verification.

That rule covers only conditions that depend solely on hosted settings. A criterion whose condition
the repository shows still applies when its evidence is remote: CI-06 applies whenever CI
configuration exists, and without a remote or a readable run it is pending verification.

## Repository and structure

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| REPO-01 | README states the purpose, requirements, and install, run, and validation commands, and those commands work from a clean clone | Always | [standard](standard.md#repository) |
| REPO-02 | Agent instructions are short and consistent with the README and the actual commands | Agents contribute | [standard](standard.md#repository) |
| REPO-03 | Each rule or state has one location; other documents link to it instead of repeating it | Always | [standard](standard.md#repository) |
| REPO-04 | Code, configuration, tests, and lockfiles are committed; environments, secrets, logs, and builds are excluded; examples use fictional values | Always | [standard](standard.md#repository) |
| REPO-05 | Decisions with alternatives and consequences are recorded where maintainers will find them | Such decisions exist | [standard](standard.md#repository) |
| REPO-06 | Comments explain intent and non-obvious invariants; documentation is proportionate and matches the code | Always | [standard](standard.md#repository) |
| REPO-07 | Each incident leaves a recorded lesson with its cause and the mechanism that now prevents it, or a named follow-up | Incidents occurred, as history, issues, or postmortems show | [standard](standard.md#repository) |
| REPO-08 | Each area has an owner, and someone other than the author approves each change, always for security, release, and policy changes | Several contributors, human or agent | [standard](standard.md#repository) |
| STRUCT-01 | Files are organized by responsibility; the root holds only entry points, manifests, lockfiles, and configuration that must live there, with exceptions recorded | Always | [structure](structure.md#locations-and-boundaries) |
| STRUCT-02 | Directories with more than 20 maintained source files have a recorded cohesion review | Threshold exceeded | [structure](structure.md#review) |
| STRUCT-03 | Allowed dependencies between modules are defined, free of cycles, and enforced by import contracts where useful | Several real modules | [structure](structure.md#locations-and-boundaries) |
| STRUCT-04 | Temporary files and scripts have a purpose, owner, and removal condition | Temporary files exist | [structure](structure.md#temporary-files-and-enforcement) |

## Quality controls

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| QUAL-01 | Installation is reproducible and one validation command is shared by local development and CI | Always | [standard](standard.md#quality) |
| QUAL-02 | Formatting, linting, type checking, tests, and builds appropriate to the stack exist, each with configuration, a local command, CI execution, and a demonstrated rejected violation | Always; depth grows with stage | [quality](quality.md#controls-by-stack) |
| QUAL-03 | Controls fail on violations: no ignored exit codes, non-blocking severities for blocking rules, or commands that always succeed | A control exists | [quality](quality.md#controls-by-stack) |
| QUAL-04 | Controls cover all maintained source, scripts, tests, and new files; exclusions are explicit by path and purpose | A control exists | [quality](quality.md#scope-and-exceptions) |
| QUAL-05 | Each suppression or exception names a path or symbol, rule, reason, owner, and removal condition; there are no blanket ignores or automatic baselines | Suppressions exist | [quality](quality.md#scope-and-exceptions) |
| QUAL-06 | Size and complexity limits have an agreed counting method before they block and are treated as design signals | Limits adopted or large units exist | [quality](quality.md#starting-limits) |
| QUAL-07 | A coverage threshold measures branches and its boundary has been tested with the actual tool | Coverage gate exists | [quality](quality.md#starting-limits) |
| QUAL-08 | Changes that weaken controls are justified separately from functional changes and reviewed | History or PRs available | [quality](quality.md#rules-for-changes-and-agents) |
| QUAL-09 | Type escapes and lint suppressions are bounded and justified; external data is validated in adapters | Typed or linted code | [quality](quality.md#rules-for-changes-and-agents) |

## Dependencies

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| DEP-01 | The runtime and dependency versions are pinned and the lockfile is committed where the package manager supports it | Dependencies exist | [standard](standard.md#quality) |
| DEP-02 | Production dependencies are justified by need, alternatives, maintenance, license, and size | Dependencies exist | [quality](quality.md#rules-for-changes-and-agents) |
| DEP-03 | Dependencies have an owner and a periodic review; automated update proposals are configured | Dependencies exist | [quality](quality.md#dependency-maintenance) |
| DEP-04 | Resolved dependencies are audited for vulnerabilities across relevant groups and platforms; a failed query is not an approved audit | Dependencies exist; required before distribution | [quality](quality.md#dependency-maintenance) |
| DEP-05 | Licenses and notices of transitive dependencies and bundled binaries are checked; downloaded tools are pinned and hash-verified | Distribution or downloaded tools | [quality](quality.md#dependency-maintenance) |

## Tests and evidence

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| TEST-01 | Tests exercise public behavior, relevant failures, and limits, and name the invariant they protect | Always | [validation](validation.md#useful-tests) |
| TEST-02 | Unit tests are deterministic: synthetic data, temporary resources, a controlled clock, and no network or arbitrary waits; integrations are separated | Tests exist | [validation](validation.md#useful-tests) |
| TEST-03 | State changes are tested for duplicates, retries, and partial failures; processes are tested for cleanup on timeout | Persistence, concurrency, or subprocesses | [validation](validation.md#useful-tests) |
| TEST-04 | Each kind of change has a matching check: contract regeneration and compatibility, real UI flows and accessibility, clean package installation | Matching change types exist | [validation](validation.md#environment-and-scope) |
| TEST-05 | Tests and tools resolve paths from the project, without personal paths or sibling repositories | Always | [validation](validation.md#environment-and-scope) |
| TEST-06 | Recorded results state the revision, command, environment, and outcome, and distinguish skipped, timed-out, and interrupted runs from passes | Results are recorded or claimed | [validation](validation.md#recording-and-reusing-results) |

## CI

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| CI-01 | CI installs with a pinned runtime and dependencies and runs the same commands as local development | Shared repository | [ci](ci.md#minimal-pipeline) |
| CI-02 | Third-party actions and images are pinned by full commit SHA or digest | CI exists | [ci](ci.md#minimal-pipeline) |
| CI-03 | Token permissions are minimal per job and checkout does not persist credentials | CI exists | [ci](ci.md#minimal-pipeline) |
| CI-04 | Jobs have timeouts; obsolete PR runs are cancelled without cancelling deliveries | CI exists | [ci](ci.md#minimal-pipeline) |
| CI-05 | Workflows and CI scripts are validated with appropriate linters | CI exists | [ci](ci.md#minimal-pipeline) |
| CI-06 | CI ran and passed on the audited revision; a run that did not start or was skipped is not a pass | CI exists | [ci](ci.md#require-real-results) |
| CI-07 | Required checks are enforced by branch protection or rulesets with the correct names and source, and bypasses are reviewed | Shared default branch | [ci](ci.md#require-real-results) |
| CI-08 | Required checks report for every relevant change: path filters, conditional jobs, and aggregators cannot turn a missing or failed result into success | Required checks exist | [ci](ci.md#require-real-results) |
| CI-09 | With a merge queue, required workflows run on `merge_group` and test the combined candidate | Merge queue used | [ci](ci.md#require-real-results) |
| CI-10 | Untrusted code never runs with secrets, privileged runners, or `pull_request_target`; publication is separated from PR validation | CI with secrets or publication | [ci](ci.md#privileges-and-delivery) |
| CI-11 | Changes to protected policy (controls, workflows, ignores) are checked by a guard from the trusted base | Risk warrants it | [ci](ci.md#protect-policy-when-risk-warrants-it) |

## Security

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| SEC-01 | The exposure level (0–3) can be identified and the controls match it | Always | [standard](standard.md#proportionate-security) |
| SEC-02 | Inputs are validated and authorization is enforced per resource; external events are authenticated | Inputs from users, networks, or other systems | [standard](standard.md#proportionate-security) |
| SEC-03 | Time, attempts, and size are bounded; retryable writes define idempotency and conflict handling | Services, APIs, or jobs | [standard](standard.md#proportionate-security) |
| SEC-04 | Debugging and administration are disabled by default in public environments | Public deployment | [standard](standard.md#proportionate-security) |
| SEC-05 | No credentials appear in code, configuration, examples, logs, packages, or history; exposed credentials were rotated | Always | [standard](standard.md#proportionate-security) |
| SEC-06 | Content, history, artifacts, and resolved dependencies are reviewed for secrets and vulnerabilities before distribution | Level 2 or higher, or distribution | [standard](standard.md#proportionate-security) |
| SEC-07 | The license, support, and a working reporting channel in SECURITY.md are defined | Public or distributed | [standard](standard.md#proportionate-security) |
| SEC-08 | Level 3 adds a threat model, independent review, traceability, and rehearsed recovery | Level 3 | [standard](standard.md#proportionate-security) |
| SEC-09 | Model features version prompts, schemas, and evaluations; validate outputs; bound tools, cost, time, and retries; and treat retrieved content as data | The product uses models or LLMs | [architecture](architecture.md#products-with-models-or-llms) |

## Delivery and operations

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| DEL-01 | Builds identify the validated revision and use locked dependencies | Artifacts are built | [standard](standard.md#delivery-and-operations) |
| DEL-02 | Artifact contents are reviewed and installed outside the development tree, without secrets, private fixtures, caches, or local configuration | Artifacts are distributed | [standard](standard.md#delivery-and-operations) |
| DEL-03 | Releases are authorized, versioned, and record their changes | Releases exist | [standard](standard.md#delivery-and-operations) |
| OPS-01 | Services document configuration, health, logs, migrations, and rollback | Deployed service | [standard](standard.md#delivery-and-operations) |
| OPS-02 | Persistent data has tested backup and restoration, and agreed acceptable loss and downtime | Persistent data | [standard](standard.md#delivery-and-operations) |

## Architecture

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| ARCH-01 | Business rules are independent of network, disk, processes, and SDKs; imports do not start services; there are no layers that only forward calls | Application code | [architecture](architecture.md#contracts-effects-and-resources) |
| ARCH-02 | Schemas are validated at inputs, persistence, and integrations, and compatibility is tested when they change | Integrations or persistence | [architecture](architecture.md#contracts-effects-and-resources) |
| ARCH-03 | Configuration is centralized; times are timezone-aware; migrations are compatible with deploy and rollback; transactions and pools are bounded | Matching components exist | [architecture](architecture.md#contracts-effects-and-resources) |
| ARCH-04 | Tasks, threads, and processes have ownership, timeouts, cancellation, and cleanup; there are no unsupervised tasks or blocking calls in async code | Concurrency | [architecture](architecture.md#contracts-effects-and-resources) |
| ARCH-05 | Errors are observable; broad catches exist only at justified isolation boundaries; retries are bounded | Application code | [architecture](architecture.md#contracts-effects-and-resources) |
| ARCH-06 | Added complexity such as caches, queues, services, or monorepos answers an observed need with evidence | Such components exist | [architecture](architecture.md#start-small) |

## Performance and capacity

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| PERF-01 | Performance and capacity claims rest on measurements with a defined load, budget, baseline, and comparison | Claims exist or performance matters | [architecture](architecture.md#verifiable-optimization) |
| PERF-02 | Services measure errors, p95/p99 latency, saturation, and volume, and were tested under sustained load, peaks, and recovery | Service in operation | [architecture](architecture.md#verifiable-optimization) |
| PERF-03 | Critical paths have a stable performance regression check | Performance-sensitive paths | [architecture](architecture.md#verifiable-optimization) |

## History, agents, and tooling

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| HIST-01 | Commits have one purpose, leave a valid revision, and stay reviewable in size or record a reviewed exception | History available | [commits](commits.md#limits) |
| HIST-02 | Commit messages follow a consistent convention, enforced if the project adopted one | History available | [commits](commits.md#naming) |
| HIST-03 | Shared history is preserved; rewrites are authorized and pushed with an explicit lease | Shared branches | [commits](commits.md#earlier-commits) |
| AGENT-01 | Agents use the same checks as developers, respect authorization limits, and their claims are verified against executed results | Agents contribute | [quality](quality.md#rules-for-changes-and-agents) |
| TOOL-01 | Adopted tools, skills, and MCP servers answer a concrete need, are pinned, and have reviewed permissions and an owner | Such tools are configured | [tooling](tooling.md#adopt-and-maintain) |
