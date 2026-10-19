"""Command line: python -m pluginhost [--config FILE] list [--json] | run NAME."""

import argparse
import json
import sys
from pathlib import Path

from pluginhost import hooks
from pluginhost.loader import PluginError, discover
from pluginhost.settings import read


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pluginhost")
    parser.add_argument("--config", type=Path, default=Path("pluginhost.toml"))
    commands = parser.add_subparsers(dest="command", required=True)
    list_command = commands.add_parser("list", help="print the plugins found")
    list_command.add_argument("--json", action="store_true", help="print a JSON array")
    run_command = commands.add_parser("run", help="run one plugin")
    run_command.add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
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
    context: dict = {}
    try:
        hooks.run_before(arguments.config, plugins, context)
        result = plugins[arguments.name].run(context)
    except PluginError as error:
        print(f"pluginhost: {error}", file=sys.stderr)
        return 1
    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
