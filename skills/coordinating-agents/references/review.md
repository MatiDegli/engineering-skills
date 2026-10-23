# Review and verification

## Contents

- Review the plan
- Independent review, with a request template
- Verify claims
- Fix rounds
- Destructive tooling
- Integration

## Review the plan

Tooling that deletes, rewrites, or guards anything, and designs that change authority or lifecycle,
start with a one-page plan:

- the states and transitions;
- the failure modes, for each window in which a fault can strike;
- the files to change and the ceilings they already sit at;
- the tests, and the fault each one injects.

The implementer stops until an independent reviewer passes the plan. A design defect is cheapest to
reject before code exists.

## Independent review

- The reviewer is the one the profile names, and never the author: no agent accepts its own work.
- Changes to security, authority, lifecycle, or gates are not merged until an independent reviewer
  has reproduced its findings and checked the final revision.
- Give the reviewer a clean context: the brief, the plan, and the diff, not the implementer's
  reasoning. Scope the review to correctness and the stated requirements.
- A clean result still lists what was checked and what could not be verified.

```text
Review <base>..<head> against <brief path> and <plan path>.
Scope: correctness and the stated requirements.
Return findings classed BLOCKING (must change before merge), SHOULD-FIX, or NIT, each with file
and line, the scenario that breaks, and a fix. Keep each probe or test that reproduces a finding,
so the implementer can rerun it. List what you checked and what you could not verify.
```

## Verify claims

- A report is a claim. Before you accept or repeat a decisive claim, such as "tests pass",
  "removed", "no size growth", or "fixed", re-derive it from the diff, a rerun, or a cheap
  experiment. A claim repeated by several agents is still one claim.
- Write numbers, times, and states from logs, run records, or code, never from memory. Reports that
  a script generates keep fixed sentences that go stale, so reread them.
- Test a check that handles secrets with a fake value, never the real one.
- A new attempt at a failing problem needs a changed hypothesis and a smaller experiment that can
  tell the causes apart. Rerunning the whole pipeline only repeats the evidence.

## Fix rounds

- A defect you find in a worker's front goes back to that front as a fix round, however small the
  fix. Never commit on a worker's branch: you review the front, and no agent accepts its own work.
  If you cannot dispatch a fix round, record the finding and the fix you would brief in the state
  record, and hand them to the owner.
- When a finding leaves a decision the owner holds, such as a change of output or scope, list the
  options with their evidence, and neither build nor brief any of them.
- Send each fix round to a fresh agent with the findings and a handoff, unless the profile says
  otherwise. A re-review may reuse a reviewer whose context is still small.
- The fix report answers every finding: fixed, with the commit, or disputed, with evidence. Each
  fix states the search it ran for sibling paths with the same problem, and for each new guard a
  mutation that makes a test fail without it. In a sample of 21 fix rounds from measured projects,
  42% of the findings were sibling paths the fix left open, and 27% were defects it added.
- Re-derive each finding against the new revision, not from the fix report.
- A correction cycle is one fix round and its re-review. Default to one, a starting value from one
  set of projects; another needs a material concern, stated in the state record.
  If a BLOCKING finding is still open after the last cycle, stop and put it to the owner with both
  reports.
- Count rounds per accepted change, not only their price: a self-review checklist made each round
  cheaper but did not reduce rounds per accepted change overall.

## Destructive tooling

Tooling that deletes, rewrites, or guards anything gets an adversarial review with real probes, in
throwaway repositories, before it runs for real. It re-checks state right before it acts, keeps
whatever it cannot prove is preserved, stays read-only unless told to apply, and archives before it
deletes.

## Integration

- Each commit passes the checks on its own tree when it is made.
- A gate piped into another command does not gate: run it unpiped, or with `pipefail`, and stop on
  its exit code.
- After resolving conflicts, look for deleted lines that came back.
- Scan for secrets before every push.
- Combining reviewed fronts in an integration worktree, including resolving their conflicts, is
  technical work any agent may do. A fix for a front's defect is not: it is that front's fix round,
  on no branch of yours. Merging, pushing, and publishing belong only to whoever holds
  that authority in the repository. The profile, the repository's rules, or the owner grant it;
  what an earlier session did grants nothing. Deleting a branch on a remote is a push.
