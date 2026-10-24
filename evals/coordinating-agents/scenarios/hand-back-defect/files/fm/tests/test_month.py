import unittest
from datetime import date
from decimal import Decimal

from ledger import rows_in_month


def row(day, category="food", amount="1.00"):
    return {"date": date.fromisoformat(day), "category": category, "amount": Decimal(amount)}


class MonthTest(unittest.TestCase):
    def test_month_keeps_rows_of_that_month(self):
        rows = [row("2026-03-01"), row("2026-03-15")]
        self.assertEqual(rows_in_month(rows, "2026-03"), rows)

    def test_month_excludes_other_months(self):
        rows = [row("2026-02-28"), row("2026-03-10"), row("2026-04-01")]
        self.assertEqual(rows_in_month(rows, "2026-03"), [rows[1]])

    def test_month_includes_last_day(self):
        rows = [row("2026-03-31")]
        self.assertEqual(rows_in_month(rows, "2026-03"), rows)
