# Decisions

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
