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
import tempfile
from functools import cache
from pathlib import Path

from tools.check_skills import catalog_files, criteria_ids
from tools.validate_repo import ROOT

CASES = ROOT / "evals" / "cases"
REFERENCES = ROOT / "skills" / "auditing-repositories" / "references"
CATALOG = REFERENCES / "criteria.md"
FINDING_STATUSES = {"partial", "pending-implementation", "pending-verification"}
COVERAGE_STATUSES = {"meets", "not-applicable"}
CRITERION = re.compile(r"\b[A-Z]+-\d{2}\b")
MARKS = "`*_"
COVERAGE_LINE = re.compile(
    r"[-*]\s*[`*_]*(meets|not-applicable)(?: areas)?[`*_]*\s*:[`*_]*\s*(.*)", re.I
)
EVIDENCE_MARK = re.compile(r"[*_`\s]*(reproduced|inferred)\s*:", re.I)
ENTRY = re.compile(r"\b[A-Z]+-(?:\d{2}\b|\*)")
LEADING_IDS = re.compile(
    r"[-*]\s*[`*_]*((?:[A-Z]+-(?:\d{2}|\*)[`*_]*\s*,\s*[`*_]*)*[A-Z]+-(?:\d{2}|\*))"
)
ACTIONS_HEADING = re.compile(r"^(#{1,6})\s*Priority actions\b", re.I | re.M)
ACTION_ITEM = re.compile(r"(?:\d+[.)]|[-*])\s")
CITATION = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+):(\d+(?:[-–]\d+)?(?:,\s?\d+(?:[-–]\d+)?)*)")
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


def verify(case: Path, destination: Path) -> list[str]:
    """Return how a prepared repository differs from a fresh preparation of the same case."""

    def git(directory: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=directory, capture_output=True, text=True, check=True, timeout=30
        ).stdout

    with tempfile.TemporaryDirectory() as directory:
        reference = Path(directory) / "reference"
        prepare(case, reference)
        expected = git(reference, "rev-parse", "HEAD").strip()
    head = git(destination, "rev-parse", "HEAD").strip()
    problems = [f"HEAD is {head[:7]}, expected {expected[:7]}"] if head != expected else []
    status = git(destination, "status", "--porcelain", "--ignored", "--untracked-files=all")
    return problems + [f"changed: {line}" for line in status.splitlines()]


@cache
def catalog(references: Path = REFERENCES) -> tuple[list[str], dict[str, list[str]]]:
    """Return every criterion ID, core first, and the IDs of each area keyed by its prefix."""
    ids, areas = [], {}
    for path in catalog_files(references):
        found = criteria_ids(path.read_text(encoding="utf-8"))
        ids += found
        if path.name != "criteria.md" and found:
            areas[found[0].split("-")[0]] = found
    return ids, areas


def without_reasons(text: str) -> str:
    """Remove parenthesized reasons, nested ones included."""
    previous = None
    while previous != text:
        previous, text = text, re.sub(r"\([^()]*\)", "", text)
    return text


