# CI and control protection

This guide applies to the CI of the project under review.

## Minimal pipeline

- Install with pinned runtime and dependencies; run the same commands as locally.
- Pin Actions by SHA, limit permissions per job, and avoid persistent credentials in checkout.
- Set timeouts; cancel obsolete PR runs without canceling deliveries in progress.
- Validate workflows and scripts with appropriate tools; test a violation and its exit code.
- Keep bounded diagnostics with defined retention and no secrets.

A small project can use a single job. Separate checks when their costs, services, platforms, or
permissions differ:

| Group | Typical work |
| --- | --- |
| Fast | Format, lint, types, size, and architectural boundaries |
| Contracts | Deterministic regeneration and consumer checks |
| Tests | Unit, integration, failure, and recovery tests |
| Security | Dependencies, secrets, and static analysis |
| Delivery | Artifact build and installation; native validation where appropriate |

Measure duration, queue time, cold/warm cache, and instability before adding runners or partitions.
Reuse commands and installations; caches speed up work without replacing evidence. Test services need
reviewed versions, synthetic data, health checks, timeouts, and cleanup of owned resources. If a
required service or [run configuration](validation.md#environment-and-scope) is missing, the job
must fail before the suite starts.

## Require real results

1. Configure PRs and relevant checks in branch protection, with correct names and emitting
   application; review administrator permissions and bypasses.
2. Test the combined candidate with its base. If using a merge queue, configure `merge_group`
   for required workflows.
3. Validate the author’s commits against the actual PR head; the synthetic integration commit serves
   a different purpose. Apply the [commit policy](commits.md) to the retained history.
4. Test a rejected case and its correction in the provider. Valid YAML does not prove hosted protection
   is active.

Required checks must report a result for all relevant changes. Review path filters and conditional jobs: an
omitted job can appear successful without running tests. Test selectors; with an unknown base/diff,
broaden scope or fail explicitly. An aggregator must reject failed, canceled, or missing results;
`always()` is not enough.

## Protect policy when risk warrants it

Inventory protected configuration, scripts, workflows, scopes, and ignores. Review the diff with a guard
run from a trusted base; the proposed version cannot approve itself.

- Require an existing, reviewed base; never silently replace it with the PR checker.
- Bind the justification to the candidate, base, and all affected paths. Deleting the record, copying an
  old one, or changing whitespace does not prove a new review.
- Test removed controls, reduced scope, suppressions, stale justifications, and omitted new files. Written
  justification does not replace independent approval.
- Use real owners and protect the workflow too. Administrators can change provider rules: protection
  depends on that configuration and its permissions.

## Privileges and delivery

Separate PR validation and publication. Avoid secrets or privileged persistent runners for external code;
do not run it through `pull_request_target`. Publish with appropriate authorization and permissions,
identifying the tested artifact, hashes, and provenance. Review pins and digests in scripts in addition
to automated dependency updates.

Sources, checked on 2026-10-16 against the claims they support: [required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks),
[Actions security](https://docs.github.com/en/actions/reference/security/secure-use).
