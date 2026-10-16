# Decisions

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
