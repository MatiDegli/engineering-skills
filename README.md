# engineering-skills

Agent skills for software engineering with coding agents: an audit of a whole repository,
coordination of several agents on shared work, and, planned, maps of large codebases. Each skill
states what to verify and why, and the agent applies its knowledge of the project's stack, in any
language or toolchain.

Every change to a skill is measured before it ships, on fictional repositories seeded with defects
and with correct code that looks wrong, and on real repositories whose findings are rated blind,
without knowing which version wrote them. [evals/RESULTS.md](evals/RESULTS.md) records more than
300 audit runs. Coordination is measured on scripted scenarios that check the state each agent
leaves.

## Skills

| Skill | For | Status |
| --- | --- | --- |
| [auditing-repositories](skills/auditing-repositories/SKILL.md) | A read-only audit of structure, quality controls, dependencies, tests, CI, security, delivery, operations, architecture, measured performance, and agent-assisted development, against a [catalog of criteria](skills/auditing-repositories/references/criteria.md) with stable IDs. It reports gaps with evidence and up to five priority actions. | Released, v0.2.3 |
| [coordinating-agents](skills/coordinating-agents/SKILL.md) | The agent that delegates: whether delegation pays, parallel tasks, briefs, checking workers' reports and fixes, shared Git state and processes, resuming from a handoff, and pacing usage against a quota or budget. A [profile](skills/coordinating-agents/references/profile.md) per repository records which cost and workflow strategies apply. | On `main`, unreleased; validation on a second model comes before v0.3.0 |
| mapping-repositories | A compact map of a large repository: its regions, modules, and architecture as claims, each with the revision where it was verified, refreshed from history. It guides navigation; the source stays the evidence. | Planned for v0.4 |

## What sets it apart

- **The whole repository.** The audit reads the code, its history, and its controls, not only a
  diff, and checks whether each control rejects a failure, not just whether it exists.
- **Evidence for every finding.** A path with lines, a value, or a command and its result. A
  high-priority finding says whether it was reproduced or inferred, and a claim that something is
  missing rests on a search of its whole scope.
- **Proportion.** Criteria apply by the project's stage, shape, and security level (0 to 3), and
  every "not applicable" gives its reason, so a prototype is not held to a production service's bar.
- **Measured against the released version.** Each candidate runs beside the current release on the
  same model, with its decision rules fixed before launch. For example, v0.2.3's parallel passes
  raised useful items per audit from 48 and 57 to 85 and 82 with Sonnet on three real repositories,
  with a similar share of false ones (runs 278 and 279).
- **Checked by what the agent does.** Coordination scenarios check the Git state, processes, and
  commands an agent leaves, not only its report. On two held-out scenarios, runs that failed a state
  check fell from 7 of 8 without the skill, and 6 of 8 with its previous version, to 0 of 8 with the
  current one, on one model (glm-5.3; round 8 in
  [evals/coordinating-agents/RESULTS.md](evals/coordinating-agents/RESULTS.md)).
- **Portable.** The skills use only the [Agent Skills format](https://agentskills.io/specification),
  ship no scripts, and name no provider. They run in Claude Code, Codex, and other agents that read
  the format.

## Install

Skills direct an agent's actions, so read a skill before installing it. Check out a specific commit
or release tag so updates are deliberate.

```bash
git clone https://github.com/MatiDegli/engineering-skills.git
```

Copy or link a skill's directory, such as `skills/auditing-repositories`, into the directory your
agent reads:

| Agent | All your repositories | One repository |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/<skill>/` | `.claude/skills/<skill>/` |
| Codex | `~/.agents/skills/<skill>/` | `.agents/skills/<skill>/` |

Other agents that support the format can load the same directory. An agent without skill support
can be asked to read `SKILL.md` and follow it.

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

The agent invokes coordinating-agents itself when you delegate to subagents or headless runs, run
several sessions or worktrees in one repository, resume work from a handoff, or check a worker's
report; you can also name it. It is for the agent that delegates and integrates, not for a worker
carrying out a brief, a reviewer checking one change, or a small change one agent can finish
directly. A repository can record its roles, model tiers, limits, and the strategies it adopts or
rejects in a profile; the skill ships a
[template](skills/coordinating-agents/references/profile.md).

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

## How the skills are measured

- [evals/](evals/README.md): fictional repositories with seeded defects and look-alikes the audit
  must not flag, a scorer for criterion coverage, missed gaps, and false positives, and blind
  ratings of audits of real repositories.
- [evals/coordinating-agents/](evals/coordinating-agents/README.md): scenarios that prepare a
  workspace, give the agent a task, and check what it reported, the state it left, and the commands
  it ran, with and without the skill. Their rounds are recorded in
  [evals/coordinating-agents/RESULTS.md](evals/coordinating-agents/RESULTS.md).
- [evals/RESULTS.md](evals/RESULTS.md): every recorded audit run with its revisions, model, and
  score, including the candidates that were dropped.

## Roadmap

- **v0.3.0:** coordinating-agents, after its validation on a second model. Releases share one
  version number; each skill keeps its own section in the [changelog](CHANGELOG.md).
- **The next audit release:** helpers that start in every repository, and a final check of each
  problem against the project's stage and scope that sets aside what cannot matter to it. Both are
  being measured now.
- **v0.4:** mapping-repositories, measured against the cheap alternative every agent already has, a
  notes file of the same size. It is not meant for a small repository, a one-off question, or a
  repository that already maintains a description of its architecture.

## Limits of the audit

- The audit does not modify the repository, install dependencies, or run commands with external
  effects. Criteria it cannot verify are reported as pending verification.
- It does not prove scalability or performance. Capacity counts only with measurements; when they
  are missing, the audit says what to measure.
- It does not replace security review, secret scanning, or tests. It checks whether they exist and
  whether they reject failures.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), the [security policy](SECURITY.md), the
[decision record](docs/decisions.md), and the [agentic workflow lessons](docs/agentic-workflow.md)
learned while building this repository with coding agents.

## License

Markdown files, including the skills and their references, are licensed under
[CC BY 4.0](LICENSE-CONTENT). All other files are licensed under the [MIT License](LICENSE).
