import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledger import format_report, parse_rows, totals_by_category

DATA = Path(__file__).parent / "data" / "expenses.csv"


class ParseTest(unittest.TestCase):
    def test_reads_every_row(self):
        rows = parse_rows(DATA)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0], {"date": date(2026, 3, 1), "category": "food", "amount": Decimal("12.50")})

    def test_a_file_with_only_a_header_has_no_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_text("date,category,amount\n", encoding="utf-8")
            self.assertEqual(parse_rows(path), [])


class TotalsTest(unittest.TestCase):
    def test_sums_each_category(self):
        totals = totals_by_category(parse_rows(DATA))
        self.assertEqual(totals, {"food": Decimal("23.85"), "rent": Decimal("900.00")})


class ReportTest(unittest.TestCase):
    def test_report_has_a_header_and_sorted_rows(self):
        lines = format_report({"rent": Decimal("900.00"), "food": Decimal("23.85")})
        self.assertEqual(lines, ["category\ttotal", "food\t23.85", "rent\t900.00"])
