# Technical debt

Each front adds its follow-ups with the next free ID.

| ID | Item |
| --- | --- |
| TD-1 | `format_table` does not escape tabs in titles. |
| TD-2 | `main` reads the whole file into memory. |
| TD-3 | No test runs `main` end to end. |
| TD-4 | `parse_tasks` raises on a row without a due date. |
| TD-5 | The README does not say which exit codes `tasklog.py` returns. |
| TD-6 | `overdue` is tested with fixed dates only, never with `date.today()`. |
| TD-7 | The CSV delimiter is fixed to a comma. |
