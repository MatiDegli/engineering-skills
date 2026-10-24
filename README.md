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

An audit reads several thousand words of guidance into the conversation: in the evaluation round for
v0.2.0, each Opus audit opened 5,700 to 8,700 of the skill's 11,800 words (runs 87 and 90 in
[evals/RESULTS.md](evals/RESULTS.md)). In Claude Code, you can keep it out of the main context by
asking Claude to run the audit in a subagent, or by adding `context: fork` to your installed copy.
That field is specific to Claude Code and outside the Agent Skills specification, so this repository
does not ship it.

## When a skill loads

An installed skill does not act on its own: the agent keeps each skill's name and description in
context, about a hundred tokens, and reads the rest only when it invokes the skill. Two kinds of
skill are best installed differently:

- A task skill does one job when asked and ends with a result: auditing-repositories writes a
  report. Keep it installed for the next audit; nothing needs removing after one.
- A reference skill guides ongoing work, such as coordinating-agents while you delegate. Leave it
  free for the agent to invoke whenever the work matches its description.

A task skill's description can still match a request it was not written for, such as a review of
one change. To run it only when you name it, or to turn it off without deleting it, set one of these
in your installed copy or your local settings:

| Agent | Only when named | Off |
| --- | --- | --- |
| Claude Code | `disable-model-invocation: true` in `SKILL.md`, or `"user-invocable-only"` for the skill in `skillOverrides` (the `/skills` menu writes it) | `"off"` in `skillOverrides` |
| Codex | `allow_implicit_invocation: false` under `policy` in `agents/openai.yaml` | `enabled = false` in a `[[skills.config]]` entry of `~/.codex/config.toml` |

Each of these belongs to one agent and is outside the Agent Skills specification, so this repository
ships none of them. In Claude Code, `/skill-doctor` reports each skill's context cost and how often
it is used.

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

See [CONTRIBUTING.md](CONTRIBUTING.md), the [security policy](SECURITY.md), the
[decision record](docs/decisions.md), and the [agentic workflow lessons](docs/agentic-workflow.md)
learned while building this repository with coding agents.

## License

Markdown files, including the skills and their references, are licensed under
[CC BY 4.0](LICENSE-CONTENT). All other files are licensed under the [MIT License](LICENSE).
