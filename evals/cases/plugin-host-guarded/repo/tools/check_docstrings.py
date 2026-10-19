#!/usr/bin/env python3
"""Fail when a public function, method, or class has no docstring and is not in the baseline.

The baseline, tools/docstring-baseline.json, lists the violations that predate the rule. It can
only shrink: a new violation fails, and so does a listed symbol that now has a docstring.
"""

import ast
import json
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def undocumented(node: ast.AST, prefix: str = "") -> Iterator[str]:
    """Yield the qualified names of the public definitions under `node` that lack a docstring."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, DEFINITIONS):
            name = prefix + child.name
            if not child.name.startswith("_") and ast.get_docstring(child) is None:
                yield name
            if isinstance(child, ast.ClassDef):
                yield from undocumented(child, name + ".")


def violations(root: Path) -> set[str]:
    """Return `path::symbol` for every violation in the package under `root`."""
    found = set()
    for path in sorted((root / "pluginhost").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found.update(f"{relative}::{symbol}" for symbol in undocumented(tree))
    return found


def check(root: Path, baseline: dict[str, list[str]]) -> list[str]:
    """Return what is wrong: new violations, and baseline entries that no longer apply."""
    known = {f"{path}::{symbol}" for path, symbols in baseline.items() for symbol in symbols}
    current = violations(root)
    return [f"new violation: {item}" for item in sorted(current - known)] + [
        f"fixed, delete it from the baseline: {item}" for item in sorted(known - current)
    ]


def main() -> int:
    """Check the repository against tools/docstring-baseline.json."""
    baseline = json.loads((ROOT / "tools" / "docstring-baseline.json").read_text(encoding="utf-8"))
    problems = check(ROOT, baseline["violations"])
    print("\n".join(problems) or "docstrings: OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
