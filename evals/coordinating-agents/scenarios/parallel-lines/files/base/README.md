# tasklog

Lists tasks from a CSV file with `id`, `title`, and `due` columns, and flags the overdue ones.

```sh
python3 tasklog.py tasks.csv
python3 tasklog.py tasks.csv --overdue
```

The output is a tab-separated table. Run the tests from this directory with
`python3 -m unittest`. The usage is in `docs/usage.md`. Released versions are listed in
`CHANGELOG.md` with their date.
