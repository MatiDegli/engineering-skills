# Cost and pacing

Which cost dominates depends on the shape of the workflow, so measure before choosing a lever. Each
strategy below states what it does, when it applies, what it should cut and what it could raise,
and how to measure it. The repository's profile records which strategies it adopts or rejects, and
why.

## Contents

- Measure first
- Pace the period
- Strategies: small coordinator context; context cap and a fresh agent; caps with an exit; a fresh
  agent per fix round; a longer cache only for agents that wait; route by the task; delegate only
  divisible work; experiments sized to the question
- The period report
- Judging a saving

## Measure first

- Read cost from usage records with a ledger, a script that sums them, never from task counts or
  estimates.
- Report three units beside the total: cost per agent-hour, per hour of project activity (counted
  once however many agents ran), and per accepted outcome, such as a change that reached main with
  passing checks. One unit alone misleads: when changes got smaller, cost per change fell 59% but
  cost per thousand changed lines only 6%; when fewer agents ran at once, cost per hour of activity
  fell 62%, and part of that fall was the lower parallelism, not efficiency.
- Give each quantity one definition, kept in one place. When two tools report it, a shared fixture
  checks both.
- A list price tells how fast a configuration consumes a resource. To translate it into quota or
  credits, calibrate it with your own measurements.

## Pace the period

Applies when the profile sets a quota or budget that resets every *N* days.

- Pace: on day *d* of the period, cumulative use stays at or below *d*/*N* of the reference plus
  the profile's margin, in percentage points of the reference. Compute the period's start from the
  reset time the provider shows, never from the weekday.
- Read usage at the start of each session and before every large launch, such as an evaluation
  round, a review by several agents, or work on the strong tier.
- Ahead of pace: stop experiments; if still ahead, defer large launches too. Closing and repair
  work continues.
- Behind pace near the reset: pull work forward. The order stays: close and repair, then delivery,
  then experiments.
- Each resource, whether a quota or a credit balance, keeps its own measured pace. Use more of one
  that runs below its linear pace, to spare the others. Change routing only when a quota is past
  its margin, or when the period's spend of credits or balance passes the plan.

## Strategies

### Small coordinator context

- Does: batches independent steps into one call, writes long outputs to files and shows counts,
  asks for short hand-backs, delegates long mechanical or read-heavy work to fresh agents, and
  keeps the state record current so a fresh session can resume from it.
- Applies when: a coordinating session runs for many turns.
- Should cut: the coordinator's rereading of its context. One measured set of coordinating sessions
  spent about 45% of all tokens, most of them cache reads.
- Could raise: workers' reads of whole files.
- Measure: the coordinator's share of tokens and its mean context per turn.

### Context cap and a fresh agent

- Does: caps each agent's context; past the cap, a fresh agent with a handoff replaces resuming.
- Applies when: agents are resumed across tasks or fix rounds.
- Should cut: requests above the cap. Could raise: requests in the bands below it, and handoffs.
- Measure: cost by context band, before and after.

### Caps with an exit

- Does: the brief's budget asks for an interim report and keeps a reserve for verification and the
  report, below any hard cap of the agent tool. Compaction keeps the work's state where a hard stop
  would lose it.
- Applies when: any cap is set.
- Should cut: work redone after an agent stopped with no report. Could raise: report tokens.
- Measure: agents stopped with no report, and tasks redone.

### A fresh agent per fix round

- Does: sends each fix round to a fresh agent with the findings and a handoff.
- Applies when: changes go through review and fix rounds.
- Should cut: resumed implementers rereading large contexts. Could raise: the cost of reading the
  change again.
- Measure: cost per fix round and rounds per accepted change.

### A longer cache only for agents that wait

- Does: pays for a longer prompt-cache lifetime only for agents expected to wait between turns for
  longer than the default lifetime.
- Applies when: the provider offers more than one cache lifetime.
- Should cut: cache rebuilds after waits. Could raise: the premium paid for agents that never wait.
  Once waits were short, the premium was close to the rebuilds it avoided.
- Measure: premium paid against rebuilds avoided.

### Route by the task

- Does: picks the model and effort for each role by the gain per extra unit of cost. A public
  benchmark, with its date, is a starting point; confirm a configuration on the repository's own
  task before making it the default.
- Applies when: more than one model or effort level is available.
- Should cut: spend on roles that a cheaper configuration does as well. Could raise: rework when the
  cheaper configuration falls short.
- Measure: accepted outcomes and rework per configuration, on the same tasks and the same text.
- Why: compare cost per task, not per token, because what one more level of effort costs differs
  widely between models. A general benchmark score does not replace a run on the repository's own
  task: the harness and the skill change the result too.

### Delegate only divisible work

- Does: delegates work that splits into independent, verifiable tasks, and finishes short chains of
  dependent steps itself.
- Applies when: deciding whether to open a front.
- Should cut: briefing and review overhead on small work. Could raise: the coordinator's context.
- Measure: review effort and rounds per delegated task. Review, not compute, is usually the limit.

### Experiments sized to the question

- Does: diagnostic runs use one economical-tier model sized to the one question. The strong tier and
  the largest inputs validate release candidates only.
- Applies when: evaluating changes to a skill, prompt, or workflow.
- Should cut: strong-tier spend on questions a cheaper run answers. Could raise: the number of runs
  before a release.
- Measure: cost per decision taken.

## The period report

One report per period answers where the spend went and what it bought:

- **How much:** the share of each quota and the credits used, against the pace.
- **On what:** by session and by model, in tokens and in their list-price equivalent.
- **What it bought:** changes that reached main with passing checks, taken from the history by a
  script, against repair, discarded, and failed work.
- **Intensity:** agent-hours and cost per agent-hour, as secondary data.

## Judging a saving

Each cost change names the driver it should cut and the one it could raise, and the next
measurement reads both. In measured projects, a cap on context cut the spend above it and moved
part of it into the bands below, and writing long output to files cut large reports to the
coordinator while workers' reads of whole files more than doubled.
