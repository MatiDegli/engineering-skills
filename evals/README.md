# Audit evaluations

Each case under `cases/` is a small fictional repository with seeded defects. `expected.json` lists
the criteria an audit must report as findings (`must_find`) and the criteria it must not report as
findings because they hold or do not apply (`must_not_flag`). The values explain each choice.

`must_find` credits a criterion whenever a report flags its ID, for any reason, so it cannot tell
whether an audit found a particular defect. An optional `defects` list can:

```json
"defects": [
  {"description": "...", "ids": ["SEC-02"], "at": "app/checkout.py:71-72",
   "terms": ["returning_customer", "caller"], "since": "2026-10-18"}
]
```

`description` names the defect in results. `ids` lists every criterion the defect may be reported
under, because an audit files a behavior defect under the closest criterion. `at` is a
`path:line` or `path:first-last` in the case's `repo/`. `terms` and `since` are optional.

A defect is found when a single row of the report's findings table meets all of these:

- Its ID is in `ids`, and its status is `partial`, `pending-implementation`, or
  `pending-verification`.
- Any of its cells cites the file of `at` with a line or range that overlaps the lines of `at`. A
  path resolves by its full relative path or else a unique suffix, as in the citation check, and a
  citation without a line number does not count.
- When `terms` is present, the row contains at least one term, ignoring case; a term made of
  digits matches only a whole number, so `500` does not match `5000`. The terms name the
  mechanism, so a row that cites the right lines for another reason, such as a missing test, does not
  find the defect.

`since` (YYYY-MM-DD) dates a defect: it counts only when the report is scored as of that day or
later. `score --as-of YYYY-MM-DD` sets the day, today in UTC by default, and `summarize` uses the day
of the round's first `start` line in `log.txt`. When a run finds a real defect that the case does not
seed, add it with `since` set to that day: earlier rounds keep their scores. `must_find` stays as it
is, because recorded results depend on it.

`score` prints `Found 1 of 3 seeded defects at their location.` and lists the defects not found only
when the case counts a defect, and neither changes the exit code.

The cases measure three things: coverage of every criterion ID, recall of seeded gaps, and false
positives. They do not prove that an audit finds every problem in a real repository.

A case whose `expected.json` sets `"reserved": true` is run, scored, and recorded like any other, but
its results are never used to change the skill or the criteria. It shows whether improvements made
on the other cases carry over or only fit them.

## Running a case

From the repository root, in WSL2 or Linux:

```bash
python3 -m tools.evals prepare python-service /tmp/audit-python-service
```

Start an agent in the prepared directory with the `auditing-repositories` skill installed and ask:
"Audit this repository." Save its final report outside the prepared directory, then score it:

```bash
python3 -m tools.evals score /tmp/report-python-service.md python-service
```

The command exits with 1 when a seeded gap is missed, a criterion is falsely flagged, an ID is missing
or repeated, the report uses an unknown ID or status, or a high finding's evidence is not marked as
reproduced or inferred. It also exits with 1 when the report contains a string listed in
`must_not_contain`, such as a seeded secret, or cites a line outside a case file. Run
`python3 -m tools.evals check <report> <case>` for these last two checks on a report without IDs.
Both commands also list citations whose quoted code sits on other lines of the cited file; that
list is a pointer for review and does not change the exit code.

The catalog is `criteria.md` plus one `criteria-<area>.md` file per area that only some repositories
need. A report closes an area that does not apply with its wildcard on a
`not-applicable areas:` line, such as `- not-applicable areas: AGENT-* (no agents contribute)`, and
the scorer counts that entry for every ID of the area. A wildcard for a prefix that is not an area
counts as an unknown ID.

After an audit, `python3 -m tools.evals verify <case> <destination>` checks that the prepared
repository is unchanged: the same revision as a fresh preparation, and no modified, untracked, or
ignored files.

`top_priorities` lists, in order, the gaps a reviewer should act on first, and `max_high` caps the
high findings a case justifies. The maintainer fixes both before reading any report. The scorer
prints which priority action names each top priority and how many high findings fall outside them;
these lines compare reports and do not change the exit code.

Cases contain intentional defects. Do not fix them, deploy them, or run their code outside a
disposable environment; some tests call external hosts.

## Headless rounds with Claude Code

`tools/claude_rounds.py` runs a round of full-skill audits with Claude Code's headless mode; another
agent needs its own runner. Keep the round directory outside this repository and outside `/tmp`:

