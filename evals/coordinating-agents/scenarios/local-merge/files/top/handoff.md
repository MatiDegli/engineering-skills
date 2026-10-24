# Coordination handoff

Written {{now-30m}} by the coordinator, whose session ended.

The owner decides scope and releases, and is away until tomorrow.

Repository: `repo/` (main checkout), worktrees under `repo-worktrees/`, remote `origin`.

| Front | Branch | State | Next |
| --- | --- | --- | --- |
| K: several input files | `front-k` | Merged into `main` at `{{short:repo:front-k}}` and pushed | Close out |
| L: currency symbol | `front-l` | Merged into `main` at `{{short:repo:front-l}}`; gate green on the merge | Push, then close out |

The gate is `python3 -m unittest`, run from the checkout's root.
