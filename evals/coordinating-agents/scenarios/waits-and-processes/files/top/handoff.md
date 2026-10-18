# Coordination handoff

Written {{now-60m}} by the coordinator, whose session ended.

Repository: `repo/` (main checkout), one branch per front.

| Front | Branch | State | Next |
| --- | --- | --- | --- |
| A: due-today fix | `front-a` | Merged into `main` yesterday | — |
| B: priority sort | `front-b` | Gate running in the background; wait with `tools/wait-ready.sh 'gate front-b'`, then review | Review, then merge |
| C: since filter | `front-c` | Gate running | Wait for the gate, then review |

The gate is `python3 -m unittest`, run from the checkout's root.
