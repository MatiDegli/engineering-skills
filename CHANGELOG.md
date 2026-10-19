# Changelog

## Unreleased

### auditing-repositories

- Step 2 records the project's shape: its maintainers, whether its software reaches anyone beyond
  the machines that build it, and whether it is a library. With one maintainer, owners and
  approvals (REPO-08, HIST-02) do not apply. Dependency policies (DEP-02, DEP-03, DEP-04, DEP-06)
  apply only to dependencies that reach users, and the Delivery area only to artifacts that reach
  anyone. A library's DEP-01 asks only for the lockfile of its development environment. With
  Sonnet on three real repositories, rows that the project's shape makes moot fell from 20 to 2 in
  six reports, and reports had 12% fewer rows (runs 190 to 195 in `evals/RESULTS.md`).
- Costly and structural criteria apply in proportion. TEST-09 asks for mutation testing only once
  the tests run automatically. QUAL-02's rejection of violations is a check the audit makes, not a
  record the project keeps. STRUCT-02's file count leaves out generated files and data. STRUCT-03
  applies with several maintainers, a documented boundary, or a dependency cycle. The Delivery area
  applies only when artifacts reach anyone. With Sonnet on three real repositories, the rows these
  rules had raised without cause fell from 8 to 2 in six reports, and a rewording removed the last
  2 (runs 196 to 203 in `evals/RESULTS.md`).
- A migration from one pattern to another names its completion condition, and a check rejects new
  uses of the pattern it replaces (QUAL-11), so new code cannot copy the pattern being retired. A
  committed baseline of known violations meets QUAL-05 when it cannot grow without a separate
  reviewed change, as large-scale changes and frozen architecture rules use it. With Sonnet, audits
  found a seeded unfinished migration in 10 of 10 reports against 4 of 10 before (runs 204 to 213
  and 231 to 240).
- Release flags and compatibility shims are temporary code under STRUCT-04: each has a purpose, an
  owner, and a removal condition, goes once that is met, and is tested in each state it can ship in
  until then. Permanent operational and permission toggles are configuration. With Sonnet, audits
  found a flag past its rollout in 10 of 10 reports against 0 of 10 before. Known limit: a flag with
  an owner, a future expiry date, and tests in both states still got a `low` partial asking for a
  check that fails once the date passes, in 10 of 10 reports.
- Past 0.y.z, the version of a library, CLI, or public API signals incompatible changes, and a
  removal follows a deprecation in an earlier release (DEL-03), as Semantic Versioning asks. The
  audit compares the declared interface between the last two releases; internal applications and
  0.y.z versions are exempt. With Sonnet, a 0.y.z package that removed an option with a changelog
  note was flagged in 1 of 10 reports against 8 of 10 before, for its release approval, not its
  version.
- Untrusted event data, such as a pull request's or an issue's title, never reaches a CI script
  through expression interpolation, where it can run as code with the job's token (CI-10). CI-10
  now also applies to CI that outside events trigger, not only to CI with secrets or publication.
  Audits had found the seeded case before this change too (runs 204 to 213).
- The behavior step reads code that measures something, such as experiments, evaluations,
  benchmarks, and model training, against the results it reports: each number comes from the
  configuration and data it names, compared runs and variants differ only in what is under test,
  the sample can detect the differences the decision rules act on, evaluated code cannot read
  held-out answers, and synthetic data covers the real cases. On a new research case, Sonnet found
  all six seeded defects in every report with the skill, with the previous skill, and without any
  skill (runs 214 to 228), so the case shows no effect yet; re-auditing the trial repositories
  where audits missed such defects is the test that remains.

### Evaluations and tooling

- Three cases: `plugin-host`, a published library that seeds an unfinished migration, a release flag
  past its rollout, a minor release that removes an option, and an issue title interpolated into
  a CI script; `plugin-host-guarded`, its sibling that does the same four practices right; and
  `review-classifier`, a research repository whose evaluation seeds six logic defects.
- `tools/claude_rounds.py` takes one round lock per provider instead of one per machine, so rounds
  on different providers, such as Claude and GLM, run at once, and rounds on one provider still run
  one at a time. A round takes all its locks or none, and checks the Claude login only when it uses
  it. Its log records the other rounds' locks at its start and end, and its summary marks a round
  that overlapped another, whose minutes are then not comparable.
- Every `claude` the round runner starts has automatic updates off, so a round that runs beside
  another cannot have its CLI updated midway, which would split its audits across two versions.
- An expert-prompt level, `+expert`, runs audits with a prompt for a repository audit that a model
  wrote without tools, context, or the catalog, so rounds can tell what the skill adds beyond a good
  prompt as well as beyond a bare request.
- A real-repository case can keep the source's branches no newer than its pin (`"branches": true`
  in `source.json`) and get a snapshot of its GitHub state (`"github": "owner/name"`): the CI runs
  and checks on the pinned commit and the default branch's protection and rules, read once with
  `gh api` when the round is planned and placed beside each prepared repository, with a sentence in
  every level's prompt that names it. Audits of real repositories could not read these before (runs
  188 and 189). Cases without the keys are prepared and prompted as before.
- A case prepared from a source repository keeps the tags the pin already had: those on the pin's
  history, or on a kept branch's, dated no later than the pin, a lightweight tag by its commit's
  date. Audits of real repositories could not compare releases by tag before. A case with seeds
  keeps none, and `verify` reports a tag that was added, removed, or moved.

## v0.2.1 — 2026-10-18

### auditing-repositories