def report_statuses(
    text: str, areas: dict[str, list[str]] | None = None
) -> dict[str, list[str]]:
    """Map each criterion ID to every status the report gives it.

    Coverage IDs may be listed inline after the status or as indented bullets below it. A bullet
    counts the comma-separated entries that open it, once reasons in parentheses are removed, so IDs
    mentioned inside reasons are ignored. A not-applicable area wildcard such as `AGENT-*` stands for
    every ID of that area; any other wildcard is kept as an unknown entry.
    """
    areas = catalog()[1] if areas is None else areas
    statuses: dict[str, list[str]] = {}
    in_findings, coverage_status = False, None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip().strip(MARKS) for cell in stripped.strip("|").split("|")]
            if cells[:2] == ["ID", "Status"]:
                in_findings = True
            elif in_findings and len(cells) > 1 and CRITERION.fullmatch(cells[0]):
                statuses.setdefault(cells[0], []).append(cells[1].lower())
            continue
        in_findings = False
        match = COVERAGE_LINE.match(line)
        if match:
            coverage_status = match[1].lower()
            found = ENTRY.findall(without_reasons(match[2]))
        elif coverage_status and line[:1].isspace() and stripped[:1] in ("-", "*"):
            leading = LEADING_IDS.match(without_reasons(stripped))
            found = ENTRY.findall(leading[1]) if leading else []
        else:
            coverage_status = coverage_status if not stripped else None
            continue
        for entry in found:
            prefix = entry.removesuffix("-*")
            if entry.endswith("-*") and coverage_status == "not-applicable" and prefix in areas:
                for identifier in areas[prefix]:
                    statuses.setdefault(identifier, []).append(coverage_status)
            else:
                statuses.setdefault(entry, []).append(coverage_status)
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
        identifier = cells[0].strip(MARKS)
        if [cell.strip(MARKS) for cell in cells[:2]] == ["ID", "Status"]:
            in_findings = True
        elif in_findings and len(cells) >= 4 and CRITERION.fullmatch(identifier):
            rows[identifier] = {
                "status": cells[1].strip(MARKS).lower(),
                "priority": cells[2].strip(MARKS).lower(),
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


def leaked(text: str, expected: dict) -> list[str]:
    """Return the forbidden strings that the report contains, masked so the output does not repeat them."""
    return [
        f"{value[:4]}... ({len(value)} characters)"
        for value in expected.get("must_not_contain", [])
        if value in text
    ]


def bad_citations(text: str, repo: Path) -> list[str]:
    """Return `path:line` citations of case files whose lines fall outside the file.

    A path resolves to a file by its full relative path or, failing that, by a unique suffix such
    as `app.py`. Paths that do not resolve, like guide names or missing files, are not checked.
    """
    files = {
        path.relative_to(repo).as_posix(): path
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }
    problems = set()
    for path, lines in CITATION.findall(text):
        matches = [path] if path in files else [f for f in files if f.endswith("/" + path)]
        if len(matches) != 1:
            continue
        length = len(files[matches[0]].read_text(encoding="utf-8", errors="replace").splitlines())
        numbers = [int(number) for number in re.findall(r"\d+", lines)]
        if min(numbers) < 1 or max(numbers) > length:
            problems.add(f"{path}:{lines} ({length} lines)")
    return sorted(problems)


def quoted_code(text: str, start: int, end: int) -> str | None:
    """Return the code a citation quotes, within its table cell and sentence, if any.

    A citation in parentheses backs the code span right before them, as in `x = 1` (`a.py:3`). Any
    other citation backs the first code span after it when a few words, not a list separator,
    separate them, as in `a.py:3` sets `x = 1`, and that span carries no citation of its own. Only
    spans of six or more characters that hold more than a name or path count as quoted code.
    """
    line_start, line_end = text.rfind("\n", 0, start) + 1, text.find("\n", end) % (len(text) + 1)
    before = text[line_start:start].removesuffix("`").rstrip()
    rest = text[end:line_end].removeprefix("`")
    if before.endswith("(") or rest.startswith(")"):
        preceding = re.search(r"`([^`]+)`\s*\($", before)
        span = preceding[1] if preceding else None
    else:
        following = re.match(r"([^`|]{0,15})`([^`]+)`", rest)
        gap = following[1].strip() if following else ""
        own = following and re.match(r"\s*\(?\s*`?(?:" + CITATION.pattern + r"|:\d+)", rest[following.end() :])
        listed = gap[:1] in ",;" or gap in ("and", "or") or not re.search(r"[A-Za-z:]", gap)
        span = following[2] if following and not own and not listed and ":" not in gap[1:] else None
    if span is None or len(span) < 6 or not re.search(r"[^\w./-]", span) or CITATION.fullmatch(span):
        return None
    return " ".join(span.replace("\\|", "|").split())


def misplaced_citations(text: str, repo: Path) -> list[str]:
    """Return citations whose quoted code occurs in the cited file only on other lines.

    This catches citations of the wrong line, which `bad_citations` cannot. A citation without a
    quoted neighbor that occurs in the file is not checked.
    """
    files = {
        path.relative_to(repo).as_posix(): path
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }
    problems = set()
    for match in CITATION.finditer(text):
        path, lines = match.groups()
        matches = [path] if path in files else [f for f in files if f.endswith("/" + path)]
        if len(matches) != 1:
            continue
        snippet = quoted_code(text, match.start(), match.end())
        if snippet is None:
            continue
        content = files[matches[0]].read_text(encoding="utf-8", errors="replace").splitlines()
        found = [n for n, line in enumerate(content, 1) if snippet in " ".join(line.split())]
        cited = set()
        for part in re.split(r",\s?", lines):
            first, _, last = part.replace("–", "-").partition("-")
            cited.update(range(int(first), int(last or first) + 1))
        if found and not cited & set(found):
            problems.add(f"{path}:{lines} (quoted code is on line {found[0]})")
    return sorted(problems)


def check_text(text: str, case: Path, expected: dict) -> dict:
    """Checks that apply to any report, with or without criterion IDs."""
    return {"leaked": leaked(text, expected), "bad_citations": bad_citations(text, case / "repo")}


def score_report(report: Path, case: Path) -> tuple[dict, dict]:
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    ids = catalog()[0]
    text = report.read_text(encoding="utf-8")
    result = score(report_statuses(text), ids, expected, finding_rows(text))
    return expected, result | check_text(text, case, expected)


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


def priority_actions(text: str) -> list[list[str]]:
    """Return the criterion IDs named by each top-level item of the Priority actions section."""
    heading = ACTIONS_HEADING.search(text)
    if not heading:
        return []
    actions: list[list[str]] = []
    for line in text[heading.end() :].splitlines()[1:]:
        if re.match(rf"#{{1,{len(heading[1])}}}\s", line):
            break
        if ACTION_ITEM.match(line):
            actions.append([])
        if actions:
            actions[-1] += [i for i in CRITERION.findall(line) if i not in actions[-1]]
    return actions


def priority_placement(text: str, expected: dict) -> str | None:
    """Describe where the report's actions place the case's top priorities, and its high findings.

    These are comparisons between reports, not failures: the maintainer fixes `top_priorities`, and
    optionally `max_high`, before reading any report.
    """
    top = expected.get("top_priorities")
    if not top:
        return None
    actions = priority_actions(text)
    positions = [next((n for n, ids in enumerate(actions, 1) if i in ids), None) for i in top]
    high = [i for i, row in finding_rows(text).items() if row["priority"] == "high"]
    placed = ", ".join(f"{i} {p or '-'}" for i, p in zip(top, positions))
    line = (
        f"top priorities by action ({len(actions)} actions): {placed}; "
        f"{sum(p is not None and p <= 5 for p in positions)} of {len(top)} in the first five; "
        f"high outside them: {len(set(high) - set(top))}"
    )
    if len(high) > expected.get("max_high", len(high)):
        line += f"; {len(high)} high against a case limit of {expected['max_high']}"
    return line


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="copy a case into a new Git repository")
    prepare_parser.add_argument("case")
    prepare_parser.add_argument("destination", type=Path)
    score_parser = commands.add_parser("score", help="score an audit report for a case")
    score_parser.add_argument("report", type=Path)
    score_parser.add_argument("case")
    check_parser = commands.add_parser(
        "check", help="check any report, even one without IDs, for leaks and bad citations"
    )
    check_parser.add_argument("report", type=Path)
    check_parser.add_argument("case")
    verify_parser = commands.add_parser(
        "verify", help="check that an audit left a prepared repository unchanged"
    )
    verify_parser.add_argument("case")
    verify_parser.add_argument("destination", type=Path)
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
    if arguments.command == "verify":
        problems = verify(case, arguments.destination)
        print("\n".join(problems) or f"{arguments.destination} is unchanged")
        return int(bool(problems))
    if arguments.command == "check":
        expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
        result = check_text(arguments.report.read_text(encoding="utf-8"), case, expected)
        print(f"report sha256: {hashlib.sha256(arguments.report.read_bytes()).hexdigest()}")
        for key, values in result.items():
            print(f"{key}: {', '.join(values) or 'none'}")
        misplaced = misplaced_citations(arguments.report.read_text(encoding="utf-8"), case / "repo")
        print(f"misplaced citations (not a failure): {', '.join(misplaced) or 'none'}")
        return int(any(result.values()))
    expected, result = score_report(arguments.report, case)
    text = arguments.report.read_text(encoding="utf-8")
    print(f"Case {arguments.case}: found {len(result['found'])} of {len(expected['must_find'])} seeded gaps.")
    print(f"report sha256: {hashlib.sha256(arguments.report.read_bytes()).hexdigest()}")
    print(priority_summary(text))
    placement = priority_placement(text, expected)
    if placement:
        print(placement)
    misplaced = misplaced_citations(text, case / "repo")
    if misplaced:
        print(f"misplaced citations (not a failure): {', '.join(misplaced)}")
    for key, values in result.items():
        if key != "found" and values:
            print(f"{key}: {', '.join(values)}")
    return int(any(values for key, values in result.items() if key != "found"))


if __name__ == "__main__":
    raise SystemExit(main())
