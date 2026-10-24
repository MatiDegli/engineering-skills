import unittest
from decimal import Decimal

from ledger import format_report


class CurrencyTest(unittest.TestCase):
    def test_report_shows_the_currency_only_when_asked(self):
        totals = {"food": Decimal("12.50")}
        self.assertEqual(format_report(totals, currency="EUR"), ["category\ttotal", "food\t12.50 EUR"])
        self.assertEqual(format_report(totals), ["category\ttotal", "food\t12.50"])
