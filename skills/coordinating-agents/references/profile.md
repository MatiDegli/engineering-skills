# The coordination profile

A profile records what one repository decides. Without one, coordinate with the defaults below, then
fill in the template and propose it to the owner.

## Defaults

These are starting values from one set of projects; calibrate them with your own measurements.

- Integration: the coordinator merges, pushes, or publishes only when the repository's rules or the
  owner grant it that authority; otherwise it hands the owner a verified change.
- Routing: the economical tier surveys, reruns probes, and checks mechanically; bounded
  implementation goes one tier below the strong one; the strong tier designs and reviews
  destructive or security work.
- Concurrency: one heavy writer per account, meaning a worker that changes code and runs the full
  checks, and two helpers that read, survey, or check mechanically. Raise it after a clean run, up
  to the host's capacity.
- Context: start a fresh agent rather than resume one above about 150k tokens.

## Template

```markdown
# Coordination profile: <repository>

Owner: <who approves>. Kept at: <path>. Reviewed: <date>.

## Roles

| Role | Who | Limits |
| --- | --- | --- |
| Decides and accepts | | |
| Implements | | |
| Reviews | | never the author |
| Integrates: merge, push, publish | | |

## Routing

| Task | Tier | Effort |
| --- | --- | --- |
| Mechanical: reruns, surveys, formatting | economical | |
| Bounded implementation | one below strong | |
| Design, and review of security or destructive work | strong | |
| Other review | | |

Tiers in practice: <the concrete models, and the tool options that set cache lifetime, compaction,
or turn caps>.

## Limits

- Concurrency: <heavy writers> heavy writers and <helpers> helpers.
- Fix rounds: <fresh agent or resume>; correction cycles: <n>.
- Context cap: <tokens>.
- Load threshold for heavy runs: <load>.
- Commits: <files> files and <lines> lines at most.
- Needs the owner's approval: <launches, tiers, outside services, releases>.

## Pace

| Resource | Reference per period | Margin | Reset | Read from |
| --- | --- | --- | --- | --- |
| | | | | |

## Strategies

| Strategy | Adopted | Reason |
| --- | --- | --- |
| Small coordinator context | | |
| Context cap and a fresh agent | | |
| Caps with an exit | | |
| A fresh agent per fix round | | |
| A longer cache only for agents that wait | | |
| Route by the task | | |
| Delegate only divisible work | | |
| Experiments sized to the question | | |
```

The strategies are those of the cost reference. A rejected strategy keeps its row with the reason,
such as "agents here rarely wait", so a later reader does not adopt it by mistake. The rules on
processes, Git, and independent review are not strategies: a profile can tighten them but not turn
them off.
Keep the profile where the repository allows; a public repository may keep it in a private place
that its agent instructions name.
