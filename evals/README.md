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
or repeated, or the report uses an unknown ID or status.

Cases contain intentional defects. Do not fix them, deploy them, or run their code outside a
disposable environment; some tests call external hosts.

## Recording results

Add each run to [RESULTS.md](RESULTS.md): date, revision of this repository, agent and model, case,
score output, and notes. Run every case after changing the skill, the criteria, or a case, and
compare with the previous results. Results from one agent or model do not transfer to another.
