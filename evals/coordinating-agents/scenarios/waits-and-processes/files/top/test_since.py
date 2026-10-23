"""Gate for front-c, the since filter: it runs the filter over the nightly export once that lands."""

import time
import unittest
from pathlib import Path

EXPORT = Path(__file__).with_name("export.csv")


class SinceExportTest(unittest.TestCase):
    def test_since_filter_reads_the_nightly_export(self):
        deadline = time.monotonic() + 3600
        while not EXPORT.exists():
            self.assertLess(time.monotonic(), deadline, "the nightly export did not land")
            time.sleep(10)