- Logic defects: a business rule that callers can bypass, or that charges, grants, or books
  wrongly, is rated `high`, and the behavior step checks that configuration such as alert
  thresholds, limits, timeouts, retries, and schedules means what its names, units, and
  descriptions say. With Opus, audits found 15 of 16 seeded logic defects against 10 before, 13
  without the skill, and 13 with the catalog alone (runs 149 to 156 in `evals/RESULTS.md`).
- `criteria.md` and `quality.md`, the two guides longer than 100 lines, start with a table of
  contents, as Anthropic's skill authoring guide recommends, so a partial read still shows every
  section.
- A finding that holds only under a condition, such as a setting, a log level, an environment
  variable, or a deployment option, states the condition and whether the repository shows that it
  is met, and software already in production or distributed gets no "before release" timing. With
  Sonnet, no production-case report used that timing, against 4 of 10 before (runs 157 to 176).
- Unverified recovery of production data, such as backups that nothing shows to exist or to have
  been restored, is `high`. With Sonnet, reports rated it high and acted on it among the first five
  actions in 10 of 10, against 1 of 10 before (runs 157 to 176).
- A `high` finding's evidence starts with exactly `Reproduced:` or `Inferred:`, and anything that
  qualifies it follows the colon. With the condition rule above, Opus had written marks such as
  `Inferred (pytest not runnable):` (runs 177 to 184).

### Evaluations and tooling

- Cases can list logic defects that a findings row must pin by criterion, location, and wording.
  A new `booking-api` case breaks five rules its README states, and `orders-service` lists three
  defects found after v0.2.0.
- `tools/claude_rounds.py` runs one round at a time on a machine.
- The scorer matches a numeric defect term only as a whole number, so `500` no longer matches inside
  `5000`, and ignores parentheses inside code in Coverage reasons, which had hidden the IDs after
  them.
- Against v0.2.0 with Opus (runs 177 to 187), this release found 28 of 32 logic defects against 22,
  rated unverified backups high and among the first five actions in 8 of 8 reports against 5,
  and kept seeded gaps, secrets, top priorities, and cost.

### Documentation

- `docs/agentic-workflow.md` records what building this repository with coding agents has
  taught, each lesson with its incident and the mechanism that enforces it or its follow-up.

## v0.2.0 — 2026-10-18

### auditing-repositories

- 87 criteria, up from 69. New checks cover agent-assisted development, delivery, operations,
  personal data, incidents and ownership, fix and flaky tests, mutation triage, bounded waits and
  processes, error text as data, test secrets, dependency release age, guard failure modes, and
  stacked commits. A new guide, `agents.md`, explains the agent-assisted development checks.
- Criteria load by area: agent-assisted development (`AGENT-*`), delivery (`DEL-*`), and operations
  (`OPS-*`) live in their own files, read only when the area applies, and close in Coverage with a
  wildcard otherwise.
- The procedure checks the integration path and real distribution first, reads code behavior and
  narrows reproduced findings, requires one ID per entry and IDs in priority actions, masks
  secret-like values even when they look fake, and leaves the audited repository's ignored files
  unchanged.
- Evidence rules: an absence claim comes from a search, a count names its command, and cited line
  numbers come from output that shows them, numbered per file.
- Deeper checks: up to three one-line entries for `high` findings whose unverified premise could
  change them, offered to the user instead of exploring every premise.

### Evaluations and tooling

- Six seeded cases, up from three, including a service in production and a repository developed
  with agents. The scorer fails reports that copy a secret or cite missing lines, points out
  citations whose quoted code is elsewhere, shows where each case's top priorities land, and
  verifies that audits leave the prepared repository unchanged.
- `tools/claude_rounds.py` runs headless rounds with Claude Code: control and candidate arms in the
  same round, skill levels, a cost cap, models from other providers, and a stop that ends every
  running audit. `tools/claude_ledger.py` shows where tokens go by kind.
- Cases can be prepared from a pinned repository with seeds folded into its history; the large
  case built this way stays private.
- `tools/check_range.py` checks every commit of a range on its own tree, and
  `tools/check_secrets.sh` scans every commit for secrets before each push.

### Results and known limits

In the release comparison (runs 87 to 92 in `evals/RESULTS.md`), Opus 5.5 with the full skill found
100 of 100 seeded gaps, passed the scorer in 12 of 12 reports, copied no secret, and marked 19 high
findings outside the top priorities against 77 with the catalog alone. It met five of the six
criteria approved before the comparison:

- It placed 26 of 28 top priorities in its first five actions, against 28 with the catalog. Both
  misses are the unverified backups of `orders-service`, rated medium. The maintainer released with
  this exception recorded in `docs/decisions.md`.
- In a blind comparison of `orders-service` reports, the reviewer and the maintainer preferred the
  full skill to the catalog, but ranked the report written without any skill first, for logic
  defects that the case does not seed. Across both runs of each level, the reports without the skill
  found a CPU alert's unit error that every skill report missed, and a discount that trusts the
  caller's flag, which each skill level found in one of two runs and rated medium. Finding and
  ranking such defects is the first goal after this release. (Corrected after the release: the
  first count said every skill report missed both defects.)

Evaluated with small fictional cases and one large private repository, mostly with Claude models.

## v0.1.0 — 2026-10-16

First public release of engineering-skills.

- auditing-repositories: a read-only audit procedure, 69 criteria with stable IDs, and eight
  engineering guides, for any language or toolchain.
- Repository checks for links, skill metadata, criterion IDs, workflows, and external links.
- Seeded evaluation cases and a scorer. Run 2 found every seeded gap with no false flags and full
  criterion coverage (`evals/RESULTS.md`).

Limits: evaluated on three small fictional cases with one model.
