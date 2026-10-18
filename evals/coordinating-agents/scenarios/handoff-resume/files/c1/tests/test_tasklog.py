import unittest
from datetime import date

from tasklog import format_table, parse_tasks

CSV = "id,title,due\n1,Write report,2026-03-01\n2,Pay invoice,2026-03-10\n"


class ParseTest(unittest.TestCase):
    def test_reads_every_row(self):
        tasks = parse_tasks(CSV)
        self.assertEqual([t["id"] for t in tasks], ["1", "2"])
        self.assertEqual(tasks[0]["due"], date(2026, 3, 1))


class FormatTest(unittest.TestCase):
    def test_table_has_header_and_rows(self):
        lines = format_table(parse_tasks(CSV))
        self.assertEqual(lines[0], "id\ttitle\tdue")
        self.assertEqual(lines[1], "1\tWrite report\t2026-03-01")
