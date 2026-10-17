"""Command line: python3 -m notesync index OUTPUT DIRECTORY..."""

import json
import sys
from pathlib import Path

from notesync.core import build_index, index_directories


def main(argv: list[str]) -> int:
    if argv[:1] == ["worker"] and len(argv) >= 2:
        print(json.dumps(build_index(Path(argv[1]))))
        return 0
    if argv[:1] == ["index"] and len(argv) >= 3:
        index_directories([Path(argument) for argument in argv[2:]], Path(argv[1]))
        return 0
    print("usage: python3 -m notesync index OUTPUT DIRECTORY...", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