```bash
python3 -m tools.claude_rounds plan ~/eval-runs/round10 --run 51=claude-opus-5-5 --run 52=claude-sonnet-5-5
python3 -m tools.claude_rounds run ~/eval-runs/round10 --budget-usd 10
python3 -m tools.claude_rounds summarize ~/eval-runs/round10
python3 -m tools.claude_rounds clean ~/eval-runs/round10
```

`plan` exports the skill from a revision into a temporary directory, away from the reports, and
prepares one repository per run and case; `--case` takes a case name or directory and may repeat. A
run may name its own revision and level, as in `--run 66=claude-sonnet-5-5@8b2a2c6` or
`--run 67=claude-opus-5-5+catalog`: the catalog level receives only the `criteria*.md` files, the
none level nothing, and a none-level report is marked for scoring by hand. A round that tests a
change includes the current version as a control, with the same models and runs, in the same plan:
`plan` lists the jobs case by case, so both arms run side by side.
`run` starts agents and spends usage, so the maintainer runs it or allows it; `--budget-usd` stops
launching audits once the finished ones reach that API-equivalent cost, which on a subscription
measures quota rather than money. `--provider-url glm-5.3=URL --provider-key glm-5.3=KEY_FILE` runs
a model from another provider with only host variables, its own Claude Code configuration directory
so the CLI does not use the user's Claude login, every model alias set to that model, and the key
read by an `apiKeyHelper` from a file of mode 600; a run whose key source is not that helper is
marked. That keeps the key out of the environment and the settings file. It does not hide the key
from the audit, which runs as the same user with the Bash tool and no sandbox, so a shell command
can read the file. The settings also deny `Read` on the key's directory with paths anchored at the
filesystem root, which stops Claude Code's Read tool and the file commands it recognizes, such as
`cat`, but not a script or a command that reads without naming the file. `summarize` scores every
report,
verifies every prepared repository, and writes `summary.md` with the tables that RESULTS.md records.
The tables get a "Defects at location" column only when a case in the round counts a defect, so
older summaries keep their shape.
`clean` removes only the directories that `plan` created. `run --stagger-seconds` (5 by default)
spaces launches, so later audits read the prompt cache the first one wrote.

Most of a round's cost is cached context written and reread, not generated text.
`python3 -m tools.claude_ledger rounds <runs-dir>` shows each model's share of weighted tokens by
kind (cache writes, cache reads, output), and `transcripts ~/.claude/projects/<project>` does the
same for the sessions and subagents that coordinate the work. Measure with it before and after a
change meant to save cost.

Each mechanism answers an incident in this repository's evaluations:

| Incident | Mechanism |
| --- | --- |
| An audit that lost its scratch path extracted files into this repository (run 10) | Each run starts in its prepared repository, with the skill exported outside this repository |
| Parallel runs that found an expired login raced to refresh it, and all failed before their first tool call | One short call per model, one at a time, before the parallel runs; a run whose login refresh fails is retried after a random pause |
| Two lines of work could start rounds at once on one machine, sharing the login and the host | `run` holds one lock per provider for the whole round, all or none: `~/.cache/engineering-skills/rounds.lock` for the Claude login and `rounds-<host>.lock` beside it for another provider. A second round on a provider in use exits naming the holder, or waits `--lock-wait-minutes`. Rounds on different providers run at once; `log.txt` records the other rounds' locks at the start and the end, and `summarize` marks a round that overlapped another, since its minutes are not comparable |
| The `haiku` alias resolved to an older model than intended, and an older CLI did not know the newer model's ID | Full model IDs; the short call stops the round when the CLI does not serve a model, and a run whose stream names another model is marked |
| An agent started inside a repository loads that repository's agent settings, hooks, skills, and agents | Runs load only user settings, with hooks off, and fix the effort level instead of inheriting it |
| Rounds kept under `/tmp` lost their scripts and streams when WSL restarted | The round directory keeps the plan, streams, reports, and summary; `plan` warns when it is under the temporary directory |
| The same skill cost 43% more in the afternoon than in the morning, and the rise was first blamed on a rule (runs 59 to 63) | A control arm in the same round, with jobs interleaved case by case |
| Audits of a rewritten private clone queried the hosted repository with the maintainer's GitHub login, found that its history did not match, and one run reported three of ten gaps (run 56) | Runs see no GitHub CLI login or token, so remote settings are unverified the same way in every round |

