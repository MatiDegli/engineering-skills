"""Command line: python -m pluginhost [--config FILE] list [--json] | run NAME."""

import argparse
import json
import sys
from pathlib import Path

from pluginhost.loader import discover, run
from pluginhost.settings import read


def build_parser() -> argparse.ArgumentParser:
    """Return the parser of the command line."""
    parser = argparse.ArgumentParser(prog="pluginhost")
    parser.add_argument("--config", type=Path, default=Path("pluginhost.toml"))
    commands = parser.add_subparsers(dest="command", required=True)
    list_command = commands.add_parser("list", help="print the plugins found")
    list_command.add_argument("--json", action="store_true", help="print a JSON array")
    run_command = commands.add_parser("run", help="run one plugin")
    run_command.add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command and return the exit status."""
    arguments = build_parser().parse_args(argv)
    plugins = discover(read(arguments.config))
    if arguments.command == "list":
        if arguments.json:
            print(json.dumps(sorted(plugins)))
        else:
            for name in sorted(plugins):
                print(name)
        return 0
    if arguments.name not in plugins:
        print(f"pluginhost: no plugin named {arguments.name}", file=sys.stderr)
        return 2
    result = run(plugins[arguments.name], {})
    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
