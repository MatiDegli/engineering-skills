# Review of front F

Review agent R1, context 210k, finished {{now-150m}}.

Reviewed: `front-f` at `{{short:repo:front-f~3}}`. Verdict: changes required.

## Findings

- BLOCKING-1: `overdue()` raises on a row with an empty due date. Probe:

  ```sh
  printf 'id,title,due\n1,x,\n' > t.csv; python3 tasklog.py t.csv --overdue
  ```

- SF-1: No test covers a row with an empty due date.
- NIT-1: The docstring of `overdue()` does not say how rows without a due date are treated.
