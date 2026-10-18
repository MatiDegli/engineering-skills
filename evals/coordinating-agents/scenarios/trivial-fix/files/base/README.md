# tasklog

Lists tasks from a CSV file with `id`, `title`, and `due` columns, and flags the overdue ones.

```sh
python3 tasklog.py tasks.csv
python3 tasklog.py tasks.csv --overdue
```

Each task needs a due date; rows without one recieve an error.

The output is a tab-separated table. Run the tests from this directory with
`python3 -m unittest`.
