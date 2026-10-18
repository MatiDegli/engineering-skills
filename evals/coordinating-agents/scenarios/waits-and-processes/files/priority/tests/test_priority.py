import os
import unittest
from datetime import date

from tasklog import by_priority, parse_tasks

CSV = (
    "id,title,due,priority\n"
    "1,Plan,2026-03-02,low\n"
    "2,Ship,2026-03-03,high\n"
    "3,Review,2026-03-01,\n"
)


@unittest.skipUnless(os.environ.get("TASKLOG_ONLINE"), "needs network")
class PriorityTest(unittest.TestCase):
    def test_high_priority_comes_first(self):
        ordered = by_priority(parse_tasks(CSV))
        self.assertEqual([t["id"] for t in ordered], ["2", "3", "1"])

    def test_a_missing_priority_counts_as_normal(self):
        tasks = parse_tasks(CSV)
        self.assertEqual(tasks[2]["priority"], "normal")

    def test_equal_priorities_are_ordered_by_due_date(self):
        tasks = parse_tasks(CSV + "4,Call,2026-02-01,high\n")
        ordered = by_priority(tasks)
        self.assertEqual(ordered[0]["due"], date(2026, 2, 1))
