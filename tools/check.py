#!/usr/bin/env python3
"""Check documentation and its maintenance tools from any working directory."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    print("Documentation checks and maintenance-tool tests:", flush=True)
    for command in (
        [sys.executable, "tools/validate_repo.py"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    ):
        result = subprocess.run(command, cwd=ROOT, timeout=300)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
