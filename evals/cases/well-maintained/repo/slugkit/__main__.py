"""Command-line entry point: python -m slugkit TITLE."""

import argparse
import sys

from slugkit.core import slugify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slugkit", description="Print the slug for a title.")
    parser.add_argument("title")
    arguments = parser.parse_args(argv)
    try:
        print(slugify(arguments.title))
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
