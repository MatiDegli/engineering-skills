# Minimum standard

Adopt these guidelines in each project according to its use and risk. A documented
recommendation becomes a control when it has configuration, execution, and evidence that
it rejects failures.

## Repository

- README: purpose, requirements, and actual installation, run, and validation commands.
- A short AGENTS.md if agents work on the project; record decisions only when there are alternatives and consequences.
- One location for each rule or state; link to it instead of duplicating it.
- Commit code, configuration, tests, and lockfiles. Exclude environments, secrets, logs, and builds.
  Add `.env.example` only when configuration exists, using fictional values.
- Comments explain intent and invariants that are hard to infer; keep documentation proportionate.
- Apply [organization and cleanup](structure.md) and the [commit policy](commits.md).

## Quality

- Reproducible installation and one validation command shared by development and CI.
- Formatting, linting, types, tests, and builds where appropriate to the stack.
- Test public behavior, failures, and limits; separate costly integrations.
- Justified dependencies, supported versions, lockfiles, and periodic review.
- Results state the tested revision, command, and limitations; a skipped check is not a pass.

[Quality](quality.md) details limits and exceptions; [validation](validation.md) explains what to test;
[CI](ci.md) explains how to require controls before integration.

## Proportionate security

| Level | Use | Controls before operation |
| --- | --- | --- |
| 0 | Disposable local experiment | Fictional data, no secrets, and one minimal test |
| 1 | Internal tool | Trust boundaries, validated inputs, least privilege, and logs without sensitive data |
| 2 | Public or distributed product | Above; authorization where applicable, resource limits, secret/dependency review, recovery, and support |
| 3 | Sensitive data or high impact | Above; threat model, independent review, traceability, and rehearsed recovery |

Review the level when data, users, or permissions change. At every applicable level:

- Validate inputs and authorization per resource; verify the authenticity of external events.
- Limit time, attempts, and size; define idempotency and conflict handling for retryable writes.
- Keep debugging and administration disabled by default in public environments.
- Keep credentials out of Git, examples, logs, and packages. Rotate exposed credentials: deleting them
  from the latest commit does not remove historical exposure.
- Before distribution, review secrets in content, history, and the artifact, as well as resolved
  dependencies. See [dependency maintenance](quality.md#dependency-maintenance).
- Before publication, define the license, support, and a real reporting channel in SECURITY.md.

## Delivery and operations

1. Identify the validated revision and build with locked dependencies.
2. Review the files allowed in the artifact; install it outside the development tree.
3. Verify the artifact contains no secrets, private fixtures, caches, or local configuration.
4. For services: document configuration, health, logs, migrations, and rollback.
5. For persistent data: test backup and restoration, and agree on acceptable data loss and downtime.
6. Publish with project authorization, an identifiable version, and recorded changes.

Criteria for growth and capacity measurement are in [architecture and performance](architecture.md).
