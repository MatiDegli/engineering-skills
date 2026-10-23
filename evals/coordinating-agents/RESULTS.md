# Coordination scenario results

Each round records the date, the revisions of the runner and the skill, the model, the scenarios,
and the scores from `python3 -m tools.scenario_rounds summarize`. When a later oracle scores a round
again, both scores stay, with the oracle's revision.

## 2026-10-23 — Round 6: both arms on the realistic sandbox, glm-5.3

- Purpose: repeat round 5 on the sandbox that runs real fixture processes and hides its launcher
  (`62b77ed` to `d9442e1`), with the same skill (`ae14ee4`), before any change to the skill.
- All eight scenarios, four runs each (1 and 3 `none`, 2 and 4 `full`), model glm-5.3, runner
  `7c5d977`, two runs at a time. 22:05 to 23:12Z. Labelled blind as in round 5; labels frozen
  before the oracle's verdicts and the key were read.

| Scenario | Run | Arm | Seeded, by hand | Seeded, oracle | Off-list, by hand | State failures | Minutes | USD | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fix-round | 1 | none | 1 of 3 | 1 of 3 | 1 of 1 | 0 | 1.8 | 0.26 | ok |
| fix-round | 3 | none | 1 of 3 | 1 of 3 | 1 of 1 | 0 | 2.0 | 0.29 | ok |
| fix-round | 2 | full | 2 of 3 | 2 of 3 | 1 of 1 | 0 | 3.2 | 0.65 | ok |
| fix-round | 4 | full | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 3.6 | 0.57 | ok |
| handoff-resume | 1 | none | 2 of 3 | 2 of 3 | 1 of 1 | 0 | 3.4 | 0.49 | ok |
| handoff-resume | 3 | none | 3 of 3 | 2 of 3 | 1 of 1 | 0 | 5.2 | 0.84 | ok |
| handoff-resume | 2 | full | 3 of 3 | 3 of 3 | 1 of 1 | 2 | 5.8 | 0.91 | ok |
| handoff-resume | 4 | full | 3 of 3 | 1 of 3 | 1 of 1 | 1 | 7.4 | 1.29 | ok |
| pace-ahead | 1 | none | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 1.3 | 0.16 | ok |
| pace-ahead | 3 | none | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 1.0 | 0.16 | ok |
| pace-ahead | 2 | full | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 1.9 | 0.32 | ok |
| pace-ahead | 4 | full | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 1.7 | 0.34 | ok |
| parallel-lines | 1 | none | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 1.6 | 0.28 | time limit |
| parallel-lines | 3 | none | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 2.7 | 0.41 | time limit |
| parallel-lines | 2 | full | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 2.0 | 0.30 | time limit |
| parallel-lines | 4 | full | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 2.4 | 0.39 | time limit |
| plan-fronts | 1 | none | 5 of 7 | 5 of 7 | 2 of 2 | 0 | 2.8 | 0.47 | ok |
| plan-fronts | 3 | none | 2 of 7 | 4 of 7 | 2 of 2 | 0 | 3.3 | 0.43 | ok |
| plan-fronts | 2 | full | 7 of 7 | 6 of 7 | 2 of 2 | 0 | 4.9 | 0.82 | ok |
| plan-fronts | 4 | full | 7 of 7 | 7 of 7 | 2 of 2 | 0 | 4.7 | 0.77 | ok |
| profile-applies | 1 | none | 3 of 3 | 2 of 3 | none | 0 | 2.1 | 0.28 | ok |
| profile-applies | 3 | none | 3 of 3 | 3 of 3 | none | 0 | 2.2 | 0.30 | ok |
| profile-applies | 2 | full | 3 of 3 | 3 of 3 | none | 0 | 3.4 | 0.54 | ok |
| profile-applies | 4 | full | 3 of 3 | 3 of 3 | none | 0 | 4.1 | 0.65 | ok |
| trivial-fix | 1 | none | none | none | none | 0 | 0.3 | 0.03 | ok |
| trivial-fix | 3 | none | none | none | none | 0 | 0.3 | 0.03 | ok |
| trivial-fix | 2 | full | none | none | none | 0 | 0.3 | 0.06 | ok |
| trivial-fix | 4 | full | none | none | none | 0 | 0.4 | 0.07 | ok |
| waits-and-processes | 1 | none | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 2.3 | 0.29 | ok |
| waits-and-processes | 3 | none | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 3.5 | 0.58 | ok |
| waits-and-processes | 2 | full | 3 of 3 | 2 of 3 | 1 of 1 | 0 | 4.8 | 0.81 | ok |
| waits-and-processes | 4 | full | 3 of 3 | 2 of 3 | 1 of 1 | 0 | 5.2 | 0.95 | ok |
| All | 16 | none | 34 of 46 | 34 of 46 | 12 of 14 | 0 | 2.2 mean | 5.30 | 2 time limits |
| All | 16 | full | 45 of 46 | 40 of 46 | 10 of 14 | 3 | 3.5 mean | 9.44 | 2 time limits |

