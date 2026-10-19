#!/usr/bin/env python3
"""Fail when a public function, method, or class has no docstring and is not in the baseline.

The baseline, tools/docstring-baseline.json, lists the violations that predate the rule. It can
only shrink: a new violation fails, and so does a listed symbol that now has a docstring. With
`--base REF`, as CI runs it on pull requests, a change that adds baseline entries fails unless the
baseline is the only file it touches, so the baseline cannot grow with the code it would excuse.
"""

import argparse
import ast
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "tools/docstring-baseline.json"
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
    known = entries(baseline)
    current = violations(root)
    return [f"new violation: {item}" for item in sorted(current - known)] + [
        f"fixed, delete it from the baseline: {item}" for item in sorted(known - current)
    ]


def entries(baseline: dict[str, list[str]]) -> set[str]:
    return {f"{path}::{symbol}" for path, symbols in baseline.items() for symbol in symbols}


def growth(base: dict[str, list[str]], head: dict[str, list[str]], changed: list[str]) -> list[str]:
    """Return what is wrong when the baseline gains entries in a change that touches other files."""
    added = sorted(entries(head) - entries(base))
    others = sorted(path for path in changed if path != BASELINE)
    if not added or not others:
        return []
    return [f"baseline entry added beside other changes ({', '.join(others)}): {item}" for item in added]


def git(*arguments: str) -> str:
    return subprocess.run(("git", *arguments), cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main() -> int:
    """Check the repository against tools/docstring-baseline.json, and the change against `--base`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="the ref a pull request merges into, such as origin/main")
    args = parser.parse_args()
    baseline = json.loads((ROOT / BASELINE).read_text(encoding="utf-8"))
    problems = check(ROOT, baseline["violations"])
    if args.base:
        before = json.loads(git("show", f"{args.base}:{BASELINE}"))
        changed = git("diff", "--name-only", f"{args.base}...HEAD").split()
        problems += growth(before["violations"], baseline["violations"], changed)
    print("\n".join(problems) or "docstrings: OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
