# Shared state, processes, and resources

Read this when agents, processes, or lines share a repository, a host, or an account, or when you
resume coordination that left any of them behind. The rules on processes and on Git apply even to a
single agent.

## Contents

- Isolation
- Processes and waits
- A guard for waits and kills
- Shared resources
- Repositories another agent could configure
- The state record
- Close-out at merge
- Several lines in one repository

## Isolation

- One worker that writes per worktree or checkout. Put worktrees outside the checkout when the
  repository's checks walk its tree.
- Never use the stash. Branches, tags, and the stash are shared by all worktrees of a repository,
  so one agent's stash operation can take another agent's work. Use a temporary commit or a patch
  file.
- Create scratch directories with unique names, keep their paths in your own commands, and delete
  only what you created.
- The coordinator alone assigns shared contracts, lockfiles, migrations, and identifiers such as
  debt IDs or ports, in the brief.
- The coordinator's uncommitted changes reach a worker only through a reviewed commit.

## Processes and waits

- Stop processes by exact PID, never by pattern. A pattern can match the shell that runs it, or
  another agent's process: `pkill -f <path>` once killed its own shell, and a `pgrep -f` wait
  matched itself and never ended.
- A PID in a handoff or a hand-back is a claim, and PIDs get reused. Before stopping one, check that its command
  line and start time match what the handoff records. Stop it only when they match and the handoff
  says it belongs to the previous coordinator; otherwise leave it and tell the owner.
- Every wait has a deadline and watches the signal that ends it. A waiter that counted workflow
  runs never finished, because the required checks were two check runs of one workflow run.
- Never end a session while a background run you started is alive: its evidence is lost.
- When an agent reports that it is waiting on background work, inspect its processes and its last
  report in the same turn.

## A guard for waits and kills

If rules on waits and kills keep being broken, propose a guard to the owner; installing a hook is a
change to settings that the owner makes. Where the agent tool runs a hook before each command, the
guard's contract is:

- It refuses waits without a deadline, polling without a timeout, and matching or killing processes
  by pattern. Its refusal names the allowed form.
- It matches at command position only, so quoted text does not trip it.
- Its threat is an agent that forgets, not one that evades: it is a convenience, not a security
  boundary. So by default it fails open and logs, unless the owner chooses otherwise.
- Its tests cover the failure modes: the guard's script missing, unreadable input, and a crash.

## Shared resources

- One scheduler per shared resource: a login, ports, a browser pool, host load, a provider's rate
  limit. Parallel runs that each found an expired login raced to refresh it, and all failed.
- Take the resource's lock with a bounded wait and queue behind it, instead of watching for it to
  free and starting by hand. Work on different resources may overlap; record that it did. If the
  resource has no lock, start the next use after the current one ends, and record the order in the
  state record.
- Warm up a shared login once, in series, before parallel runs.
- Bound concurrency by the host's capacity: start heavy runs, such as full test suites, only while
  the host's load is below its number of cores, a starting value the profile may change.

## Repositories another agent could configure

Git commands read a repository's configuration and can run code from it: `core.fsmonitor`, clean
and smudge filters, and hooks. `.git/commondir` and `objects/info/alternates` redirect reads to
another repository, and a promisor remote makes plumbing commands fetch through `core.sshCommand`.
A worker that commits in a worktree can change the configuration that every worktree of the
repository shares. Before running Git there:

- Read the configuration with `git config --list --show-origin` and look for `core.fsmonitor`,
  `core.hooksPath`, `core.sshCommand`, filters, and `uploadpack` settings you did not set.
- Read with `GIT_ALLOW_PROTOCOL=none` and `-c core.fsmonitor=false`, and prefer plumbing such as
  `git rev-parse`, `git cat-file`, and `git diff-tree` to `git status` and `git diff`, which run
  filters.
- Refuse a Git directory whose `commondir` or `objects/info/alternates` leads anywhere but the
  repository's own Git directory.

Launch agents in a repository you do not own with only the settings you control: its own agent
settings and hooks run code. An allow-list of commands keeps credentials and outside files out of
reach only until the agent runs code, such as a test runner; only an OS sandbox closes that gap. An
exported credential reaches every child process.

## The state record

Keep it outside the worktrees and the temporary directory, with the handoffs:

```markdown
| Front | Status | Acts next | Records |
| --- | --- | --- | --- |
| <name> | <status> | <who acts next> | <brief, hand-back, worktree, branch> |
```

- Status is one of `planned`, `running`, `waiting` (on background work), `ready_for_review`,
  `fixing`, `blocked`, `failed`, `merged`, and `closed`.
- Act on a ready report; do not leave it waiting.
- Generate the checkable part, such as branches, worktrees, processes, and open reviews, with a
  command rather than from memory.
- Keep records outside the repository and the temporary directory before removing anything: a
  restart once wiped a temporary directory with every script and log in it.

## Close-out at merge

Once the front's commits are on main and its records are archived, list what you will remove, then
remove the front's worktree and the branches it created, with the forms that refuse unmerged or
dirty work. Delete nothing another front or line created.

## Several lines in one repository

- Each line owns its files. A file that two lines change needs both lines' agreement first.
- A line announces a change to any interface another line imports before making it.
- Runs that share a provider queue on that provider's lock.
