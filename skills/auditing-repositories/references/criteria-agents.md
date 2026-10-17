# Agent-assisted development criteria

Apply these criteria when agents contribute to the repository; see the
[areas table](criteria.md#areas). Otherwise close the area in Coverage with
`AGENT-* (no agents contribute)`.

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| AGENT-01 | Agents use the same checks as developers, respect authorization limits, and their claims are verified against executed results | Agents contribute | [quality](quality.md#rules-for-changes-and-agents) |
| AGENT-02 | Delegated tasks have a bounded brief: base revision, binding decisions, allowed paths, reserved identifiers, verification, and report format | Agents receive delegated tasks | [agents](agents.md#briefs) |
| AGENT-03 | Changes to security, authority, lifecycle, or gates get an independent review that reproduces its findings, and fixes are verified on the new revision rather than taken from reports | Agents implement changes | [agents](agents.md#review-and-verification) |
| AGENT-04 | Concurrent agents work in isolation: one writer per worktree, no shared Git state such as the stash, partitioned scratch space, ports, and locks, and work closed out at merge | Several agents work at once | [agents](agents.md#isolation) |
| AGENT-05 | Concurrent work is bounded by host capacity, shared resources go through one scheduler, and a state record shows each task's status and next owner | Several agents work at once | [agents](agents.md#capacity-and-state) |
