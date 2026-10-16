#!/usr/bin/env python3
"""Prepare evaluation repositories and score audit reports against expected findings."""

from __future__ import annotations

import argparse
import hashlib
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
EVIDENCE_MARK = re.compile(r"[*_`\s]*(reproduced|inferred)\s*:", re.I)
LEADING_IDS = re.compile(r"[-*]\s*`?((?:[A-Z]+-\d{2}`?\s*,\s*`?)*[A-Z]+-\d{2})")
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
    """Map each criterion ID to every status the report gives it.

    Coverage IDs may be listed inline after the status or as indented bullets below it. A bullet
    counts the comma-separated IDs that open it; IDs inside reasons are ignored.
    """
    statuses: dict[str, list[str]] = {}
    in_findings, coverage_status = False, None
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
        match = COVERAGE_LINE.match(line)
        if match:
            coverage_status = match[1].lower()
            found = CRITERION.findall(re.sub(r"\([^)]*\)", "", match[2]))
        elif coverage_status and line[:1].isspace() and stripped[:1] in ("-", "*"):
            leading = LEADING_IDS.match(stripped)
            found = CRITERION.findall(leading[1]) if leading else []
        else:
            coverage_status = coverage_status if not stripped else None
            continue
        for identifier in found:
            statuses.setdefault(identifier, []).append(coverage_status)
    return statuses


def finding_rows(text: str) -> dict[str, dict[str, str]]:
    """Return the status, priority, and evidence of each row in the findings table."""
    rows: dict[str, dict[str, str]] = {}
    in_findings = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_findings = False
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        identifier = cells[0].strip("`")
        if [cell.strip("`") for cell in cells[:2]] == ["ID", "Status"]:
            in_findings = True
        elif in_findings and len(cells) >= 4 and CRITERION.fullmatch(identifier):
            rows[identifier] = {
                "status": cells[1].strip("`").lower(),
                "priority": cells[2].strip("`").lower(),
                "evidence": cells[3],
            }
    return rows


def flagged_ids(statuses: dict[str, list[str]]) -> set[str]:
    return {i for i, values in statuses.items() if FINDING_STATUSES.intersection(values)}


def score(
    statuses: dict[str, list[str]],
    catalog: list[str],
    expected: dict,
    rows: dict[str, dict[str, str]] | None = None,
) -> dict:
    flagged = flagged_ids(statuses)
    allowed = FINDING_STATUSES | COVERAGE_STATUSES
    rows = rows or {}
    return {
        "unmarked_high": sorted(
            i
            for i, row in rows.items()
            if row["priority"] == "high" and not EVIDENCE_MARK.match(row["evidence"])
        ),
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
    text = report.read_text(encoding="utf-8")
    result = score(report_statuses(text), catalog, expected, finding_rows(text))
    return expected, result


def compare(first: str, second: str) -> dict:
    """Measure agreement between two reports of the same case."""
    statuses = report_statuses(first), report_statuses(second)
    rows = finding_rows(first), finding_rows(second)
    flagged = flagged_ids(statuses[0]), flagged_ids(statuses[1])
    common = set(statuses[0]) & set(statuses[1])
    both = sorted(i for i in flagged[0] & flagged[1] if i in rows[0] and i in rows[1])
    differences = [
        f"{i} {rows[0][i]['priority']}/{rows[1][i]['priority']}"
        for i in both
        if rows[0][i]["priority"] != rows[1][i]["priority"]
    ]
    return {
        "flagged_overlap": (len(flagged[0] & flagged[1]), len(flagged[0] | flagged[1])),
        "status_agreement": (
            sum(statuses[0][i][0] == statuses[1][i][0] for i in common),
            len(common),
        ),
        "priority_agreement": (len(both) - len(differences), len(both)),
        "priority_differences": differences,
        "only_first": sorted(flagged[0] - flagged[1]),
        "only_second": sorted(flagged[1] - flagged[0]),
    }


def priority_summary(text: str) -> str:
    rows = finding_rows(text).values()
    counts = {level: sum(r["priority"] == level for r in rows) for level in ("high", "medium", "low")}
    marks = [EVIDENCE_MARK.match(r["evidence"]) for r in rows if r["priority"] == "high"]
    reproduced = sum(bool(m) and m[1].lower() == "reproduced" for m in marks)
    return (
        f"priorities: high {counts['high']}, medium {counts['medium']}, low {counts['low']}; "
        f"high reproduced {reproduced}, inferred {sum(bool(m) for m in marks) - reproduced}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="copy a case into a new Git repository")
    prepare_parser.add_argument("case")
    prepare_parser.add_argument("destination", type=Path)
    score_parser = commands.add_parser("score", help="score an audit report for a case")
    score_parser.add_argument("report", type=Path)
    score_parser.add_argument("case")
    compare_parser = commands.add_parser("compare", help="compare two reports of one case")
    compare_parser.add_argument("first", type=Path)
    compare_parser.add_argument("second", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "compare":
        texts = [path.read_text(encoding="utf-8") for path in (arguments.first, arguments.second)]
        for key, value in compare(*texts).items():
            shown = f"{value[0]} of {value[1]}" if isinstance(value, tuple) else ", ".join(value)
            print(f"{key}: {shown or 'none'}")
        return 0
    case = CASES / arguments.case
    if not (case / "expected.json").is_file():
        parser.error(f"unknown case: {arguments.case}")
    if arguments.command == "prepare":
        prepare(case, arguments.destination)
        print(f"Prepared {arguments.case} at {arguments.destination}")
        return 0
    expected, result = score_report(arguments.report, case)
    text = arguments.report.read_text(encoding="utf-8")
    print(f"Case {arguments.case}: found {len(result['found'])} of {len(expected['must_find'])} seeded gaps.")
    print(f"report sha256: {hashlib.sha256(arguments.report.read_bytes()).hexdigest()}")
    print(priority_summary(text))
    for key, values in result.items():
        if key != "found" and values:
            print(f"{key}: {', '.join(values)}")
    return int(any(values for key, values in result.items() if key != "found"))


if __name__ == "__main__":
    raise SystemExit(main())
