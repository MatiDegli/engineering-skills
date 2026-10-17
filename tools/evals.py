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
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache, partial
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
SEED_PATH = re.compile(r"[^\t\n\\*?\[\]]+")
FIXED_IDENTITY = {
    "GIT_AUTHOR_NAME": "Evaluation Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_NAME": "Evaluation Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


def git_environment(**variables: str) -> dict[str, str]:
    """Return the caller's environment without Git's variables and configuration, plus `variables`.

    Hooks export variables such as GIT_INDEX_FILE, and a caller may export GIT_OBJECT_DIRECTORY;
    inherited, they point a command at another repository's index or objects. User and system
    configuration can add hooks, filters, signing, or commit encodings that change the result.
    """
    clean = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    isolated = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1"}
    return {**clean, **isolated, "GIT_TERMINAL_PROMPT": "0", **variables}


def git_at(
    git_dir: Path,
    *arguments: str,
    work_tree: Path | None = None,
    stdin: str | None = None,
    environment: dict | None = None,
) -> str:
    """Run Git on exactly this Git directory, never on one found by searching parent directories."""
    variables = {"GIT_DIR": str(git_dir), **({"GIT_WORK_TREE": str(work_tree)} if work_tree else {})}
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=work_tree or git_dir,
        env=git_environment(**variables, **(environment or {})),
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
        timeout=900,
    ).stdout


def prepare(case: Path, destination: Path) -> None:
    """Copy a case repository and commit it so the audit has a revision to record.

    Identity, dates, and file modes are fixed, so the revision is the same in every environment;
    without core.fileMode=false, WSL records files under /mnt/c as executable. A case with a
    `source.json` is cloned from a pinned commit instead; see `prepare_from_source`.
    """
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination}")
    if (case / "source.json").is_file():
        prepare_from_source(case, destination)
        return
    shutil.copytree(case / "repo", destination)
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=destination,
        env=git_environment(),
        check=True,
        timeout=30,
    )
    git = partial(git_at, destination / ".git", work_tree=destination, environment=FIXED_IDENTITY)
    git("config", "core.fileMode", "false")
    git("add", "-A")
    git("commit", "-q", "-m", "Initial commit")


def clone(origin: Path, target: Path, *options: str) -> None:
    """Clone without templates, hooks, or the caller's Git settings, so no hook or filter runs."""
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "clone", "-q", "--no-local", "--template="]
        + ["-o", "origin", *options, "--", str(origin), str(target)],
        cwd=tempfile.gettempdir(),
        env=git_environment(),
        capture_output=True,
        text=True,
        check=True,
        timeout=900,
    )


def seed_files(case: Path) -> dict[str, Path]:
    """Return the files under the case's `seed/` by repository path; symbolic links are refused."""
    seed, files = case / "seed", {}
    for directory, names, file_names in os.walk(seed):
        for name in names + file_names:
            path = Path(directory) / name
            if path.is_symlink():
                raise SystemExit(f"Seed entries must not be symbolic links: {path}")
            if name in file_names:
                files[path.relative_to(seed).as_posix()] = path
    return dict(sorted(files.items()))


