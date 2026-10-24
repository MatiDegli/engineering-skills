"""Sum expenses from a CSV file by category."""

import argparse
import calendar
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


def rows_in_month(rows, month):
    """Return the rows dated in a month, given as YYYY-MM."""
    y, m = (int(part) for part in month.split("-"))
    first = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])
    return [row for row in rows if first <= row["date"] < last]


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
    parser.add_argument("--month", help="only the rows of this month, as YYYY-MM")
    args = parser.parse_args(argv)
    rows = parse_rows(args.path)
    if args.month:
        rows = rows_in_month(rows, args.month)
    print("\n".join(format_report(totals_by_category(rows))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
