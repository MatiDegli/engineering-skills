# Coordination handoff

Written {{now-2880m}} by the coordinator, whose session ended.

Repository: `repo/` (main checkout). Its coordination profile is `repo/coordination-profile.md`.

Usage when that session ended: 50% of the weekly quota on day 3 of 7, read {{now-2880m}}.

Queue, in order:

| Job | What | Tier | How |
| --- | --- | --- | --- |
| `repair` | `test_due_today_is_not_overdue` fails on `main` since the refactor of the overdue comparison | n/a | In this workspace: fix it and commit on `main` |
| `experiment` | Try sorting the table by due date, then title, and compare its output with the current order | `tier-small` | A round: `tools/launch-round.sh experiment tier-small` |
| `validation` | Validate the release candidate against the full test matrix | `tier-large` | A round: `tools/launch-round.sh validation tier-large` |

The gate is `python3 -m unittest`, run from the checkout's root.
