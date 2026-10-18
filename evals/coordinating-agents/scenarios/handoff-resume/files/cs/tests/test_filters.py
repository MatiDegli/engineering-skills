import unittest
from datetime import date

from filters import since
from tasklog import parse_tasks

CSV = "id,title,due\n1,Write report,2026-03-01\n2,Pay invoice,2026-03-10\n"


class SinceTest(unittest.TestCase):
    def test_keeps_tasks_due_from_the_start_date(self):
        tasks = parse_tasks(CSV)
        self.assertEqual([t["id"] for t in since(tasks, date(2026, 3, 1))], ["1", "2"])
        self.assertEqual([t["id"] for t in since(tasks, date(2026, 3, 2))], ["2"])
