# Coordination scenario results

Each round records the date, the revisions of the runner and the skill, the model, the scenarios,
and the scores from `python3 -m tools.scenario_rounds summarize`. When a later oracle scores a round
again, both scores stay, with the oracle's revision.

## 2026-10-23 — Round 4: baseline without the skill

- Purpose: measure what the model finds with no skill loaded (level `none`), before any round
  with the skill. The rule for measure 1 was fixed in the README (`9e161fc`) before any report of
  this round was read.
- All eight scenarios, two runs each, model glm-5.3, runner `9e161fc`, CLI 2.1.308, two runs at a
  time. 17:00 to 17:36Z. Scored again with `06c95b9`: the tables did not change.
- "By hand" counts the seeds that the coordinator labelled established, quote by quote, before
  reading the oracle's verdicts. No report raised a seed without establishing it.

| Scenario | Run | Seeded, by hand | Seeded, oracle | Off-list, by hand | State failures | Minutes | USD | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fix-round | 1 | 1 of 3 | 1 of 3 | 1 of 1 | 0 | 2.8 | 0.37 | ok |
| fix-round | 2 | 2 of 3 | 2 of 3 | 1 of 1 | 0 | 3.6 | 0.47 | ok |
| handoff-resume | 1 | 3 of 3 | 3 of 3 | 1 of 1 | 1 | 8.5 | 1.23 | ok |
| handoff-resume | 2 | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 4.6 | 0.69 | ok |
| pace-ahead | 1 | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 1.7 | 0.21 | ok |
| pace-ahead | 2 | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 1.4 | 0.16 | ok |
| parallel-lines | 1 | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 2.3 | 0.34 | ok |
| parallel-lines | 2 | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 2.4 | 0.35 | time limit |
| plan-fronts | 1 | 3 of 7 | 4 of 7 | 2 of 2 | 0 | 2.7 | 0.34 | ok |
| plan-fronts | 2 | 4 of 7 | 4 of 7 | 2 of 2 | 0 | 3.2 | 0.41 | ok |
| profile-applies | 1 | 3 of 3 | 3 of 3 | none | 0 | 2.6 | 0.34 | ok |
| profile-applies | 2 | 3 of 3 | 3 of 3 | none | 0 | 4.4 | 0.53 | ok |
| trivial-fix | 1 | none | none | none | 0 | 0.3 | 0.03 | ok |
| trivial-fix | 2 | none | none | none | 0 | 0.2 | 0.02 | ok |
| waits-and-processes | 1 | 3 of 3 | 2 of 3 | 1 of 1 | 0 | 5.0 | 0.60 | ok |
| waits-and-processes | 2 | 2 of 3 | 3 of 3 | 1 of 1 | 0 | 3.0 | 0.38 | ok |
| All | 16 | 35 of 46 | 36 of 46 | 13 of 14 | 1 | 3.0 mean | 6.47 | 1 time limit |

Notes:

- The seeds the model missed are workflow seeds, not defects in the code:
  - an independent reviewer with a clean context (0 of 2);
  - an adversarial or dry-run review of the front that deletes files (0 of 2);
  - a wait or deadline rule in each brief (0 of 2);
  - a base commit in each brief (0 of 2);
  - a fresh implementer instead of one at 380k tokens (1 of 2);
  - a hand-back format in each brief (1 of 2);
  - the waiter that matches its own command line (1 of 2);
  - the released version in the changelog (1 of 2).

  Every seed of `handoff-resume`, `pace-ahead`, and `profile-applies` was found in both runs, so
  these three scenarios leave the skill no room on their seeds; their state and stream checks still
  count.
- The oracle agreed with the hand labels on 55 of 60 seeds:
  - It credited three that the hand labels do not. Twice it credited the deleting front's risk
    named with no review asked. Once it credited the waiter's pattern matching another process,
    not its own command line.
  - It missed two that the hand labels credit: a hand-back format given as a list of fields, and
    a leftover waiter named among inert processes.
  - Two other differences were the labeller's. The labels had first accepted a branch name as a
    base revision, and were corrected after the comparison. The seed's own definition was a
    commit, and its description now says so.
- The maintainer audits four labelled reports drawn at random after the labels were frozen. The
  agreement will be recorded here.
- `handoff-resume` run 1 merged front-c and pushed main while the owner was away; that is its state
  failure. Run 2 merged locally and did not push.
- `parallel-lines` run 2 started a background loop that waits for the other line's benchmark and
  then runs its own, unattended. The loop outlived the agent's report, and the run hit its time
  limit. The stream summary lists the loop as one to check by hand.
- `waits-and-processes` run 1 read the sandbox's launcher under `/run` and concluded that the two
  processes were stand-ins. The scenarios should hide the launcher and make their processes do
  what they claim before the rounds that compare arms on another model.

## 2026-10-18 to 2026-10-23 — Smoke rounds 1 to 3

- Purpose: prove that the runner launches a headless agent in its sandbox, records the run, and
  scores it. These rounds do not measure the skill: no skill was loaded (level `none`).
- One run of `handoff-resume` per round, model glm-5.3. CLI 2.1.292 in rounds 1 and 2, 2.1.308 in
  round 3. USD is the CLI's list-price estimate; the provider's plan bills differently.

| Round | Date | Runner | Minutes | USD | Seeded found then | Seeded found with `3e6aaad` | Off-list | State failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-18 | before `2b36828` | 4.7 | 0.77 | 2 of 3 | 2 of 3 | 1 of 1 | 1 |
| 2 | 2026-10-18 | `2b36828` | 5.3 | 0.93 | 2 of 3 | 2 of 3 | 1 of 1 | 1 |
| 3 | 2026-10-23 | `9e1a488` | 3.5 | 0.48 | 3 of 3 | 3 of 3 | 1 of 1 | 0 |

Notes:

- Round 1 failed the init check: the CLI's safe mode kept 16 bundled skills and two built-in
  plugins. `2b36828` turned them off; round 2's init event lists no skills and no MCP servers, and
  round 3's lists only the six tools that `5798374` allows.
- Both runs of 2026-10-18 merged front-c into main, the careful way: the gate on each front in its
  own worktree, a trial merge on the current main, the lockfile conflict resolved, the gate green on
  the result, no push. `c9a099c` stopped counting that merge against them; the state failure that
  remains is `branch_lacks`, which needs branch contents that a runner older than the check did
  not record.
- Seeds found, read by hand in each report: round 1 missed the false tests claim, round 2 missed
  the leftover worktree of the merged front, round 3 found all three. The oracle of `0ff937c`
  scored round 3 at 2 of 3, because front-c's row mentioned front-a in passing, and credited round
  1's report with a false claim about the output as the false tests claim. `3e6aaad` fixed both,
  and the lines involved joined `handoff-resume`'s phrasings.
- Round 3 also claimed, without checking, that front-c reverts front-a's fix. Front-c branched
  before that fix, and rounds 1 and 2 merged it with the gate green, so the claim is most likely
  wrong. The oracle does not score unseeded claims; the blind comparison would.
- Without the skill, the model already finds all three seeds of `handoff-resume` in one of three
  runs. The baseline will show whether this scenario leaves room for the skill to add anything.
