# Audit evaluations

Each case under `cases/` is a small fictional repository with seeded defects. `expected.json` lists
the criteria an audit must report as findings (`must_find`) and the criteria it must not report as
findings because they hold or do not apply (`must_not_flag`). The values explain each choice.

The cases measure three things: coverage of every criterion ID, recall of seeded gaps, and false
positives. They do not prove that an audit finds every problem in a real repository.

## Running a case

From the repository root, in WSL2 or Linux:

```bash
python3 -m tools.evals prepare python-service /tmp/audit-python-service
```

Start an agent in the prepared directory with the `auditing-repositories` skill installed and ask:
"Audit this repository." Save its final report outside the prepared directory, then score it:

```bash
python3 -m tools.evals score /tmp/report-python-service.md python-service
```

The command exits with 1 when a seeded gap is missed, a criterion is falsely flagged, an ID is missing
or repeated, the report uses an unknown ID or status, or a high finding's evidence is not marked as
reproduced or inferred. It also exits with 1 when the report contains a string listed in
`must_not_contain`, such as a seeded secret, or cites a line outside a case file. Run
`python3 -m tools.evals check <report> <case>` for these last two checks on a report without IDs.
Both commands also list citations whose quoted code sits on other lines of the cited file; that
list is a pointer for review and does not change the exit code.

After an audit, `python3 -m tools.evals verify <case> <destination>` checks that the prepared
repository is unchanged: the same revision as a fresh preparation, and no modified, untracked, or
ignored files.

`top_priorities` lists, in order, the gaps a reviewer should act on first, and `max_high` caps the
high findings a case justifies. The maintainer fixes both before reading any report. The scorer
prints which priority action names each top priority and how many high findings fall outside them;
these lines compare reports and do not change the exit code.

Cases contain intentional defects. Do not fix them, deploy them, or run their code outside a
disposable environment; some tests call external hosts.

## Recording results

Add each run to [RESULTS.md](RESULTS.md): date, revision of this repository, agent and model, case,
score output, and notes. Run every case after changing the skill, the criteria, or a case, and
compare with the previous results. Results from one agent or model do not transfer to another.

## Baselines

Runs with the skill show what an agent finds with it, not what the skill adds. A baseline runs the
same cases, model, and harness with less of the skill:

| Level | The agent receives | Scoring |
| --- | --- | --- |
| No skill | A request to audit the repository, list its problems with evidence, and give up to five priority actions | By hand |
| Catalog only | `criteria.md` and the report's Findings, Priority actions, and Coverage format, without the procedure or the guides | `score` |
| Full skill | The skill | `score` |

Start every agent in the prepared repository, where it cannot reach this repository, the skill, or
`expected.json` unless its level provides them, and check its tool calls afterwards.

A report without the skill has no criterion IDs, so score it by hand against `expected.json` with
these rules, fixed before reading any report:

- A seeded gap is found when the report names the same defect: the same mechanism at the same
  location or, for a missing control, the same missing control. A broader statement that would also
  cover it, such as "CI is weak", does not count.
- A false flag is a claim that contradicts the reason given for a `must_not_flag` entry.
- A priority action places a top priority when it names that gap's defect by the same rule.
- Record, for each seeded gap, the report text that matched it or "missed", so that someone else
  can review the scoring.

The full skill is judged better than the catalog alone, by criteria the maintainer approved on
2026-10-17 before the comparison, when over both runs of every case it:

- places the top priorities in its first five actions at least as often;
- contains no `must_not_contain` string;
- marks fewer high findings outside the top priorities;
- covers every ID at least as completely;
- has no more citations outside a case file;
- and is the maintainer's choice in a blind comparison of reports.
