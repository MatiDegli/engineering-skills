# Validation and evidence

Choose checks according to impact and record what they demonstrate. Meet the mandatory [CI](ci.md)
controls on the candidate to be integrated.

## Environment and scope

Before running checks, verify the checkout, revision, local changes, runtime, lockfile, and run
configuration (the services, environment variables, and test selection the run requires). In
Python, check that the editable installation belongs to the expected checkout. Each checkout/platform
needs its own mutable environment; sharing compatible caches does not mean sharing `.venv` or
installations. Prepare services within the authorized scope.

Resolve internal resources from the project and parameterize external data. Avoid personal paths or sibling
repositories; test spaces, Unicode, and another cwd when supported.

| Change | Relevant check |
| --- | --- |
| Behavior | Observable result and a relevant failure/limit |
| API, schema, or client | Generation without unexpected differences, compatibility, and consumers |
| Persistence, concurrency, or processes | Real resources, partial failures, cancellation, and recovery |
| UI | Real user flow, recovery, visual review, and accessibility |
| Runtime, lockfile, or packaging | Clean installation and artifact on affected platforms |
| Scripts, policy, or workflows | Real tool with valid and invalid cases, scope, and exit code |
| Documentation | Navigation, applicable commands, and accuracy of claims |
| Uncertain impact | Expand the affected set and record the uncertainty |

## Useful tests

- Name the invariant and failure before choosing fixtures; test public interfaces.
- Keep unit tests deterministic: synthetic data, temporary resources, a controlled clock, no network
  or arbitrary waits. Separate integrations and block network access in the pure suite if needed.
- For state changes, test duplicates, retries, and failures between acceptance, execution, and
  persistence. For an ambiguous effect, reconcile before repeating it.
- For processes, represent real wrappers, children, and groups/jobs. Check cleanup of descendants and
  owned resources even on timeout; parent exit does not prove this.
- Distinguish mocks from real providers and a browser from a native desktop app. State omissions.
- Test each control’s boundary, including rounding and severities that could let a failure pass.

## Recording and reusing results

Keep in the PR or existing record: revision and relevant local changes, command, environment, run
configuration, inputs, result/exit code, and accessible evidence. Include new files; an identical
HEAD does not identify the state of a changed working tree. Record duration when relevant to cost
or performance.

Distinguish passed, failed, skipped, not applicable, timed out, and interrupted. Explain pending scope
and how to complete it. Reuse results only when inputs, environment, and scope match; repeat after
relevant changes, failures, or missing evidence. Audits also depend on the dates of their sources. Avoid
unnecessary repetition.

If a tool records this evidence automatically, capture the revision and working-tree state when the
run starts and confirm they are unchanged when it ends. Changes during execution invalidate the result;
comparing only the start and end states does not detect a change that was later reverted.
Limit logs, access, and retention.

## Coordinate and recover work

Define the outcome, scope, and validation; assign an owner and isolate simultaneous changes. Deliver the
commit/diff, evidence, and next action; review and integrate, then verify the result. A blocker needs a
cause and resolution condition. Status belongs in the implementation repository.

When handing off work, preserve commits, staged/unstaged changes, relevant new files, and evidence. If
reconstructing, use an inventory with hashes and a new destination; verify recovery before removing the
source. Exclude secrets, environments, and caches; commands recorded in the evidence do not
authorize running them.

Automate the assignment of work to agents or jobs only after completing a manual cycle. The automation
needs a single process that assigns work, with an accountable owner; explicitly authorized tasks;
time/cost/retry limits; duplicate prevention; and a stop condition. Communicate relevant changes or the
need for intervention; a list of pending tasks does not authorize running them.
