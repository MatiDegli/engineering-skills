#!/usr/bin/env python3
"""Run the repository checks on the exact tree of every commit in a range, without its history.

Each commit is archived into a new temporary directory and checked there, so a check that depends
on this repository's history, on an untracked file, or on the working tree fails here as it would
for that commit alone. CI checks only the commit it receives; this covers the commits under it.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from tools.evals import git_environment
from tools.validate_repo import ROOT


def git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        env=git_environment(),
        capture_output=True,
        check=True,
        timeout=120,
    ).stdout


def commits(root: Path, revisions: str) -> list[str]:
    return git(root, "rev-list", "--reverse", revisions).decode().split()


def check_commit(root: Path, commit: str) -> tuple[int, str]:
    """Check one commit's tree in a new Git repository; return the exit code and last output line."""
    archive = git(root, "archive", "--format=tar", commit)
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tree, filter="data")
        for command in (["git", "init", "-q"], ["git", "add", "-A"]):
            subprocess.run(command, cwd=tree, env=git_environment(), check=True, timeout=120)
        result = subprocess.run(
            [sys.executable, "tools/check.py"],
            cwd=tree,
            capture_output=True,
            text=True,
            timeout=900,
        )
    lines = (result.stdout + result.stderr).strip().splitlines()
    return result.returncode, lines[-1] if lines else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "revisions", nargs="?", default="origin/main..HEAD", help="a range for git rev-list"
    )
    arguments = parser.parse_args()
    failed = 0
    for commit in commits(ROOT, arguments.revisions):
        code, last = check_commit(ROOT, commit)
        failed += code != 0
        print(f"{commit[:7]} exit={code} {last}", flush=True)
    print(f"{failed} failing commit(s)")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
