# Changelog

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
  full skill to the catalog, but ranked the report written without any skill first. It found two
  real logic defects that the case does not seed and that every skill report missed. Finding such
  defects is the first goal after this release.

Evaluated with small fictional cases and one large private repository, mostly with Claude models.

## v0.1.0 — 2026-10-16

First public release of engineering-skills.

- auditing-repositories: a read-only audit procedure, 69 criteria with stable IDs, and eight
  engineering guides, for any language or toolchain.
- Repository checks for links, skill metadata, criterion IDs, workflows, and external links.
- Seeded evaluation cases and a scorer. Run 2 found every seeded gap with no false flags and full
  criterion coverage (`evals/RESULTS.md`).

Limits: evaluated on three small fictional cases with one model.
