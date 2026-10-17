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
- Record each incident's lesson where maintainers will find it: the cause, and the mechanism that now
  prevents it, or a named follow-up until one exists. A rule that depends on someone remembering it
  is not a mechanism.
- Give each area an owner. Someone other than the author, human or agent, approves each change, and
  always changes to security, releases, and policy. Code-owner rules can request and require those
  reviews.

## Quality

- Reproducible installation and one validation command shared by development and CI.
- Formatting, linting, types, tests, and builds where appropriate to the stack.
- Test public behavior, failures, and limits; separate costly integrations.
- Justified dependencies, supported versions, lockfiles, and periodic review.
- Pin the runtime at least to a minor version, such as 3.12, which keeps compatible patch releases
  flowing; pin the patch version too only when the project depends on one.
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

A product is distributed once people outside the team that maintains it receive it; an installer
or package that only its maintainers use does not raise the level. Review the level when data,
users, or permissions change. At every applicable level:

- Validate inputs and authorization per resource; verify the authenticity of external events.
- Limit time, attempts, and size; define idempotency and conflict handling for retryable writes.
- Keep debugging and administration disabled by default in public environments.
- Keep credentials out of Git, examples, logs, and packages. Rotate exposed credentials: deleting them
  from the latest commit does not remove historical exposure.
- Treat error text as data. Database and library errors can carry bound parameters, request bodies,
  or secrets, so code at trust boundaries logs the error class and a correlation identifier rather
  than the message, and drivers are configured to hide parameters. Passwords, tokens, connection
  strings, keys, and sensitive personal data stay out of logs.
- Write secrets in tests and examples as low-entropy, obviously fake sentinels, such as
  `fake-api-token`. Scanners flag values by pattern and entropy, so realistic fakes force allowlists
  that can also hide real leaks.
- For personal data, inventory what is collected and why, keep only what that purpose needs, protect
  it in storage, logs, and backups, and define how long it is kept and how it is deleted.
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
7. For distributed artifacts: publish build provenance that identifies the source revision and the
   build, and a software bill of materials, in formats consumers can verify.
8. For services in operation: set service level objectives on user-visible indicators, alert on
   symptoms that consume the error budget rather than on every cause, keep every page actionable,
   and give each alert a runbook with its impact and first steps.
9. For services with users: roll out changes progressively, for example to a canary compared with
   the current version, stop or roll back automatically on user-visible regressions, and rehearse
   the rollback.

Criteria for growth and capacity measurement are in [architecture and performance](architecture.md).

Sources checked on 2026-10-17 against the claims they support:
[code owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners),
[data to exclude from logs](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html),
[entropy in secret scanning](https://github.com/gitleaks/gitleaks),
[data minimisation](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/data-minimisation/),
[provenance levels](https://slsa.dev/spec/v1.0/requirements),
[software bill of materials](https://www.cisa.gov/sbom),
[symptoms and actionable pages](https://sre.google/sre-book/monitoring-distributed-systems/),
[alerting on objectives](https://sre.google/workbook/alerting-on-slos/),
[playbooks](https://sre.google/workbook/on-call/),
[canarying](https://sre.google/workbook/canarying-releases/).
