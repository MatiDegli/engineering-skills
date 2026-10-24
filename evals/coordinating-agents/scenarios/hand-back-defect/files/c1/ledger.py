"""Sum expenses from a CSV file by category."""

import argparse
import csv
import sys
from datetime import date
from decimal import Decimal


def parse_rows(path):
    """Return one dict per CSV row with its date, category, and amount."""
    with open(path, encoding="utf-8", newline="") as handle:
        return [
            {
                "date": date.fromisoformat(row["date"]),
                "category": row["category"],
                "amount": Decimal(row["amount"]),
            }
            for row in csv.DictReader(handle)
        ]


def totals_by_category(rows):
    """Return the total amount of each category."""
    totals = {}
    for row in rows:
        totals[row["category"]] = totals.get(row["category"], Decimal("0.00")) + row["amount"]
    return totals


def format_report(totals):
    """Return the report as lines: a header, then one line per category, sorted."""
    lines = ["category\ttotal"]
    lines += [f"{category}\t{total}" for category, total in sorted(totals.items())]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sum expenses by category.")
    parser.add_argument("path", help="CSV file with date, category, and amount")
    args = parser.parse_args(argv)
    rows = parse_rows(args.path)
    print("\n".join(format_report(totals_by_category(rows))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
