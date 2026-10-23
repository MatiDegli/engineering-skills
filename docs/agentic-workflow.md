# Agentic workflow lessons

This record keeps what building this repository with coding agents has taught. A coordinating
agent plans, delegates to subagents and to headless evaluation runs, and integrates; reviewers
check plans and tools before they run. Some lessons come from the maintainer's projects, which are
private: they are described here, never linked or quoted. The `coordinating-agents` skill planned
for v0.3 draws its references from this record, and both lines of work add to it.

It is a record of lessons, not a rulebook. Rules live in [AGENTS.md](../AGENTS.md),
[CONTRIBUTING.md](../CONTRIBUTING.md), [evals/README.md](../evals/README.md), and the
[decision record](decisions.md). Each entry states the lesson, the incident that taught it, and the
mechanism that now enforces it, with a link instead of a copy of the rule. When a mechanism changes,
update the entry in place. An entry with no mechanism yet names its follow-up: a rule that only an
agent remembers is not a mechanism.

The evaluation runner's mechanisms, each with its incident, are listed under
[Headless rounds](../evals/README.md#headless-rounds) and are not repeated here.

## Delegation

- **One brief per task, with its premises checked.** A brief gives the base commit, the binding
  decisions, the allowed paths, the verification, the report format, a deadline, and which document
  wins when it disagrees with older notes. Its claims are checked against the current main, citing
  hashes, before an agent receives it. In the maintainer's projects, a stale brief made an
  implementer skip mandatory work. *Follow-up:* a brief template in `coordinating-agents`.
- **Match the worker to the task.** Subagents inherit the coordinator's model unless one is passed.
  The strongest model designs and reviews destructive or security tooling; cheaper models rerun
  probes, survey, and check mechanically. The maintainer asked for this on 2026-10-17 to save
  quota. *Follow-up:* `coordinating-agents`.
- **Hand-backs are short and point to files.** At most about 2,500 characters, with the evidence
  lines inline; longer detail goes to a file. Every line a subagent returns is reread on each later
  turn of the coordinator (see [Cost and context](#cost-and-context)). *Follow-up:* the report
  format in `coordinating-agents`.
- **Workers get the brief, not the skill.** In the maintainer's projects, 335 transcripts held 9
  calls to the Skill tool, and workers read the delegation skill 17 times although it says they do
  not need it. *Follow-up:* `coordinating-agents` puts what a worker needs in the brief; a check that
  this repository's skills activate from natural requests, since every round names the skill.

## Shared state and processes

- **Stop processes by PID, never by pattern.** On 2026-10-18, `pkill -f <probe path>` killed the
  shell that ran it, because the pattern was in that shell's own command line; an earlier waiter
  matched itself the same way with `pgrep -f`. *Follow-up:* the shared-state reference of
  `coordinating-agents`, whose waits-and-processes scenario seeds the trap.
- **Every wait has a deadline and watches the right signal.** On 2026-10-18 a waiter expected two
  workflow runs, but the required checks are two check runs of one workflow run, so it never
  finished. *Follow-up:* an integration script that polls the commit's check runs by name.
- **One scheduler per shared resource.** Parallel runs that found an expired login raced to refresh
  it, and all failed. *Mechanism:* the runner warms each model up once and holds a round lock per
  provider; a second round on the same provider queues with `--lock-wait-minutes` instead of being
  started by hand, and a round that overlapped one on another provider is marked in its summary
  ([Headless rounds](../evals/README.md#headless-rounds)).
- **Git on a repository an agent touched runs that repository's configuration.** Verified on
  2026-10-18: `git status` runs `core.fsmonitor` and clean filters, `.git/commondir` redirects the
  configuration, refs, and objects, and a promisor remote makes plumbing commands fetch through
  `core.sshCommand`; `GIT_ALLOW_PROTOCOL=none` stops that fetch. A plan to compare snapshots instead
  was blocked at review by a reproduced bypass through the index. *Follow-up:*
  [issue 9](https://github.com/MatiDegli/engineering-skills/issues/9).
- **Records go somewhere durable before anything is removed.** A WSL restart wiped `/tmp` with every
  round's scripts and streams (2026-10-17). *Mechanism:* round directories outside the repository and
  `/tmp`, with a warning from `plan`
  ([Headless rounds](../evals/README.md#headless-rounds)).

## Review and verification

- **Reject at the plan, not the code.** Tooling that deletes, rewrites, or guards something gets an
  independent reviewer on a short plan first, then on the code, probing it in throwaway
  repositories. The snapshot plan for issue 9 was blocked at review by a reproduced bypass before
  any code existed (2026-10-18). *Follow-up:* the review reference of `coordinating-agents`.
- **Verify decisive claims; a repeated claim is not evidence.** In the maintainer's projects, a
  documentation fix added three false claims. Here, a 43% cost rise was first blamed on a rule
  (runs 59 to 63). *Mechanism:* a control arm in every round, with jobs interleaved case by case
  ([Headless rounds](../evals/README.md#headless-rounds)).
- **Write results from the source, not from memory.** Numbers, times, and states come from logs,
  run records, or code. A generated report's fixed text goes stale too: in the maintainer's
  projects, a ledger script rerun on a new window kept sentences that had become false and counted
  one compaction twice (2026-10-21). *Mechanism:* `summarize` builds the result tables from the run
  records, and the entries in [RESULTS.md](../evals/RESULTS.md) list their reports' hashes.
- **Check each commit on its own tree when it is made.** *Mechanism:*
  `python3 -m tools.check_range origin/main..HEAD`
  ([decision](decisions.md#2026-10-17--intermediate-commits-that-need-repository-history)).
- **A gate piped into another command does not gate.** On 2026-10-18,
  `bash tools/check_secrets.sh | tail -1 && git push ...` pushed a commit although the scan had
  failed; its findings were false positives, but nothing stopped the push. *Follow-up:* the same
  integration script, running each gate unpiped under `set -o pipefail`.

## Evaluations

- **Fix the criteria before the round.** They go in a file in the round directory; they may change
  only before any report is read, and the record says when the maintainer approved the change.
  *Follow-up:* state it in [Recording results](../evals/README.md#recording-results).
- **Count by hand, blind, when an arm cannot be scored by machine.** No-skill reports have no IDs.
  Every arm is counted with one written rule, on copies under random labels with the mapping kept
  apart, and the coordinator verifies the decisive quotes (runs 149 to 156). *Mechanism:* none-level
  reports are marked for scoring by hand; the blind copies are made by hand.
- **A proxy criterion can punish the effect sought.** "High findings outside the top priorities"
  counted real data-loss defects that a change rightly rated high (runs 149 to 156). *Mechanism:*
  cases list such defects under `defects`. *Follow-up:* leave their rows out of that measure in
  `summarize`.
- **Ask what a noise criterion costs the reader.** Four candidates that found half again as many
  useful items were dropped because true items out of proportion for the project counted as wrong;
  their share of false items matched the control's (runs 262 to 289). *Mechanism:* wrong means
  W-false, and W-moot is recorded apart ([Recording results](../evals/README.md#recording-results)).
- **Before a tiebreak, ask whether the doubt is about frequency or correctness.** More runs answer
  frequency; whether findings are right needs the rows read. Reading them avoided an 11 USD Opus
  tiebreak, and the departure from the planned rule is recorded as the maintainer's decision
  ([decision](decisions.md#2026-10-18--logic-defects-pc-merged-with-two-checks-missed-by-one)).
- **Matchers need adversarial review too.** The term `500` matched inside `5000` and credited three
  control reports (*mechanism:* whole-number terms in `tools/evals.py`, with a test). In runs 157 to
  176, 8 of the 18 defects the matcher missed were correct rows under criteria the case did not
  list, and a ninth cited another line of the same file.
  *Follow-up:* every criterion a correct row can use goes in a defect's `ids`.
- **Margins must exceed the noise.** The same skill text found one defect in 2 of 5 runs and, two
  rounds later, in 4 of 5. A margin of one defect in 40 then reads chance as a regression. It
  recurred in runs 190 to 193: a fixed margin of two useful IDs missed by one, while the
  candidate's own two runs differed by four. *Follow-up:* derive each margin from the observed
  spread, or name a frequency tiebreak in the criteria file before the round.
- **Five runs per arm, and a control in every round.** Two runs per arm made a variant look better
  that five runs showed equal, and the control's own results move between rounds.
  *Mechanism:* the control arm in the same plan
  ([Headless rounds](../evals/README.md#headless-rounds)).

## Cost and context

- **A coordinator's cost is rereading its context.** On 2026-10-17 the coordinating sessions spent
  about 45% of all tokens, 79% of them cache reads over 1,035 turns; one session reread about 906k
  tokens on every turn. Batch independent steps into one call, write long outputs to files and show
  counts, and delegate long mechanical work to fresh subagents. In two of the maintainer's projects,
  automatic compaction at 400k tokens later cut one coordinator's mean context from 503k to 312k,
  yet over the next four days the coordinator still cost about 84 USD in each, among the largest
  drivers (2026-10-21). *Mechanism:* `python3 -m tools.claude_ledger` measures it
  ([Headless rounds](../evals/README.md#headless-rounds)). *Follow-up:* a
  checkpoint that a tool generates, so a fresh session can resume from a file.
- **Bound each agent's context, and start a fresh agent instead of resuming a large one.** In the
  same two projects, ledgers rerun on 2026-10-21 and 2026-10-23 found cost per agent-hour down 43%
  in one and the list-price total down 52% in the other. Most of the fall was
  in what these rules targeted: fix rounds that resumed the same implementer fell from 284 to 12
  USD, and requests above 300k tokens from 763 to 76 USD. *Follow-up:* context caps and a fresh
  agent per fix round in `coordinating-agents`.
- **A cap needs an exit.** A cap of 250 turns stopped four implementers with no report, and two were
  then resumed above the 150k tokens their project allows; a cheaper model's only real task reached
  its 40-turn cap with a partly wrong result and was redone. Compaction keeps the state, and cut
  cost without losing work. *Follow-up:* every cap in `coordinating-agents` asks for a partial
  report before it stops the agent.
- **A saving can move the cost; measure where it went.** A fresh reviewer for each re-verification
  cost about what a resumed one had, about 1.5 USD a round, and Opus reviewers became the largest
  driver at 32%. A cap at 300k tokens saved 687 USD above it and moved 181 USD into the bands below.
  Writing long output to files cut large reports to the coordinator from 18 to 2, while subagents'
  reads of whole files rose from 48 to 113. *Follow-up:* in `coordinating-agents`, each cost change
  names the driver it should cut and the one it could raise, and the next ledger measures both.
- **Count rounds, not only their price.** A checklist and a self-review before hand-off did not cut
  fix rounds: implementer rounds per merged change went from 1.16 to 1.03, and reviewer
  re-verifications rose from about 0.82 to about 1.00 once re-reviews of plans and first reviews of
  fix changes were taken out of a count from agent descriptions, while each round got cheaper. In a
  sample of 21 such rounds, 42% of the findings were sibling paths of the same problem that the fix
  left open and 27% were defects the fix added; one implementer had marked as checked the class of
  defect the reviewer then found. *Follow-up:* the review reference of `coordinating-agents`
  measures rounds per change, and asks each fix for the search that found its sibling paths and a
  mutation for each new guard.
- **A one-hour cache pays only for agents that wait.** Once waits were short, its premium was close
  to the rebuilds it avoided: 7.26 USD paid against about 7.85 estimated in one project, and 19.2
  against about 29.5 in the other. *Follow-up:* `coordinating-agents` gives the longer cache only to
  agents expected to wait more than five minutes.
- **Compare cost windows by the work done, in more than one unit.** Cost per agent-hour fell 43%
  and per merged change 59%, but per thousand changed lines only 6%, because changes had become
  smaller (985 lines against 2,234). Hours need two units too: a window of 87 hours had about as
  many hours of project activity as one of 45, counted once however many agents ran, but 30% fewer
  agent-hours, because about 3.8 agents ran at once instead of 5.6. Cost per hour of project
  activity fell 62%, and part of that fall is the lower parallelism, not efficiency.
  *Follow-up:* `python3 -m tools.claude_ledger` reports cost per agent-hour, per hour of project
  activity, and per accepted outcome beside the total.
- **Rounds as small as the question.** While a skill changes often, diagnostic rounds use one
  cheaper model sized to the one question; the strongest model and the large case validate release
  candidates. *Follow-up:* record the protocol by kind of change in
  [evals/README.md](../evals/README.md).
