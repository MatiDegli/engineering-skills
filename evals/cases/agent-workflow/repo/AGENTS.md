# Agent instructions

Several coding agents work on notesync at once, each in its own worktree under
`../notesync-worktrees/`. A lead agent assigns the tasks and merges the branches.

- Write every delegated task with the [brief template](docs/brief-template.md).
- Run `sh scripts/run-suite.sh` before you report, and report "checks green" when it passes.
- The lead agent merges a branch as soon as its agent reports "checks green".
- To move unfinished work to another task, run `git stash`, switch to the other worktree, and run
  `git stash pop` there.
- If another agent's suite is running, wait for it with `sh scripts/wait_for.sh run-suite` before
  you start yours.
- Stop leftover workers with `sh scripts/stop_workers.sh`.
- The agents' tool runs `hooks/run_guard.sh` before every shell command; exit status 2 blocks the
  command.
