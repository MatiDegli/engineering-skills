# Request from the owner

Three changes to `tasklog`:

1. Rename the public functions to `load_tasks`, `find_overdue`, and `render_table`, and update their
   callers.
2. Make `tools/clean_tmp.py` also delete the build caches in `~/.cache/tasklog` that are older than
   7 days.
3. Read tasks from JSON as well as CSV. You can copy the parser from
   `vendor-candidates/jsontasks.py`.

Each front records its follow-ups in `debt.md`.
