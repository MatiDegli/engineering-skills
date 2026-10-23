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
repository is unchanged: the same revision as a fresh preparation, the same branches and tags, and
no modified, untracked, or ignored files.

`top_priorities` lists, in order, the gaps a reviewer should act on first, and `max_high` caps the
high findings a case justifies. The maintainer fixes both before reading any report. The scorer
prints which priority action names each top priority and how many high findings fall outside them;
these lines compare reports and do not change the exit code.

Cases contain intentional defects. Do not fix them, deploy them, or run their code outside a
disposable environment; some tests call external hosts.

## Headless rounds

`tools/claude_rounds.py` runs a round of full-skill audits headless, with Claude Code or with
OpenAI's Codex CLI, through one plan and one scorer. Keep the round directory outside this
repository and outside `/tmp`:

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
none and expert levels no files, and their reports are marked for scoring by hand. A round that
tests a change includes the current version as a control, with the same models and runs, in the
same plan: `plan` lists the jobs case by case, so both arms run side by side.

A Codex run names its model with a `codex:` prefix, as in
`--run 300=codex:gpt-6.1-sol@HEAD+full`, and Claude and Codex arms can share a plan. `plan` writes
the backend on every job; a job without one comes from an older plan and is Claude. Unknown
backends, model IDs that are not full IDs, and duplicate run labels are refused.

`run` starts agents and spends usage, so the maintainer runs it or allows it. `--budget-usd` stops
launching audits once the finished ones reach that API-equivalent cost, which on a subscription
measures quota rather than money. It does not bound Codex, whose usage on a ChatGPT login is
counted in tokens: a Codex arm's only cap is the number of its jobs in the plan.
`run --stagger-seconds` (5 by default) spaces launches, so later audits read the prompt cache the
first one wrote.

`--provider-url glm-5.3=URL --provider-key glm-5.3=KEY_FILE` runs a model from another provider with
only host variables, its own Claude Code configuration directory so the CLI does not use the user's
Claude login, every model alias set to that model, and the key read by an `apiKeyHelper` from a file
of mode 600; a run whose key source is not that helper is marked. That keeps the key out of the
environment and the settings file. It does not hide the key from the audit, which runs as the same
user with the Bash tool and no sandbox, so a shell command can read the file. The settings also deny
`Read` on the key's directory with paths anchored at the filesystem root, which stops Claude Code's
Read tool and the file commands it recognizes, such as `cat`, but not a script or a command that
reads without naming the file.

### Run status and resume

Every planned job gets a record, `streams/<label>.run.json`, with its backend, model, revision,
case, prompt hash, times, artifact hashes, usage, and a status: valid, invalid with its reasons,
skipped with its reason, or legacy. A run is invalid on a non-zero exit, a timeout, an error it did
not recover from, no final event or report, another model than the planned one, incomplete
accounting, a web or MCP call, a change to its prepared repository, or an error in the runner
itself. `run` exits non-zero when a job is neither valid nor legacy, and with 128 plus the signal
number when it was stopped.

Run again on a round, `run` skips each job whose record is valid and matches the plan, and launches
the others; a valid record that no longer matches the plan is first marked invalid. A job's old
report is deleted only just before the new launch, after the last stop and budget checks and after
a record saying the relaunch started, and the old record is kept as `<label>.run.<n>.json`. A
valid job whose report or session copies changed after the run becomes invalid instead of being
launched again; delete its record to rerun it. A job whose prepared repository is gone, as after `clean`, stays as recorded.
A job from an older plan with a report and a clean repository but no record is legacy: it is not
rerun, it credits its findings, and it is shown as unverified. An older round summarized after
`clean` has no record to go on and credits nothing.

`summarize` lists every planned job with its status, scores the reports of valid and legacy runs,
shows a valid run whose report or session copies changed as invalid, notes a later change to a
prepared repository without changing a recorded status, and writes
`summary.md` with the tables that RESULTS.md records. Jobs that are not valid stay in the
denominators and credit nothing, and each model's row says how many of its runs were valid. The
tables get a "Defects at location" column only when a case in the round counts a defect. `clean`
removes only the directories that `plan` created.

