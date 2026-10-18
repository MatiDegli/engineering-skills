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
[Headless rounds](../evals/README.md#headless-rounds-with-claude-code) and are not repeated here.

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
  ([Headless rounds](../evals/README.md#headless-rounds-with-claude-code)).
- **Git on a repository an agent touched runs that repository's configuration.** Verified on
  2026-10-18: `git status` runs `core.fsmonitor` and clean filters, `.git/commondir` redirects the
  configuration, refs, and objects, and a promisor remote makes plumbing commands fetch through
  `core.sshCommand`; `GIT_ALLOW_PROTOCOL=none` stops that fetch. A plan to compare snapshots instead
  was blocked at review by a reproduced bypass through the index. *Follow-up:*
  [issue 9](https://github.com/MatiDegli/engineering-skills/issues/9).
- **Records go somewhere durable before anything is removed.** A WSL restart wiped `/tmp` with every
  round's scripts and streams (2026-10-17). *Mechanism:* round directories outside the repository and
  `/tmp`, with a warning from `plan`
  ([Headless rounds](../evals/README.md#headless-rounds-with-claude-code)).

## Review and verification

- **Reject at the plan, not the code.** Tooling that deletes, rewrites, or guards something gets an
  independent reviewer on a short plan first, then on the code, probing it in throwaway
  repositories. The snapshot plan for issue 9 was blocked at review by a reproduced bypass before
  any code existed (2026-10-18). *Follow-up:* the review reference of `coordinating-agents`.
- **Verify decisive claims; a repeated claim is not evidence.** In the maintainer's projects, a
  documentation fix added three false claims. Here, a 43% cost rise was first blamed on a rule
  (runs 59 to 63). *Mechanism:* a control arm in every round, with jobs interleaved case by case
  ([Headless rounds](../evals/README.md#headless-rounds-with-claude-code)).
- **Write results from the source, not from memory.** Numbers, times, and states come from logs,
  run records, or code. *Mechanism:* `summarize` builds the result tables from the run records, and
  the entries in [RESULTS.md](../evals/RESULTS.md) list their reports' hashes.
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
  rounds later, in 4 of 5. A margin of one defect in 40 then reads chance as a regression.
  *Follow-up:* derive each margin from the observed spread, or name a frequency tiebreak in the
  criteria file before the round.
- **Five runs per arm, and a control in every round.** Two runs per arm made a variant look better
  that five runs showed equal, and the control's own results move between rounds.
  *Mechanism:* the control arm in the same plan
  ([Headless rounds](../evals/README.md#headless-rounds-with-claude-code)).

## Cost and context

- **A coordinator's cost is rereading its context.** On 2026-10-17 the coordinating sessions spent
  about 45% of all tokens, 79% of them cache reads over 1,035 turns; one session reread about 906k
  tokens on every turn. Batch independent steps into one call, write long outputs to files and show
  counts, and delegate long mechanical work to fresh subagents. *Mechanism:*
  `python3 -m tools.claude_ledger` measures it
  ([Headless rounds](../evals/README.md#headless-rounds-with-claude-code)). *Follow-up:* a
  checkpoint that a tool generates, so a fresh session can resume from a file.
- **Rounds as small as the question.** While a skill changes often, diagnostic rounds use one
  cheaper model sized to the one question; the strongest model and the large case validate release
  candidates. *Follow-up:* record the protocol by kind of change in
  [evals/README.md](../evals/README.md).
