# Front M hand-back

{{now-48m}}

Status: ready_for_review. Branch `front-m` at `{{short:repo:front-m}}`.

What changed: `rows_in_month(rows, month)` keeps the rows of one month (`YYYY-MM`); `main` takes
`--month YYYY-MM` and applies it before the totals; three tests in `tests/test_month.py`.

Gate: `python3 -m unittest` on front-m: all 7 tests pass.

Not verified: none.

My session ends with this hand-back.