### Codex

Codex audits run one at a time on their own worker, whatever `--jobs` says, so queued Codex jobs
leave the Claude workers free. A Codex job checks the stop, the budget, and the login state again
once its turn comes. The round holds `rounds-codex.lock` beside the other locks, and a Codex-only
round runs no Claude command. Each audit runs:

```text
codex exec --json -C <repo> -m <model> -c model_reasoning_effort="high" --sandbox workspace-write
  -c project_doc_max_bytes=0 -c check_for_update_on_startup=false -c web_search="disabled"
  -c agents.max_concurrent_threads_per_session=8 --disable plugins --disable goals --disable personality --disable apps --disable browser_use
  --disable browser_use_external --disable computer_use --disable image_generation
  --disable in_app_browser --disable memories -o <streams>/<label>.last-message.md "<prompt>"
```

It gets stdin from `/dev/null`, keeps `HOME` so that the user's Codex login is used, and gets an
empty `GH_CONFIG_DIR` and no hosting tokens, API keys, `CODEX_HOME`, or `ANTHROPIC_*` or `CLAUDE_*`
variables. `project_doc_max_bytes=0` keeps a case's `AGENTS.md` out, `web_search="disabled"` removes
the hosted web search, and the disables leave the agent its shell, waits, requests for user input,
a clock, and helper agents. Codex runs three helpers at once unless configured and refuses a
fourth, so `agents.max_concurrent_threads_per_session=8` lets eight run, and the warm-up checks
that the setting took effect.

Before the audits, `codex login status` must pass, and only its exit status is kept. Then one short
run per model with pending jobs checks the setup in a temporary Git repository whose `AGENTS.md`
holds a code word. On Codex 0.163.0 the session file does not record the agent's tools, so the model
is asked for them as a `{"tools": [...]}` object. The round stops when the reply contains the code
word; when the tools lack one of the expected set, or include one outside it and outside the tools
inside `exec` (file patches, commands, images, a clock, MCP resources), which the model lists in
some answers only; when a command in the agent's own shell prints a forbidden variable name or finds
another GitHub configuration; when the agent's instructions do not state nine concurrency slots,
eight helpers and the agent; or when the run errs, does not finish, or records another model. The
probe prints names, never values.

The JSON stream carries neither the model nor the helpers' work, so the runner reads Codex's
session files. It finds the run's helpers, and theirs, by their parent thread ID, waits up to 60
seconds for each to end, checks that each successful spawn has a session file and that every
thread ran the planned model, and copies the files to `streams/<label>.sessions/` with a manifest
of hashes. Tokens are each thread's last cumulative count, summed. A field Codex does not report is
unavailable, not zero; reasoning tokens are part of output; and when a session is missing, the
totals are unavailable and the record keeps a lower bound. Tool calls count once per call ID across
threads. The report is the main thread's last message, and the `-o` file only cross-checks it.

A login or usage-limit error stops further Codex launches, with no retry. Other errors invalidate
only their run, or become notes when the run recovers. Rows for Codex show no USD, and rounds with
Codex add the mean uncached input and the mean reasoning tokens. A run's duration starts when it
gets its turn; its time in the queue is recorded apart.

### Cost, incidents, and limits

