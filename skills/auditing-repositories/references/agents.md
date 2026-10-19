# Agent-assisted development

Apply this guide when coding agents contribute to the repository. It extends the
[rules for changes and agents](quality.md#rules-for-changes-and-agents), which apply to every
contributor. Prefer mechanisms to written rules: a template, a hook, or a gate that rejects a mistake
works even when an agent forgets an instruction.

## Briefs

Give each delegated task one brief that bounds it:

- The base revision, the binding decisions and corrections, and which document wins when a plan and
  a later correction disagree.
- The allowed paths and the shared identifiers reserved for the task, such as migration numbers,
  debt IDs, or ports, assigned by whoever coordinates the work.
- The verification to run, the report format, and the evidence each claim needs.
- Rules for waiting: every wait has a deadline, and a report says whether background work is still
  running.

The brief bounds the task while it runs, so keep it where the task is tracked, such as its issue or
pull request. A finished task's brief need not stay in the repository.

Keep one bounded task per brief and match the agent to it: work that spans several commits, touches
security, or changes a user interface needs a stronger implementer and review. Nobody approves their
own work, as [independent review](standard.md#repository) requires.

## Review and verification

- Review the plan before implementation. A design defect is cheapest to fix before code exists.
- Classify review findings by severity, with file and line evidence. The next round resolves each one
  or argues against it with evidence.
- Changes to security, authority, lifecycle, or gates get an independent review before merge. A
  reviewer who reproduces a finding with a probe or a deterministic test, kept so the implementer can
  rerun it, finds defects that passing tests miss.
- Verify fixes, not reports. Re-derive each finding against the new revision and check decisive claims,
  such as "removed" or "no size growth", against the diff. Each commit passes the checks on its own.
- Tooling that deletes or rewrites anything gets an adversarial review with real probes in throwaway
  repositories before it runs for real. It re-checks state right before acting and keeps whatever it
  cannot prove is preserved.

## Isolation

Concurrent agents need isolated state:

- One writer per worktree or checkout.
- No shared Git state. Every ref under `refs/`, the stash included, is shared by all worktrees of a
  repository, so one agent's stash operation can take another agent's work; use a temporary commit or
  a patch file instead.
- Scratch space, ports, and locks partitioned per task or assigned by one scheduler. An agent deletes
  only what it created.
- Work closed out at merge: archive the task's records, then remove its worktree and branches. Left to
  memory, leftovers accumulate.

Processes and waits started by agents follow
[contracts, effects, and resources](architecture.md#contracts-effects-and-resources).

## Capacity and state

Bound concurrency by the host, not by the number of available agents. Limit heavy runs, such as full
test suites, to what the machine sustains, start them below a load threshold, and send every consumer
of a shared resource, such as ports or browsers, through the same slots. Keep a state record with each
task's status and next owner, so that a finished task is not mistaken for one still waiting on
background work. This applies when several agents work at once; one agent at a time needs none of it.

Sources checked on 2026-10-17 against the claims they support:
[shared and per-worktree refs](https://git-scm.com/docs/git-worktree#_refs).