Each run also has a time limit and its own process group, which is stopped as a whole when the limit
passes or when the runner receives SIGTERM or SIGINT; the runner then starts no other audit, logs the
stop, and exits with 128 plus the signal number. `summarize` lists home paths that tool calls name
outside the run and new temporary entries that a stream mentions. Nothing confines a run to its
paths: it uses the Bash tool as the user, with no sandbox, so the prompt's instruction not to read
other paths is not enforced, and the listing misses a path that a command builds instead of naming.

## Cases from a pinned repository

A case directory may hold `source.json` and `seed/` instead of `repo/`, to test an audit on a
repository too large to read in full. `prepare` then clones the pinned commit of the local
repository that `source.json` names, writes each file under `seed/` at the same path, and removes
each path in its `remove` list. A relative `repository` starts at the case directory, and new seed
files are not executable unless `executable` lists them:

```json
{"repository": "~/Projects/example", "commit": "<full 40-character SHA>", "remove": ["docs/backup.md"]}
```

A replaced or removed path changes in every commit that holds its content at the pinned commit, so
no backport or revert keeps the original. Preparation fails when that content stays reachable at
another path, as after a rename, when a seed would leave a commit empty, or when a seed changes
nothing; seed the other path too, or pick another file. A new file lands in the last commit that
changed a file in its directory. No commit is added, the
history is rewritten in a temporary clone so that every file in the prepared tree has the same age,
and the result keeps one branch and no remote, reflog, or unreachable objects. Git runs without the
caller's Git variables, hooks, and user or system settings, so a hook's exported index or a global
setting cannot reach another repository or change the revision. The source repository is only read,
and a failed preparation leaves no destination.

Such a case can live outside this repository: pass its directory path wherever a command takes a
case name, as in `python3 -m tools.evals prepare ~/cases/large /tmp/audit-large`. `score` and
`check` verify citations against a fresh preparation, which takes longer for a long history.

## Recording results

Add each run to [RESULTS.md](RESULTS.md): date, revision of this repository, agent and model, case,
score output, and notes. For a case outside this repository, record its scores and report hashes
but not its reports or files. Run every case after changing the skill, the criteria, or a case, and
compare with the previous results. Results from one agent or model do not transfer to another.

Cost is part of the result: a gain in precision that costs too much is a regression. Compare each
model's mean cost and time, which `tools/claude_rounds.py summarize` reports with tokens and tool
calls, against the previous results on the same cases. A change regresses when, for any model:

- on the cases in `cases/`, it loses a seeded gap, adds a false flag, or raises mean cost or time
  by more than 10%;
- on a large case, it raises mean cost or time by more than 20%, or by any amount without halving
  the wrong or partly correct `high` and `medium` findings.

The maintainer approved these limits on 2026-10-17, before the runs that first apply them. Large
repositories make every extra step costlier, so a rule that adds work should apply only when its
condition arises, such as when a finding is about to be reported.

## Baselines

Runs with the skill show what an agent finds with it, not what the skill adds. A baseline runs the
same cases, model, and harness with less of the skill:

| Level | The agent receives | Scoring |
| --- | --- | --- |
| No skill | A request to audit the repository, list its problems with evidence, and give up to five priority actions | By hand |
| Catalog only | `criteria.md` and the report's Findings, Priority actions, and Coverage format, without the procedure or the guides | `score` |
| Full skill | The skill | `score` |

Start every agent in the prepared repository, whose files hold none of this repository, the skill,
or `expected.json`, and give it the skill or the catalog only as its level requires. An agent with a
shell can still read other paths, so tell it not to and check its tool calls afterwards.

A report without the skill has no criterion IDs, so score it by hand against `expected.json` with
these rules, fixed before reading any report:

- A seeded gap is found when the report names the same defect: the same mechanism at the same
  location or, for a missing control, the same missing control. A broader statement that would also
  cover it, such as "CI is weak", does not count.
- A false flag is a claim that contradicts the reason given for a `must_not_flag` entry.
- A priority action places a top priority when it names that gap's defect by the same rule.
- Record, for each seeded gap, the report text that matched it or "missed", so that someone else
  can review the scoring.

The full skill is judged better than the catalog alone, by criteria the maintainer approved on
2026-10-17 before the comparison, when over both runs of every case it:

- places the top priorities in its first five actions at least as often;
- contains no `must_not_contain` string;
- marks fewer high findings outside the top priorities;
- covers every ID at least as completely;
- has no more citations outside a case file;
- and is the maintainer's choice in a blind comparison of reports.