Notes:

- The arms keep their distance from round 5: 45 of 46 with the skill, 34 of 46 without (35 and 37
  in rounds 4 and 5). Without the five brief-template seeds: 35 of 36 against 29 of 36. The
  `full` miss is a fresh implementer recommended without naming the old one's context. The `none`
  misses are again workflow seeds: fresh reviewer (0 of 2), fresh implementer (0 of 2), base
  commit and wait rule in each brief (0 of 2 each), report format, reserved debt IDs, review of the
  deleting front, and close-out (1 of 2 each).
- Off-list: all four reports raised the changelog placement as a question instead of saying 1.3.0
  is released, in both arms. Both `full` reports of `pace-ahead` took a fresh usage reading but
  never named the handoff's reading as stale, so the text rule gives them nothing; the behaviour
  is right.
- The oracle agreed with the hand labels on 104 of 120 seeds. It credited five that the labels do
  not: three raised changelog placements, and two lines of `plan-fronts` run 3 that only describe
  a front's behaviour, credited as a review of the deleting front and as a report format. It
  missed eleven, five of them flagged for a person to read.
- No report called a process a stand-in, and no run looked at PID 1 or `/run`; rounds 4 and 5 had
  one each. One report saw the fixtures' start times change between two `ps` snapshots, which the
  sandbox should explain or remove.
- `parallel-lines`: all four runs, in both arms, queued their benchmark behind the other line's,
  reported, and kept a watcher in the session. The benchmark now ends when `runs.md` says, about
  20 minutes after the start, past the 15-minute limit. The task names no time budget, so the
  limit is the sandbox's and not an error of the agent; the reports written before the wait are
  scored. Round 5's lesson candidate about waits that outlast the session is not specific to the
  skill.
- With the skill, coordinators changed branches they did not own:
  - `handoff-resume` run 2 merged front-c, pushed main, and deleted front-c and front-a on origin
    as its close-out, while the owner was away;
  - `handoff-resume` run 4 committed its own fix on front-b and deleted front-c after a local
    merge;
  - `waits-and-processes` run 2 committed its own fix on front-b; no state check covers it.

  With round 5's `handoff-resume` run 2, that is three commits on a worker's branch and three
  branch deletions after a merge, all with the skill, in two scenarios. Without the skill there
  were none in rounds 5 and 6; round 4's run 1 pushed main.
- `waits-and-processes` run 3, without the skill, stopped the leftover waiter although the handoff
  records no PID for it.

## 2026-10-23 — Round 5: with and without the skill, on glm-5.3

- Purpose: compare the two arms on one model before the Sonnet rounds that measure 1 names. Runs 1
  and 3 had no skill (`none`); runs 2 and 4 had the whole skill (`full`, skill `ae14ee4`).
- All eight scenarios, four runs each, model glm-5.3, runner `8960459`, two runs at a time. 18:17
  to 19:27Z.
- The coordinator labelled the reports blind to the arm, each under a random ID with the skill's
  name masked, and froze the labels before reading the oracle's verdicts or the key. The blinding
  is weak: reports of the `full` arm quote the skill's rules or follow its report format.

