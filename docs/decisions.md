# Decisions

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