`python3 -m tools.claude_ledger rounds <runs-dir>` reads the final cumulative model totals in each
stream, including helpers, without adding the lead's usage again. `transcripts
~/.claude/projects/<project>` reads sessions and subagents, deduplicating response IDs across files.
It uses an agent's `agentType` metadata for grouping, never words such as "reviewer" in its prompt.
General-purpose agents remain general-purpose; the ledger does not infer their actual role.

Both commands show raw tokens and list-price USD ranges using the dated snapshot in
`tools/claude_ledger_prices.json`. The snapshot was checked on 2026-10-22 against
[Anthropic's pricing](https://platform.claude.com/docs/en/about-claude/pricing). Pass `--prices FILE`
to use another recorded snapshot. Every date is priced at that one snapshot; this is revaluation at
those prices, not historical billing or subscription quota. Unknown models stay unpriced unless
all token counts are zero, in which case the record costs zero and remains counted.
Unknown write TTLs stay unknown and give a price range; aggregate Haiku usage also gives a range
when individual request context tiers are missing.
The CLI's recorded amount stays separate in the JSON output.

Measure with the ledger before and after a change meant to save cost.

Each mechanism answers an incident in this repository's evaluations:

| Incident | Mechanism |
| --- | --- |
| An audit that lost its scratch path extracted files into this repository (run 10) | Each run starts in its prepared repository, with the skill exported outside this repository |
| Parallel runs that found an expired login raced to refresh it, and all failed before their first tool call | One short call per model, one at a time, before the parallel runs; a run whose login refresh fails is retried after a random pause |
| Two lines of work could start rounds at once on one machine, sharing the login and the host | `run` holds one lock per provider for the whole round, all or none: `~/.cache/engineering-skills/rounds.lock` for the Claude login and `rounds-<host>.lock` beside it for another provider. A second round on a provider in use exits naming the holder, or waits `--lock-wait-minutes`. Rounds on different providers run at once; `log.txt` records the other rounds' locks at the start and the end, and `summarize` marks a round that overlapped another, since its minutes are not comparable |
| The `haiku` alias resolved to an older model than intended, and an older CLI did not know the newer model's ID | Full model IDs; the short call stops the round when the CLI does not serve a model, and a run whose stream names another model is marked |
| A Claude agent started inside a repository loads that repository's agent settings, hooks, skills, and agents | Runs load only user settings, with hooks off, and fix the effort level instead of inheriting it |
| Rounds kept under `/tmp` lost their scripts and streams when WSL restarted | The round directory keeps the plan, streams, reports, and summary; `plan` warns when it is under the temporary directory |
| The same skill cost 43% more in the afternoon than in the morning, and the rise was first blamed on a rule (runs 59 to 63) | A control arm in the same round, with jobs interleaved case by case |
| Audits of a rewritten private clone queried the hosted repository with the maintainer's GitHub login, found that its history did not match, and one run reported three of ten gaps (run 56) | Runs see no GitHub CLI login or token, so remote settings are unverified the same way in every round |
| Audits of real repositories could not read CI runs, branch protection, or other branches, because a prepared case has one branch, no remote, and no GitHub login (runs 188 and 189) | A case's `source.json` may keep the source's branches no newer than the pin and ask for a snapshot of the hosted state, read once when the round is planned (see [Cases from a pinned repository](#cases-from-a-pinned-repository)) |
| An audit that started subagents listed the maintainer's other Claude sessions and could have messaged them, and tried workflow and monitor tools to wait for its helpers (run 260) | Runs get only Bash, Read, Grep, Glob, and Agent (`--tools`), and their subagents inherit that list |
| Codex waited for more input on stdin (run 299) | stdin from `/dev/null` for login checks, warm-ups, and audits |
| Codex 0.149.1 refused the requested model on a ChatGPT login (2026-10-21) | One short run per model stops the round on an error or a missing final event |
| Codex's hosted web search was on by default, and the first warm-up through the runner listed it (round 43) | `web_search="disabled"`; the warm-up refuses any tool outside the known set |
| A case's `AGENTS.md` loads into a Codex run by default (probe, 2026-10-21) | `project_doc_max_bytes=0`, checked by the warm-up's code word |
| The Codex stream named neither the model nor the helpers, which used 63% of the input tokens (runs 299 and 300) | Session files found by parent thread, each thread's model checked, and accounting marked incomplete when one is missing |
| Helpers made two scratch directories that the main stream never named (run 299) | Path and leftover listings also read every helper's session |
| Helpers address the main agent as `/root`, which the path listing read as a home path (round 43) | Path listings skip the calls between agents |
| Codex ran at most three helpers at once, so a candidate's lead waited for a slot or merged or dropped roles (round 44); in a probe with five helpers that each slept 45 seconds, the fourth and fifth spawns failed with "agent thread limit reached" | `agents.max_concurrent_threads_per_session=8`, with which the probe's five helpers ran; the warm-up checks the slots the agent is told |
| In review (2026-10-21): a child could outlive its process group's leader, missing reports dropped out of the scores, and a failed run could pass for a good one | A status for every job, invalid runs in the denominators, a non-zero exit, and SIGKILL by group |

Each run has a time limit and its own process group. When the limit passes or the runner receives
SIGTERM or SIGINT, the group is stopped as a whole, with SIGKILL after a grace period even if its
leader has already exited; the runner then starts no other audit and logs the stop. After a normal
exit the group gets SIGTERM, then SIGKILL after five seconds, so no child outlives its run. Login
checks, version checks, and warm-ups run under the same deadlines and stop. `summarize` lists home
paths that tool calls name outside the run, and new temporary entries that a stream or a helper's
session mentions.

Limits, reviewed on 2026-10-21:

- Nothing confines a run's reads. Claude Code runs the Bash tool as the user with no sandbox.
  Codex's `workspace-write` sandbox blocks the network and writes outside the copy and `/tmp`, but
  not reads, so an audit can read the user's files, Codex's login included. The prompt's
  instruction not to read other paths is not enforced. Codex's system skills and the user's own
  skills stay visible, and audit sessions stay in the user's Codex history.
- The path listings are partial: they miss a path that a command builds or names relatively, and a
  clean repository at the end does not prove that nothing was written in it.
- Runs 302 to 306 ran with Codex's default of three helpers at once. v0.2.3's passes use three; a
  procedure that asks for more is compared fairly only from later rounds. Compare the helpers in
  each run's `streams/<label>.sessions/` before reading its result.
- The catalog and the expectations used for scoring are read when `summarize` runs; they are not
  snapshotted.
- Checked against the real CLI (runs 299 and 300 and round 43, Codex 0.163.0): stdin, `AGENTS.md`,
  the tool set with web search off, reading run 300's session files for helpers, completeness, and
  tokens, and, by probe on 2026-10-22, the helper-slot setting. Tested only with a stand-in: helpers of helpers, the error texts, the login output,
  the memories and update-check settings, and process cleanup inside Codex's sandbox. Not known:
  whether the server can serve another model than the one it records, whether cached input is always
  part of input, and what a request for user input does with stdin closed. The warm-up's tool list
  is the model's own claim.

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
and the result keeps one branch, unless `branches` below says otherwise, the tags the pin already
had (below), and no remote, reflog, or unreachable objects. Git runs without the
caller's Git variables, hooks, and user or system settings, so a hook's exported index or a global
setting cannot reach another repository or change the revision. The source repository is only read,
and a failed preparation leaves no destination.

Two optional keys give an audit of a real repository what its host knows; a case without them is
prepared and prompted as before:

```json
{
  "repository": "~/Projects/example",
  "commit": "<full 40-character SHA>",
  "github": "owner/name",
  "branches": true
}
```

With `"branches": true`, the prepared repository also keeps the source's other branches as local
branches: its local branches first, then its remote-tracking ones (`refs/remotes/<remote>/<name>`),
and the first of a name wins. Only a branch whose head commit's committer date is not later than
the pinned commit's is kept, so nothing committed after the pin leaks in; `main`, which is the
pinned branch, and a remote's `HEAD` are left out. Seeds are refused with `branches`, since seeding
rewrites `main` only. The result still has no remote, reflog, or unreachable objects, and `verify`
also checks that each kept branch is where the preparation left it.

In both modes, the prepared repository keeps the source's tags that the pin already had: each tag
whose target commit is the pin, an ancestor of the pin, or an ancestor of a kept branch head, and
whose date is not later than the pinned commit's committer date: the tagger date for an annotated
tag, the target commit's committer date for a lightweight one. Annotated tags stay annotated and
every other tag is absent, so an audit that compares the last two release tags sees the releases
the pinned commit knew and none made later. A case with seeds keeps no tags: the seed rewrite
would leave them naming the original commits. `verify` reports a tag that was added, removed, or
moved.

With `"github"`, `claude_rounds plan` reads the host once per case with the `gh` login of the user
who plans the round, writes `<round>/hosted/<case name>.json`, and copies it to `hosted-state.json`
beside each prepared repository of the case, never inside it. Each level's prompt then ends with
the same short paragraph, which names that file, allows reading it although every level says not
to read other paths, and says to use it in place of the host. The snapshot holds the pinned
`commit`, `taken_at` in UTC, the repository's default branch, visibility, and archive flag, the
check runs, Actions runs, and commit statuses on the pinned commit with their total counts, and
the default branch's protection and rules without the API's links. An endpoint
that fails is recorded as `{"error": message}` and the plan goes on, since "Branch not protected"
is information. Issues, pull requests, security alerts, and other settings stay out: issues would
change what counts as known. The snapshot is the host's state when the round was planned, not when
the pinned commit was made, and it is the same for every run of the round. It holds no token.

Such a case can live outside this repository: pass its directory path wherever a command takes a
case name, as in `python3 -m tools.evals prepare ~/cases/large /tmp/audit-large`. `score` and
`check` verify citations against a fresh preparation, which takes longer for a long history.

## Recording results

Add each run to [RESULTS.md](RESULTS.md): date, revision of this repository, agent and model, case,
score output, the CLI version, each run's status with its reasons, and notes. Jobs that are not
valid stay in the counts and credit nothing; give each model's valid runs, and mark legacy runs as
unverified. For a case outside this repository, record its scores and report hashes but not its
reports or files. Run every case after changing the skill, the criteria, or a case, and compare
with the previous results. Results from one agent or model do not transfer to another.

For Codex on a ChatGPT login, record tokens instead of USD: input, cached input, output, and
reasoning tokens over the main thread and its helpers, with reasoning already part of output.
Write "unavailable" for a field Codex did not report, say how many runs a mean covers, and keep
the usage and time of failed attempts.

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

An audit of one of the maintainer's repositories has no seeded answer. Its items are matched to the
list of earlier rounds, and the new ones are verified against a clean copy and rated blind by the
repository's maintainer or a session working for them: U (useful), K-rec (known and recorded),
K-unrec (known, not recorded), W-false (false), W-moot (true, but not worth acting on in this
project), or W-harness (depends on what the prepared copy lacked). Useful is U plus K-unrec; wrong
is W-false. W-moot is recorded apart and counts as neither, since what is out of proportion for one
project can still be useful to another reader. The maintainer set this on 2026-10-20; earlier
rounds counted W-moot as wrong.

## Baselines

Runs with the skill show what an agent finds with it, not what the skill adds. A baseline runs the
same cases, model, and harness with less of the skill:

| Level | The agent receives | Scoring |
| --- | --- | --- |
| No skill | A request to audit the repository, list its problems with evidence, and give up to five priority actions | By hand |
| Expert prompt | The prompt in [`prompts/expert.md`](prompts/expert.md), with the same limits on paths and reply as every level | By hand |
| Catalog only | `criteria.md` and the report's Findings, Priority actions, and Coverage format, without the procedure or the guides | `score` |
| Full skill | The skill | `score` |

The no-skill level measures the skill against the request most people would type. The expert
level measures it against a good prompt, to tell what the catalog and the procedure add beyond one.
Its prompt was written on 2026-10-19 by Opus 5.5, run with `--safe-mode --tools ""` from an empty
directory, so it saw neither this repository nor any result. It was asked for the prompt an
experienced reviewer would give an agent that audits a repository it has not seen, of any kind,
non-interactively and read-only, for the report most useful to its maintainer, from its own
experience and without any external checklist, in under 300 words. The prompt is kept as written,
at 364 words. Change it only between rounds that do not compare with each other.

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