def seed_operations(case: Path, source: dict, git) -> tuple[dict[str, list[str]], dict]:
    """Map each commit to the index entries that plant the seeds; also return what to check after.

    A replaced or removed path changes in every commit that holds the content it has at the pinned
    commit, so neither its history, a backport, nor a revert keeps that content; a copy of the same
    content at another path is not changed. A new file appears in the last commit that changed a
    file directly in its nearest existing directory, and in every later commit. New files are not
    executable unless `source.json` lists them under `executable`.
    """
    files = seed_files(case)
    removed = list(dict.fromkeys(source.get("remove", [])))
    executable = set(source.get("executable", []))
    commits = git("rev-list", "HEAD").split()
    operations: dict[str, list[str]] = {}
    checks: dict[str, tuple[tuple[str, str] | None, str | None]] = {}
    for path in [*files, *removed]:
        parts = path.split("/")
        if (
            not SEED_PATH.fullmatch(path)
            or path.startswith(":")
            or any(part in ("", ".", "..") or part.lower() == ".git" for part in parts)
            or (path in files and path in removed)
        ):
            raise SystemExit(f"Unsupported seed path: {path!r}")
        for depth in range(1, len(parts)):
            if git("ls-tree", "HEAD", "--", "/".join(parts[:depth])).split()[1:2] == ["blob"]:
                raise SystemExit(f"A parent of the seed path is a file: {path}")
        listed = git("ls-tree", "HEAD", "--", path)
        current = listed.split("\t", 1)[0].split() if listed else []
        if current and (current[1] != "blob" or current[0] == "120000"):
            raise SystemExit(f"Seed path is not a regular file at the pinned commit: {path}")
        if not current and path in removed:
            raise SystemExit(f"Cannot remove a path that the pinned commit lacks: {path}")
        if current:
            targets = commits
        else:
            directory = "/".join(parts[:-1])
            while directory and not git("ls-tree", "-d", "HEAD", "--", directory).strip():
                directory = directory.rpartition("/")[0]
            anchors = [f":(glob){directory}/*" if directory else ":(glob)*", directory or "."]
            last = next(
                (c for a in anchors if (c := git("log", "-1", "--format=%H", "HEAD", "--", a).strip())),
                None,
            )
            if last is None:
                raise SystemExit(f"No commit touches the directory of seed path: {path}")
            targets = [last, *git("rev-list", "--ancestry-path", f"{last}..HEAD").split()]
        held = git(
            "cat-file", "--batch-check=%(objectname)", stdin="".join(f"{c}:{path}\n" for c in targets)
        ).splitlines()
        if path in removed:
            entry, wanted = f"0 {'0' * 40}\t{path}\n", None
        else:
            mode = "100755" if path in executable else current[0] if current else "100644"
            blob = git("hash-object", "-w", "--no-filters", "--", str(files[path])).strip()
            entry, wanted = f"{mode} {blob}\t{path}\n", (mode, blob)
        for commit, held_object in zip(targets, held):
            if held_object == current[2] if current else held_object.endswith(" missing"):
                operations.setdefault(commit, []).append(entry)
        checks[path] = (wanted, current[2] if current else None)
    if set(source.get("executable", [])) - set(files):
        raise SystemExit("Every path under `executable` must be a seed file")
    return operations, checks


def check_seeds(git, checks: dict) -> None:
    """Fail unless HEAD holds every seed and no commit keeps a replaced path's pinned content."""
    commits = git("rev-list", "HEAD").split()
    for path, (wanted, pinned) in checks.items():
        listed = git("ls-tree", "HEAD", "--", path)
        held = tuple(listed.split("\t", 1)[0].split()[0::2]) if listed else None
        if held != wanted:
            raise SystemExit(f"HEAD does not hold the seed for {path}: {held} instead of {wanted}")
        if pinned:
            blobs = git(
                "cat-file", "--batch-check=%(objectname)", stdin="".join(f"{c}:{path}\n" for c in commits)
            ).splitlines()
            if pinned in blobs:
                raise SystemExit(f"A commit still holds the content seeded away at {path}")


def prepare_from_source(case: Path, destination: Path) -> None:
    """Clone a pinned commit of a local repository and fold the case's seeded changes into it.

    `source.json` names the `repository` (relative paths start at the case directory), the full
    `commit` SHA, the paths to `remove`, and any new seed files that are `executable`; `seed/`
    holds files to add or replace, at their paths in the repository. `seed_operations` explains
    where each change lands. The history is rewritten in a temporary bare clone, which the
    destination then clones, so the work tree is written once and every file has the same age, and
    no rewrite leftovers reach the destination. The source is only read. The destination keeps one
    branch and no remote, reflog, or unreachable objects, so nothing in it leads back to the
    original files. Commit metadata is kept; signatures and encoding headers are dropped from every
    commit alike. Any failure removes the destination.
    """
    source = json.loads((case / "source.json").read_text(encoding="utf-8"))
    origin = Path(source["repository"]).expanduser()
    origin = (origin if origin.is_absolute() else case / origin).resolve()
    target = destination.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit", ""))):
        raise SystemExit("source.json must pin a full 40-character commit SHA")
    if target == origin or origin in target.parents or target in origin.parents:
        raise SystemExit(f"The destination must be outside the source repository: {destination}")
    if target.exists():
        raise SystemExit(f"Destination already exists: {destination}")
    try:
        with tempfile.TemporaryDirectory() as scratch:
            work = Path(scratch) / "work.git"
            clone(origin, work, "--bare")
            git = partial(git_at, work)
            if (work / "shallow").exists():
                raise SystemExit("The source repository is shallow; its history is incomplete")
            git("update-ref", "refs/heads/main", source["commit"])
            git("symbolic-ref", "HEAD", "refs/heads/main")
            for ref in git("for-each-ref", "--format=%(refname)").split():
                if ref != "refs/heads/main":
                    git("update-ref", "-d", ref)
            operations, checks = seed_operations(case, source, git)
            if operations:
                entries = Path(scratch) / "entries"
                entries.mkdir()
                for commit, lines in operations.items():
                    (entries / commit).write_text("".join(lines), encoding="utf-8")
                git(
                    "filter-branch",
                    "-d",
                    str(Path(scratch) / "rewrite"),
                    "--index-filter",
                    'if test -f "$SEED_ENTRIES/$GIT_COMMIT"; then '
                    'git update-index --index-info < "$SEED_ENTRIES/$GIT_COMMIT"; fi',
                    "--",
                    "main",
                    environment={"FILTER_BRANCH_SQUELCH_WARNING": "1", "SEED_ENTRIES": str(entries)},
                )
            check_seeds(git, checks)
            clone(work, target)
        git = partial(git_at, target / ".git", work_tree=target)
        git("remote", "remove", "origin")
        git("config", "core.fileMode", "false")
        for name in ("ORIG_HEAD", "FETCH_HEAD"):
            (target / ".git" / name).unlink(missing_ok=True)
        git("reflog", "expire", "--expire=now", "--expire-unreachable=now", "--all")
        git("gc", "-q", "--prune=now")
        if git("status", "--porcelain", "--ignored", "--untracked-files=all").strip():
            raise SystemExit(f"The prepared repository is not clean: {destination}")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