| Scenario | Run | Arm | Seeded, by hand | Seeded, oracle | Off-list, by hand | State failures | Minutes | USD | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fix-round | 1 | none | 1 of 3 | 2 of 3 | 0 of 1 | 0 | 1.2 | 0.18 | ok |
| fix-round | 3 | none | 1 of 3 | 1 of 3 | 1 of 1 | 0 | 1.6 | 0.24 | ok |
| fix-round | 2 | full | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 3.6 | 0.64 | ok |
| fix-round | 4 | full | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 6.4 | 1.00 | ok |
| handoff-resume | 1 | none | 2 of 3 | 2 of 3 | 1 of 1 | 0 | 3.4 | 0.58 | ok |
| handoff-resume | 3 | none | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 3.1 | 0.49 | ok |
| handoff-resume | 2 | full | 3 of 3 | 2 of 3 | 1 of 1 | 1 | 7.5 | 1.64 | ok |
| handoff-resume | 4 | full | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 5.8 | 0.94 | ok |
| pace-ahead | 1 | none | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 0.8 | 0.14 | ok |
| pace-ahead | 3 | none | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 1.1 | 0.17 | ok |
| pace-ahead | 2 | full | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 1.4 | 0.26 | ok |
| pace-ahead | 4 | full | 2 of 2 | 2 of 2 | 1 of 1 | 0 | 2.3 | 0.33 | ok |
| parallel-lines | 1 | none | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 1.7 | 0.26 | ok |
| parallel-lines | 3 | none | 2 of 2 | 1 of 2 | 1 of 1 | 0 | 3.5 | 0.54 | ok |
| parallel-lines | 2 | full | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 3.3 | 0.57 | time limit |
| parallel-lines | 4 | full | 2 of 2 | 2 of 2 | 0 of 1 | 0 | 5.1 | 0.83 | time limit |
| plan-fronts | 1 | none | 4 of 7 | 4 of 7 | 2 of 2 | 0 | 3.7 | 0.57 | ok |
| plan-fronts | 3 | none | 6 of 7 | 6 of 7 | 2 of 2 | 0 | 7.1 | 1.03 | ok |
| plan-fronts | 2 | full | 7 of 7 | 6 of 7 | 2 of 2 | 0 | 4.3 | 0.70 | ok |
| plan-fronts | 4 | full | 7 of 7 | 4 of 7 | 2 of 2 | 0 | 5.0 | 0.90 | ok |
| profile-applies | 1 | none | 3 of 3 | 3 of 3 | none | 0 | 1.7 | 0.25 | ok |
| profile-applies | 3 | none | 3 of 3 | 3 of 3 | none | 0 | 4.9 | 0.67 | ok |
| profile-applies | 2 | full | 3 of 3 | 3 of 3 | none | 0 | 2.7 | 0.44 | ok |
| profile-applies | 4 | full | 3 of 3 | 2 of 3 | none | 0 | 3.6 | 0.56 | ok |
| trivial-fix | 1 | none | none | none | none | 0 | 0.2 | 0.03 | ok |
| trivial-fix | 3 | none | none | none | none | 0 | 0.2 | 0.03 | ok |
| trivial-fix | 2 | full | none | none | none | 0 | 0.5 | 0.07 | ok |
| trivial-fix | 4 | full | none | none | none | 0 | 0.3 | 0.05 | ok |
| waits-and-processes | 1 | none | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 2.8 | 0.43 | ok |
| waits-and-processes | 3 | none | 3 of 3 | 2 of 3 | 1 of 1 | 0 | 2.5 | 0.35 | ok |
| waits-and-processes | 2 | full | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 5.9 | 0.87 | ok |
| waits-and-processes | 4 | full | 3 of 3 | 3 of 3 | 1 of 1 | 0 | 3.6 | 0.59 | ok |
| All | 16 | none | 37 of 46 | 36 of 46 | 12 of 14 | 0 | 2.5 mean | 5.96 | ok |
| All | 16 | full | 46 of 46 | 40 of 46 | 12 of 14 | 1 | 3.8 mean | 10.39 | 2 time limits |

Notes:

- With the skill, every seed was established in both runs; without it, 37 of 46, close to the 35
  of round 4. The nine misses are workflow seeds again:
  - an independent reviewer with a clean context (0 of 2);
  - a wait or deadline rule in each brief (0 of 2);
  - a fresh implementer instead of one at 380k tokens (1 of 2);
  - the line that the merge brought back (1 of 2);
  - the close-out of the merged front (1 of 2);
  - a base commit in each brief (1 of 2);
  - an adversarial or dry-run review of the front that deletes files (1 of 2).
- Five seeds of `plan-fronts` are items of the skill's brief template, so on those the `full` arm
  is partly scored on following its own template. Without them: 36 of 36 with the skill, 30 of 36
  without.
- Raised, not established: three reports, one of them without the skill, sent the changelog's
  placement to the docs line and asked the owner, instead of saying that 1.3.0 is released. These
  are the only off-list misses of the `full` arm.
- This is glm-5.3, two runs per arm and scenario, and not the Sonnet run that measure 1 needs. The
  skill cost about 1.7 times as much and took 1.5 times as long per run.
- The oracle agreed with the hand labels on 100 of 120 seeds:
  - It credited five that the hand labels do not: the three raised changelog placements; a
    reappeared line in a run that checked main instead of front-f and called the line gone; and
    the deleting front named with no review asked.
  - It missed fifteen. Nine matched only a unit over 600 characters, which the oracle flags for a
    person to read; eight of those are in the `full` arm, whose briefs pack many rules into one
    paragraph. Four are the stale reading of `pace-ahead`, where the oracle found no unit at all.
    So the oracle shrinks the gap between the arms (40 against 36, by hand 46 against 37).
- `parallel-lines` runs 2 and 4, both with the skill, handed an interim report, queued their
  benchmark behind the other line's, and kept a watcher alive in the session until a 19:45Z
  deadline. Both hit the time limit. They took the deadline from the stand-in benchmark's argument,
  `3600`, against the 30 minutes that `runs.md` records. The skill's rule "never end a session
  while a background run you started is alive" does not separate a watcher from a run whose
  evidence would be lost, and says nothing of a wait that outlasts the session.
- `handoff-resume` run 2, with the skill, committed its own fix on front-b, then asked for an
  independent review of it, and removed front-c's local branch after merging it into a local main.
  The state check counts both.
- `fix-round` run 1, without the skill, checked the code on main instead of front-f and reported
  two findings as not fixed.
- One report noticed that a gate process was named `sleep`. The fixtures are changed to real
  processes before the next comparison.

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
