import contextlib
import io
import unittest
from pathlib import Path

from ledger import main

DATA = Path(__file__).parent / "data"


class SeveralFilesTest(unittest.TestCase):
    def test_main_sums_every_file_given(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main([str(DATA / "expenses.csv"), str(DATA / "more.csv")])
        self.assertEqual(
            output.getvalue().splitlines(),
            ["category\ttotal", "food\t28.85", "rent\t900.00", "transport\t2.40"],
        )
