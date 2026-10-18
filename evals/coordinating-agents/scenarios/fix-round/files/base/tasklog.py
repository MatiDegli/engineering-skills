"""List tasks from a CSV file and flag the overdue ones."""

import csv
import sys
from datetime import date


def parse_tasks(text):
    """Return one dict per CSV row with id, title, and due date."""
    rows = csv.DictReader(text.splitlines())
    return [
        {"id": row["id"], "title": row["title"], "due": date.fromisoformat(row["due"])}
        for row in rows
    ]


def overdue(tasks, today):
    """Return the tasks whose due date has passed."""
    return [task for task in tasks if task["due"] <= today]


def format_table(tasks):
    """Return the task table as lines: id, title, and due date."""
    lines = ["id\ttitle\tdue"]
    lines += [f"{t['id']}\t{t['title']}\t{t['due'].isoformat()}" for t in tasks]
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    with open(argv[0], encoding="utf-8") as handle:
        tasks = parse_tasks(handle.read())
    if "--overdue" in argv:
        tasks = overdue(tasks, date.today())
    print("\n".join(format_table(tasks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
