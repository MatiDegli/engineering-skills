"""The since filter over the nightly export, which the export job writes late."""

import time
import unittest
from pathlib import Path

EXPORT = Path(__file__).with_name("export.csv")
POLL_SECONDS = 30
POLLS = 180


class SinceExportTest(unittest.TestCase):
    def test_since_filter_reads_the_nightly_export(self):
        for _ in range(POLLS):
            if EXPORT.exists():
                break
            time.sleep(POLL_SECONDS)
        else:
            self.fail("the nightly export did not land")
        self.assertEqual(EXPORT.read_text().splitlines()[0], "id,title,due")
