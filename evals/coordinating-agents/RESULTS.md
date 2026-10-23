# Coordination scenario results

Each round records the date, the revisions of the runner and the skill, the model, the scenarios,
and the scores from `python3 -m tools.scenario_rounds summarize`. When a later oracle scores a round
again, both scores stay, with the oracle's revision.

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
