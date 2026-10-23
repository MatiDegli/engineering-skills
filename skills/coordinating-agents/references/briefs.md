# Briefs, hand-backs, and handoffs

## Contents

- The brief, with the hand-back format inside it
- Matching the worker to the task
- Resume or start fresh
- The handoff

## The brief

Write one brief per task. Before sending it, check every premise it states against the current main
and cite commit hashes: a stale brief made an implementer skip required work. Keep it to a few
hundred words, and link to longer material instead of pasting it. Keep the brief where the task is
tracked, such as its issue or pull request; a finished task's brief need not stay in the repository.

````markdown
# Brief: <task>

Base: <commit>. If this brief and an older note disagree, <document> wins.
Goal: <one paragraph>. Not in scope: <...>.
Done when: <an observable result>.
Binding decisions: <each decision, with where it is recorded>.

Paths you may change: <...>.
Excluded unless listed above: credentials and secrets, dependency manifests and lockfiles,
generated output, CI workflows, gate and hook configuration, agent configuration, unrelated
migrations, and version-control internals.
Ceilings: <size limits the touched files already sit at, such as file length or commit size>.
Reserved for this task: <identifiers, ports, migration numbers>.

Verify with: <commands>, on each commit.
Budget: <turns> turns and <minutes> minutes. At about half, write an interim report. Keep about
15% for verification and the report. If a requirement is missing or contradicts another, stop and
report; do not invent one.
Waiting: every wait has a deadline; stop only processes you started, by PID; never end while a
background run you started is alive.
Shared state: never use the stash; create scratch directories with unique names, and delete only
what you created.
Report to <path>, in this format, in about 2,500 characters at most, with longer detail in a file.
Never mark your own work accepted.

```text
STATUS: ready_for_review | blocked | failed
Changed: <files or commits>
Verified: <command> -> <result>, one line each
Not verified: <what, and why>
Open: <questions, risks, follow-ups>
Still running: <none | PIDs you could not stop, each with command line and start time>
Context at the end: <size, if your tool reports it>
Details: <path>
```
````

Drop the fields a task does not need: a read-only survey has no paths to change or ceilings. Work
that changes code without tests asks for characterization tests of the current behavior first.

Size the budget from a comparable task you measured. Without one, state the figure and the reason
in the brief. The interim report at half and the 15% reserve are starting values from one set of
projects; adjust them to what you measure. Set any hard cap of the agent tool above the brief's
budget, so the interim report and the reserve come first: a cap that stops an agent cannot ask it
for a report.

The coordinator rereads every line a worker returns on each later turn, which is why the hand-back
stays short.

## Matching the worker to the task

- Route by the task: its difficulty, role, and risk, with the profile's tiers, or with the default
  tiers in profile.md when there is no profile.
- Pass the model and effort explicitly: a delegated agent may otherwise inherit the coordinator's.
- A configuration is not evidence of routing, and neither is a worker's word: read the model that
  ran from the run's own record.
- A worker's tools exclude delegation unless its task is to coordinate.

## Resume or start fresh

Resume an agent only while its cache is warm and its context is small. A cache is cold once the
agent has been idle longer than its cache lifetime: the provider's default, or the longer one paid
for that agent. Small means under the
profile's context cap; without one, start from about 150k tokens, the cap one measured project
uses, and adjust. Otherwise start a fresh agent with a handoff.

## The handoff

```markdown
# Handoff: <front>, <date from the clock>

Decisions and reasons: <...>
Files touched: <paths, commits, branches, worktrees>
Failing checks: <command and output, or none>
Running: <processes, with PID, command line, and start time, and how to stop them, or none>
Next step: <one action, and who takes it>
```
