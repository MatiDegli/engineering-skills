# Decisions

## 2026-10-21 — One round runner with Claude and Codex backends

The maintainer asked for rounds on OpenAI's Codex CLI, to spend less Anthropic quota and to see how
the skills work with another provider. This amends the 2026-10-17 decision that another agent needs
its own runner: `tools/claude_rounds.py` keeps plans, locks, process groups, scoring, and cleanup
for both backends, and `tools/codex_backend.py` holds what differs. Separate runners would
duplicate those controls. A job without a backend is Claude, so old plans read unchanged, and a
Codex arm can share a round with a Claude control.

Runs 299 and 300 set what the backend needs: stdin from `/dev/null`, a case's `AGENTS.md` kept out,
and Codex's session files, because its JSON stream omits the model and the helpers, which used 63%
of the input tokens in run 300. Codex audits run one at a time on the maintainer's ChatGPT login,
and their usage is counted in tokens, not USD. The maintainer accepts for now that reads are not
confined, that skills outside the repository stay visible, and that path scans are partial
diagnostics ([issue 9](https://github.com/MatiDegli/engineering-skills/issues/9)).

The same change gives both backends a status for every planned job. A job that is not valid fails
the round and credits no findings, but stays in the denominators. A job from before this change,
with a report and a clean repository but no record, is kept as legacy and unverified instead of
being run again. The maintainer left these choices, and the shared fixes, to the coordinator. The
skill and the scoring of reports do not change. The mechanisms and their limits are under
[Headless rounds](../evals/README.md#headless-rounds).

## 2026-10-20 — Moot items are neutral; helpers become the base

Four candidates that add read-only helpers to the audit (runs 262 to 289) found 72 to 85 useful
items per run on three of the maintainer's repositories, against v0.2.2's 48 and 57. Each was
recorded and dropped, mainly because its noise criterion counted W-moot items, true but out of
proportion for the project, as wrong. Looking at where that noise came from, the maintainer decided
that only false items are a problem: a moot item can still be useful to another reader. Rounds now
count W-false as wrong and record W-moot apart
([Recording results](../evals/README.md#recording-results)).

Read again that way, the helper versions' false share is 1.4% to 7.0% per run against v0.2.2's
2.5% and 3.1%. Runs 278 and 279 (`dde0696`) are the strongest: 85 and 82 useful items, 4 and 6
false, and 67 useful items found by both runs, more than the 62 that two v0.2.2 runs find together.
The one fictional case where their scorer count fell below the control's minus 1 was counted blind
by content: every report of both versions states all six seeded gaps, some under other criterion
IDs. The maintainer judges the extra cost, about 5 USD per audit, marginal against the extra real
problems.

The rounds' verdicts stand under the criteria each fixed; this is a new decision taken with all
four in view. `dde0696` becomes the skill's audit procedure and the base later rounds compare
against. The catalog rules of runs 286 and 287, aimed at moot items, are set aside. The next front
is the false items: most say something is missing (a test, a record, a use) that exists, or that a
document contradicts code it matches.

## 2026-10-19 — Team criteria as an area; v0.2.2 with one noise check missed by one

The final validation of v0.2.2 on three of the maintainer's repositories (runs 241 to 243) met
value and cost and missed noise by 2: the skill had 15 false or moot items against the expert
prompt's 10 plus 3, at the same 17% share. Six of the 15 asked one maintainer for process records.
Rather than a fourth one-maintainer exception, the maintainer proposed loading team criteria
separately. `ed912ec` moves them to a Team area (`TEAM-*`), read only when several people maintain
the project, as the agent, delivery, and operations areas are: an audit cannot over-apply a file it
does not open, and the file costs no context there. REPO-08 and HIST-02 became TEAM-01 and TEAM-02
and are retired; the owner that five core rows asked for became TEAM-03; AGENT-02 stopped asking
that a finished task's brief stay in the repository. STRUCT-03 stays in the core, since a
documented boundary or a cycle matters to one maintainer too.

On fictional cases the area opened where three people maintain the project and stayed closed with
one, with no seeded gap lost (runs 244 to 253). On the real repositories noise fell to 14 against a
bar of 13 (run 254). As the criteria fixed before the round set, the change was merged and the miss
recorded as a known limit: audits still ask one maintainer for some records, and one repository's
paused code path draws items its maintainer considers moot. Rewording stops there, at the point of
diminishing returns the maintainer set for v0.2.x.

Run 254 also found 48 useful items against run 241's 54. Runs 255 and 256 repeated both versions
once: the new version had 105 useful items over two runs against the old one's 104, within a margin
of 10, so the drop was run-to-run variation, and v0.2.2 is proposed for release. Two runs of one
version share about two thirds of the useful items they find between them, so coverage, not the
Team area, is the next front.

## 2026-10-19 — Project shape merged with one check missed by one

In the usefulness trial on three of the maintainer's repositories (runs 188 and 189), 21% of the
skill's items were wrong or not applicable, against a limit of 10%, and 15 of those 22 applied a
criterion where the project's shape makes it moot. `dad6b06` has step 2 record the maintainers, the
software's reach, and whether it is a library, and the rows that depend on them say so. In runs 190
to 195, with Sonnet and two runs per arm, it cut the moot rows in Findings from 20 to 2 and all rows
from 224 to 198. It lost no seeded gap, top priority, or `must_not_flag` check on the fictional
cases, at 1.04 times the cost. It missed one check by one: the criteria of earlier useful findings
had a row 42 times against 45, with a margin of 2. None of the IDs it lacked is a row the change
touches. Most came from one outlier report, and the candidate's own two runs differed by twice the
margin. The maintainer merged it after seeing the rows behind the miss. One pattern is left to
watch: TEST-03 in the library was in both control reports and in neither candidate report.

## 2026-10-19 — Delivery metrics stay out of the audit

The scope decision of 2026-10-18 gave delivery metrics, such as deployment frequency, change failure
rate, and rework rate, an indirect home in a comparison between audits (#21). The maintainer asked
whether they were worth it, and they stay out instead. Most of them need production and incident
records outside the repository, which an audit could reach only with credentials or by asking. DORA
meant them for a team to compare itself over time, not as a threshold, so one audit's figure says
little. The capabilities behind them are checked already: deploys from the repository (#15),
feedback within a budget (#17), a default branch kept green (#18), and releases that record their
changes (DEL-03). Their sources in the review were weak, a secondary summary and a radar entry.
A finding that a project does not measure them would be the kind of checklist item the blind
reviewer of v0.2.0 objected to. A project that already publishes the metrics can cite them as
evidence for those criteria. #21 keeps only the comparison of findings between audits. Eight of the
ten practices outside any repository now stay out, and two keep an indirect home.

## 2026-10-18 — Scope: every practice a repository can show has a destination

A review set 119 practices against the catalog. They came from standards and frameworks such as
OpenSSF and SLSA, delivery and operations research such as DORA and Google's SRE book, code health
and architecture guidance, empirical studies, industry practice, and AI-assisted development. The
catalog covered 66, covered 31 in part, and missed 4; 18 cannot be checked from a repository. None
needs a new ID: the gaps extend existing rows.

The maintainer asked that the audit's scope grow to cover the rest, each item entering when its
evaluation is ready:

- The 35 partial or missing practices map to issues #11 to #20 and #22, in milestones v0.2.2 and
  v0.2.3 except #22, which changes the large-repository sample and needs the private large case.
  A new check enters through the evaluation protocol: a seeded case for it, a `must_not_flag` case
  for its opposite, and a cost margin against the control, since the cost measured at 87 IDs came
  from their number and these changes lengthen rows instead. Guide sentences that only clarify
  need no round.
- Eight belong to the other skills: six review and refactoring practices to coordinating-agents
  (v0.3), and change coupling and change amplification to mapping-repositories (v0.4).
- Ten cannot be checked in any repository. Four get an indirect home: whether module boundaries
  match team boundaries, through the owners a map records (v0.4), and delivery metrics, rework
  rate, and code-health trends, through a comparison between successive audits (#21). The other
  six stay out: contributors from several organizations, team cognitive load, team types, and
  graded test-quality programs are properties of the organization, and arc42 and C4 are templates
  whose content REPO-05 and REPO-06 already require without imposing a format. (Revised on
  2026-10-19: delivery metrics and rework rate stay out too; see that day's entry.)

## 2026-10-18 — v0.2.1 validated with Opus after one fix

The release candidate (PC, K, B, and the guides' contents) was compared with v0.2.0 in runs 177 to
185, with criteria fixed before planning. It met every effect: 28 of 32 logic defects against 22,
counted blind; OPS-02 high and among the first five actions in 8 of 8 reports, against 5; and no
"before release" timing in 8 of 8, against 4. It kept seeded gaps, secrets, top priorities, high
findings, and cost. It missed one check: 12 of 18 reports passed the scorer against 17, because high
findings carried their evidence mark with a qualifier before the colon, such as `Inferred (pytest
not runnable):`, most likely prompted by K's rule that a conditional finding states its condition.
The maintainer chose to fix and confirm rather than accept the miss: `b82b78a` asks for the exact
mark with any qualifier after it, and eight Opus audits of it (runs 186 and 187) left one such mark
where the same cases had four, with seeded gaps and defects unchanged. The self-audit (run 185) found
no high finding; its new items are in issue #10.

## 2026-10-18 — v0.2.1: conditions, release timing, and recovery merged; findings split held back

Issues #4 and #5 change the report's judgment, not its recall. K tells a finding that holds only
under a condition to state it, and gives software already in production or distributed no "before
release" timing; B rates unverified recovery of production data `high`. In runs 157 to 176, with
Sonnet and five runs per arm, K removed "before release" from every production-case report, against
4 of 10 for the control, and B put OPS-02 at high and in the first five actions in 10 of 10, against
1. B met every fixed criterion with the defects counted by hand. K missed the defect margin, one
fewer of 40, by one more: it lost the SKU defect once more than the control and named WELCOME10
only as untested once. Neither text bears on how code is read, and the same skill text found the
SKU defect in 2 of 5 runs two rounds earlier and in 4 of 5 in this control, so the margin was
narrower than the control's own spread. The maintainer merged both, K as a recorded departure from
the margin. The Opus validation of the release candidate measures the defects again.

Issue #3's Minor findings table halved the first findings table, but two of five reports dropped
QUAL-06, a criterion usually rated `low`, from every table and from Coverage, a loss the change can
cause. It stays out of v0.2.1; a variant that keeps every ID visible can be tested later. Later
rounds derive each margin from the observed spread, or name a frequency tiebreak in the criteria
file, and cases list every criterion a correct row can use for a defect: 8 of the 18 defects the
matcher missed here were correct rows under criteria the cases did not list.

## 2026-10-18 — Logic defects: PC merged with two checks missed by one

Issue #1 found that audits with the skill missed logic defects that audits without it found. PC
adds two sentences to `SKILL.md`: the `high` priority covers a business rule that callers can bypass
or that charges, grants, or books wrongly, and step 4 reads configuration that encodes behavior.
In the Opus milestone (runs 149 to 156), PC found 15 of 16 logic defects against 10 for the frozen
skill, 13 without the skill, and 13 with the catalog alone, at the same cost. It missed two checks
of the no-regression criterion by one item each: one top priority, OPS-02 rated medium as in the
v0.2.0 exception, and three more high findings outside the top priorities than the control, one
over the limit, from real data-loss and unauthorized-write defects of `python-service` that the
case does not list as defects. The tiebreak fixed before the round, three more runs per arm on each
affected case, was not run: its likely outcome was clear from both runs, and whether those findings
deserve high is a question of correctness, which reading the rows answered. The maintainer accepted
both misses after seeing the results and merged PC. Listing that case's real defects, so later rounds
exclude them from the limit, is left for later.

## 2026-10-18 — Scenario evaluations for work skills

An audit produces a report that a scorer reads for criterion IDs; a work skill changes what an agent
does. `coordinating-agents` is therefore evaluated with seeded scenarios. Each scenario is a
prepared workspace and a task, plus an oracle that reads three things: the agent's final report,
the state it leaves behind (a stash, a worktree, or a process that another agent owns), and the
commands in its stream. Every round also runs the same scenarios without the skill, as a control.

Three lessons from v0.2.0 shape the design:

- A long checklist displaced judgment. Some seeds are therefore problems that the skill does not
  name, and the skill must not find fewer of them than no skill.
- The scorer saw only what was seeded. A blind comparison by the maintainer therefore accompanies
  the scores, and real findings that were not seeded join their scenario with a date.
- A complete report was harder to use. Reports and hand-backs are therefore measured by length too.

One scenario is a trivial task, where coordination steps count against the run.

The scenarios and a baseline without the skill come before the skill's text. That way the procedure
covers failures that were measured, not every lesson available.

The material lives in `evals/coordinating-agents/`, with its own runner, `tools/scenario_rounds.py`.
The runner reuses the headless safeguards of `tools/claude_rounds.py` without changing it and takes
the same round lock. Each scenario agent runs in its own PID namespace, so a command that kills
processes by pattern reaches only its own scenario. Extending `tools/claude_rounds.py` to cover both
skills is postponed until after v0.3.0, because the audit rounds depend on it while it changes for
v0.2.1.

## 2026-10-18 — No executable mechanism in coordinating-agents v0.3.0

The maintainer's projects enforce bounded waits and exact-PID kills with a shell guard registered as
a hook. They adopted it after rules written into briefs were broken again and again: one
coordinating agent counted about a dozen calls to a forbidden interpreter despite an explicit rule,
and waits that matched their own command line kept running for hours.

The Agent Skills specification allows a `scripts/` directory, so a guard would not break the
portable frontmatter. It is deferred for two other reasons: each agent registers hooks in its own
way, against tool independence, and a guard that filters commands is high-trust code that every
user would have to review.

v0.3.0 states the guard's contract instead:

- what it refuses: waits without a deadline, polling without a timeout, and killing processes by
  pattern;
- the threat it addresses: an agent that forgets, not one that evades;
- the failure modes it must be tested for;
- a deliberate choice between failing open and failing closed.

The scenario evaluations count how often agents with the skill still break these rules. That count
decides whether a reference guard ships in a later version, under the conditions of "No executable
code in the audit skill".

## 2026-10-18 — Separate guides for auditing and coordinating

`coordinating-agents`, planned for v0.3, needs the practices that the audit's agent guide checks:
briefs, review, isolation, and capacity. The audit's guide is written for someone who verifies a
repository. The work skill is read by the agent that coordinates, which needs templates, the order
of the steps, and when to wait, resume, or start fresh.

Each skill therefore keeps its own text for its own reader. "One explanation per rule" holds within
each skill. A test that ships with neither skill maps each criterion from AGENT-02 to AGENT-05 to
the section of `coordinating-agents` that carries it out, so the two texts cannot drift apart
unnoticed.

This is the decision that "Origin and scope" asks of a second skill, and it chooses neither of the
two options named there:

- A shared copy checked for equality was rejected: one text would serve two readers, and every
  change would require evaluating both skills.
- Another packaging, such as a plugin with dependencies, was rejected: the Agent Skills
  specification has no dependencies between skills.

## 2026-10-17 — A secret scan before every push

The self-audit before v0.2.0 found that nothing scanned file contents or history for secrets:
`tools/validate_repo.py` checks only secret-like filenames. `tools/check_secrets.sh` now scans every
commit of every local branch with a pinned, hash-verified Gitleaks, and the integration flow runs it
before the first push, because pushing a branch already publishes it. Its first run found only the
fake key seeded in the `orders-service` case. Running the scan only in CI was rejected: it would
report a leak after publication. Reviewed exceptions are fingerprints in `.gitleaksignore`; a
configuration file and inline `gitleaks:allow` comments are refused, because an agent could use
either to hide a real leak. CI may add the same scan later as a backstop.

## 2026-10-17 — Release v0.2.0 with one level criterion unmet

In the release level comparison (runs 87 to 92), the full skill met four of the five criteria
scored against the catalog alone: no copied secret, 19 high findings outside the top priorities
against 77, complete coverage, and no citation outside a file. It placed 26 of 28 top priorities in
its first five actions against 28. Both misses are OPS-02 in orders-service, which the full skill
rates `pending-verification` and medium because the case's data sits in a managed database whose
backups may exist outside the repository; the case expects it as its second priority. The
maintainer chose to release with this exception recorded rather than reopen the frozen skill. How
an audit ranks unverified backups of production data moves to the secondary line of experiments,
to be validated with Opus at the next milestone. Changing the case's expectation to pass the gate
was rejected.

## 2026-10-17 — Intermediate commits that need repository history

The commit policy asks every commit in a stack to pass the checks on its own. Twenty-three commits
from `2de7861` to `2d5e3e5`, integrated together, pass `python3 tools/check.py` in a checkout with
history but not in a tree without it: the runner tests exported the skill from this repository's
`HEAD` and `HEAD~1`. `0981320` gives those tests their own repository, so the integrated head passes
on any tree. Rewriting the stack would have changed the hashes that RESULTS.md cites as the measured
skill versions, so the maintainer chose to keep them; the skill content of every commit is
unaffected. Checks of a commit's tree must not depend on this repository's history.

## 2026-10-17 — A versioned runner for headless rounds

Headless rounds ran from scripts kept outside this repository. Their safeguards came from
incidents: a login warm-up, a check of the model that ran, user settings only, and a durable record
directory. When a restart cleared `/tmp`, the scripts were lost and had to be rebuilt from a session
transcript. A safeguard that lives in an unversioned file depends on someone keeping it, so the
runner is now `tools/claude_rounds.py`, tested with a stand-in CLI, and `evals/README.md` pairs
each mechanism with its incident. The runner is specific to Claude Code: the skills stay
independent of any agent, and another agent needs its own runner. Keeping the scripts local was
rejected because their results would not be reproducible from this repository.

## 2026-10-17 — A private case for large repositories

Testing how an audit samples a repository it cannot read in full needs a real repository's size and
history: the sample follows entry points, trust boundaries, and the files the log shows changing
most. A generated tree would be uniform enough for an agent to recognize the filler. A public
open-source repository would need network access and a license notice to prepare, and models may
already know it, so an audit could assert what it never checked. The large case therefore starts
from a pinned commit of one of the maintainer's projects, with seeded defects folded into the
commits that last touched their paths, so the history does not point at them. Those projects are
private: the case's seeds and expected findings stay outside this repository, only the maintainer
can reproduce its runs, and RESULTS.md records its scores and report hashes without content. The
cases under `evals/cases` remain the reproducible measure; the preparation code is public and tested
on throwaway repositories.

## 2026-10-17 — Criteria loaded by area

The catalog is a core file plus one file per area that only some repositories need: agent-assisted
development (`AGENT-*`), delivery (`DEL-*`), and operations (`OPS-*`). An audit reads an area file
only when the area applies; otherwise it closes the area in Coverage with its wildcard. With 87
criteria, audits grew longer and costlier, a smaller model omitted IDs, and agents read every guide
even when most did not apply. Areas follow ID prefixes, so a wildcard is unambiguous and no ID
changes meaning; criteria with other prefixes that apply only sometimes, such as PERF-02 or SEC-04,
stay in the core with their own conditions. More areas, or a split of the guides, wait until
measurements show the effect of this one. UI becomes an area when the catalog has UI criteria.

## 2026-10-17 — No executable code in the audit skill

`auditing-repositories` stays Markdown only. Evaluations showed that mechanisms enforce rules
better than written instructions, and the maintainer's projects use guards and hooks for that.
Shipping such a mechanism inside the audit skill was rejected: it would tie the skill to an
interpreter and to each agent's hook system, against the tool independence and portable
frontmatter decisions, and a guard that filters commands is high-trust code that every user would
have to review. The audit instead checks that the audited repository has working mechanisms
(QUAL-10, AGENT-02 to AGENT-05). Reference mechanisms may come with a later work skill, such as
`coordinating-agents`, only as an opt-in part with tests, a threat model, and a documented failure
behavior, after its own decision. Costly controls are also gated by applicability, so that small or
low-risk repositories are not asked for them.

## 2026-10-17 — Lessons from the maintainer's projects

The agent-assisted development guide and the criteria added for v0.2 on incidents, ownership, fix
and flaky tests, mutation triage, processes and waits, error text, test secrets, release age,
guards, debt, and stacked commits come from lessons recorded in the maintainer's projects, where a
coordinating agent delegates to many coding agents. Those projects are private, so this repository
neither links nor quotes them; each lesson appears as a tool-independent check, explained in a
guide with public sources checked on 2026-10-17. Operations, delivery, and personal data criteria
come from the v0.2 plan's list of missing areas.

## 2026-10-16 — One audit skill; work skills separate

Skills are split by the job the agent is asked to do. `auditing-repositories` evaluates a
repository across every area, including how the repository uses agents, so one report ranks all
findings together. Skills that guide the work itself, such as coordinating agents or starting
projects, are separate skills in this repository that install independently; the first,
`coordinating-agents`, is planned for v0.3. Splitting the audit by topic was rejected because it
would duplicate the procedure, report format, scorer, and evaluations, and would produce reports
whose priorities cannot be compared.

## 2026-10-16 — Portable frontmatter only

Shipped skills use only the frontmatter fields of the
[Agent Skills specification](https://agentskills.io/specification), checked on 2026-10-16:
`name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools`. Client-specific
fields such as Claude Code's `context: fork` would make the same file behave differently across
agents and fail strict validators, so the README explains them as a local option instead.
`tools/check_skills.py` rejects any other field.

## 2026-10-16 — Origin and scope

This repository turns the engineering guidance of the maintainer's private Portfolio-OS repository
(`docs/` at commit `7c1fde9`) into installable agent skills. The guidance moved here: Portfolio-OS
stops maintaining it and will be archived once this repository is published.

- **A new public repository** instead of publishing Portfolio-OS. Its history includes a private
  email address and retired material unrelated to the skills.
- **Stack- and tool-independent skills.** Criteria state what to verify. The agent supplies
  knowledge of the audited stack, and specific tools appear only as optional examples. Skills per
  language or tool were rejected because they repeat the maintenance cost that led Portfolio-OS to
  drop its generator and per-stack templates.
- **Guides inside the skill.** The guides live in `skills/auditing-repositories/references/` so that
  an installed skill is self-contained. A second skill that needs them requires a new decision
  between a checked shared copy and another packaging method.
- **Criteria with stable IDs.** The catalog lets an audit walk every criterion and report coverage,
  and lets evaluations score reports by ID.
- **Measured detection.** Seeded evaluation cases measure coverage, recall, and false positives. The
  skill does not claim to find every problem.
- **Not migrated:** the new-project steps and README template from Portfolio-OS's quickstart, which
  belong to a future skill for starting projects. The copy-and-paste audit prompt is replaced by the
  `auditing-repositories` skill.
- **Licenses:** CC BY 4.0 for Markdown content and MIT for all other files.
