#!/usr/bin/env python3
"""Prepare evaluation repositories and score audit reports against expected findings."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from tools.check_skills import criteria_ids
from tools.validate_repo import ROOT

CASES = ROOT / "evals" / "cases"
CATALOG = ROOT / "skills" / "auditing-repositories" / "references" / "criteria.md"
FINDING_STATUSES = {"partial", "pending-implementation", "pending-verification"}
COVERAGE_STATUSES = {"meets", "not-applicable"}
CRITERION = re.compile(r"\b[A-Z]+-\d{2}\b")
COVERAGE_LINE = re.compile(r"[-*]\s*(meets|not-applicable)\s*:\s*(.*)", re.I)
FIXED_IDENTITY = {
    "GIT_AUTHOR_NAME": "Evaluation Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_NAME": "Evaluation Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


def prepare(case: Path, destination: Path) -> None:
    """Copy a case repository and commit it so the audit has a revision to record.

    Identity, dates, and file modes are fixed, so the revision is the same in every environment;
    without core.fileMode=false, WSL records files under /mnt/c as executable.
    """
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination}")
    shutil.copytree(case / "repo", destination)
    environment = {**os.environ, **FIXED_IDENTITY}
    for command in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "core.fileMode", "false"],
        ["git", "add", "-A"],
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "Initial commit"],
    ):
        subprocess.run(command, cwd=destination, env=environment, check=True, timeout=30)


def report_statuses(text: str) -> dict[str, list[str]]:
    """Map each criterion ID to every status the report gives it."""
    statuses: dict[str, list[str]] = {}
    in_findings = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
            if cells[:2] == ["ID", "Status"]:
                in_findings = True
            elif in_findings and len(cells) > 1 and CRITERION.fullmatch(cells[0]):
                statuses.setdefault(cells[0], []).append(cells[1].lower())
            continue
        in_findings = False
        match = COVERAGE_LINE.match(stripped)
        if match:
            listed = re.sub(r"\([^)]*\)", "", match[2])
            for identifier in CRITERION.findall(listed):
                statuses.setdefault(identifier, []).append(match[1].lower())
    return statuses


def score(statuses: dict[str, list[str]], catalog: list[str], expected: dict) -> dict:
    flagged = {
        identifier
        for identifier, values in statuses.items()
        if FINDING_STATUSES.intersection(values)
    }
    allowed = FINDING_STATUSES | COVERAGE_STATUSES
    return {
        "found": sorted(set(expected["must_find"]) & flagged),
        "missed": sorted(set(expected["must_find"]) - flagged),
        "false_flags": sorted(set(expected["must_not_flag"]) & flagged),
        "uncovered": [identifier for identifier in catalog if identifier not in statuses],
        "duplicated": sorted(i for i, values in statuses.items() if len(values) > 1),
        "unknown": sorted(set(statuses) - set(catalog)),
        "invalid_status": sorted(
            i for i, values in statuses.items() if set(values) - allowed
        ),
    }


def score_report(report: Path, case: Path) -> tuple[dict, dict]:
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    catalog = criteria_ids(CATALOG.read_text(encoding="utf-8"))
    result = score(report_statuses(report.read_text(encoding="utf-8")), catalog, expected)
    return expected, result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="copy a case into a new Git repository")
    prepare_parser.add_argument("case")
    prepare_parser.add_argument("destination", type=Path)
    score_parser = commands.add_parser("score", help="score an audit report for a case")
    score_parser.add_argument("report", type=Path)
    score_parser.add_argument("case")
    arguments = parser.parse_args()
    case = CASES / arguments.case
    if not (case / "expected.json").is_file():
        parser.error(f"unknown case: {arguments.case}")
    if arguments.command == "prepare":
        prepare(case, arguments.destination)
        print(f"Prepared {arguments.case} at {arguments.destination}")
        return 0
    expected, result = score_report(arguments.report, case)
    print(f"Case {arguments.case}: found {len(result['found'])} of {len(expected['must_find'])} seeded gaps.")
    for key, values in result.items():
        if key != "found" and values:
            print(f"{key}: {', '.join(values)}")
    return int(any(values for key, values in result.items() if key != "found"))


if __name__ == "__main__":
    raise SystemExit(main())
