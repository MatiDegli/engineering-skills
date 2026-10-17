# engineering-skills

Agent skills that review software repositories against evidence-based engineering criteria. They
work with any language, framework, or toolchain: each skill states what to verify and why, and the
agent applies its knowledge of the project's stack.

## Skills

| Skill | What it does |
| --- | --- |
| [auditing-repositories](skills/auditing-repositories/SKILL.md) | Read-only audit of structure, quality controls, dependencies, tests, CI, security, delivery, operations, architecture, measured performance, and agent-assisted development against a [catalog of criteria](skills/auditing-repositories/references/criteria.md) with stable IDs |

## Install

Skills direct an agent's actions, so read a skill before installing it. Check out a specific commit
or release tag so updates are deliberate.

```bash
git clone https://github.com/MatiDegli/engineering-skills.git
```

Copy or link `skills/auditing-repositories` into the directory your agent reads:

| Agent | All your repositories | One repository |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/auditing-repositories/` | `.claude/skills/auditing-repositories/` |
| Codex | `~/.agents/skills/auditing-repositories/` | `.agents/skills/auditing-repositories/` |

Other agents that support the [Agent Skills format](https://agentskills.io/specification) can load
the same directory. An agent without skill support can be asked to read `SKILL.md` and follow it.

## Use

From the repository to review, ask the agent: "Audit this repository." In Claude Code, you can also
run `/auditing-repositories`.

The report gives the project's context, its strengths, findings by criterion ID with evidence and
priority, up to five priority actions, the status of every criterion, and the audit's limitations.

An audit can read about 10,000 tokens of guidance into the conversation. In Claude Code, you can
keep it out of the main context by asking Claude to run the audit in a subagent, or by adding
`context: fork` to your installed copy. That field is specific to Claude Code and outside the Agent
Skills specification, so this repository does not ship it.

## Limits

- The audit does not modify the repository, install dependencies, or run commands with external
  effects. Criteria it cannot verify are reported as pending verification.
- It does not prove scalability or performance. Capacity counts only with measurements; when they
  are missing, the audit says what to measure.
- It does not replace security review, secret scanning, or tests. It checks whether they exist and
  whether they reject failures.

## Measuring the skill

[evals/](evals/README.md) contains fictional repositories with seeded defects and a scorer for
criterion coverage, missed gaps, and false positives. Recorded runs are in
[evals/RESULTS.md](evals/RESULTS.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), the [security policy](SECURITY.md), and the
[decision record](docs/decisions.md).

## License

Markdown files, including the skills and their references, are licensed under
[CC BY 4.0](LICENSE-CONTENT). All other files are licensed under the [MIT License](LICENSE).