def verify(case: Path, destination: Path) -> list[str]:
    """Return how a prepared repository differs from a fresh preparation of the same case."""

    def git(directory: Path, *arguments: str) -> str:
        return git_at(directory / ".git", *arguments, work_tree=directory)

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


def check_text(text: str, repo: Path, expected: dict) -> dict:
    """Checks that apply to any report, with or without criterion IDs."""
    return {"leaked": leaked(text, expected), "bad_citations": bad_citations(text, repo)}


def score_report(report: Path, case: Path, repo: Path) -> tuple[dict, dict]:
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    ids = catalog()[0]
    text = report.read_text(encoding="utf-8")
    result = score(report_statuses(text), ids, expected, finding_rows(text))
    return expected, result | check_text(text, repo, expected)


@contextmanager
def case_files(case: Path) -> Iterator[Path]:
    """Yield the files that a case's reports cite: its `repo/`, or else a fresh preparation."""
    if (case / "repo").is_dir():
        yield case / "repo"
        return
    with tempfile.TemporaryDirectory() as directory:
        prepare(case, Path(directory) / "repo")
        yield Path(directory) / "repo"


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
    prepare_parser = commands.add_parser(
        "prepare", help="copy a case into a new Git repository; a case may also be a directory path"
    )
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
    case = Path(arguments.case).expanduser() if "/" in arguments.case else CASES / arguments.case
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
    with case_files(case) as repo:
        if arguments.command == "check":
            return check_command(arguments.report, case, repo)
        return score_command(arguments.report, case, repo)


def check_command(report: Path, case: Path, repo: Path) -> int:
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    text = report.read_text(encoding="utf-8")
    result = check_text(text, repo, expected)
    print(f"report sha256: {hashlib.sha256(report.read_bytes()).hexdigest()}")
    for key, values in result.items():
        print(f"{key}: {', '.join(values) or 'none'}")
    misplaced = misplaced_citations(text, repo)
    print(f"misplaced citations (not a failure): {', '.join(misplaced) or 'none'}")
    return int(any(result.values()))


def score_command(report: Path, case: Path, repo: Path) -> int:
    expected, result = score_report(report, case, repo)
    text = report.read_text(encoding="utf-8")
    print(f"Case {case.name}: found {len(result['found'])} of {len(expected['must_find'])} seeded gaps.")
    print(f"report sha256: {hashlib.sha256(report.read_bytes()).hexdigest()}")
    print(priority_summary(text))
    placement = priority_placement(text, expected)
    if placement:
        print(placement)
    misplaced = misplaced_citations(text, repo)
    if misplaced:
        print(f"misplaced citations (not a failure): {', '.join(misplaced)}")
    for key, values in result.items():
        if key != "found" and values:
            print(f"{key}: {', '.join(values)}")
    return int(any(values for key, values in result.items() if key != "found"))


if __name__ == "__main__":
    raise SystemExit(main())
