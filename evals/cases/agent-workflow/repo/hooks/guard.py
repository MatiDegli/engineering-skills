"""Reject destructive shell commands before an agent runs them."""

import re
import sys

BLOCKED = (
    r"\brm\s+-rf\s+/(\s|$)",
    r"\bgit\s+push\s+(-f|--force)\b",
    r"\bgit\s+reset\s+--hard\b",
)


def blocked(command: str) -> bool:
    return any(re.search(pattern, command) for pattern in BLOCKED)


if __name__ == "__main__":
    command = " ".join(sys.argv[1:])
    if blocked(command):
        print(f"guard: blocked: {command}", file=sys.stderr)
        raise SystemExit(2)
