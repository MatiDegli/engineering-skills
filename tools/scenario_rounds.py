#!/usr/bin/env python3
"""Run coordination scenarios headless with Claude Code, and score what the agents did.

A scenario prepares a workspace, gives an agent a task, and checks the report, the state the agent
left behind, and the commands it ran; see evals/coordinating-agents/README.md. `plan` validates the
scenarios and exports the skill; `run` makes each agent work in a sandbox, so run it yourself;
`summarize` scores the records; `clean` removes what a stopped round left behind. A round directory
keeps the plan, the streams, the reports, a record per run, and the summary. Keep it outside this
repository and outside /tmp, which a restart may clear.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import functools
import glob
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import signal
import stat
import statistics
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from tools.claude_rounds import (
    ANTHROPIC,
    init_key_source,
    log_overlaps,
    login_failed,
    outside_paths,
    overlap_note,
    parse_providers,
    provider_launch,
    ran_model,
    report_text,
    round_lock,
    round_resources,
    stop_groups,
    stream_results,
    stream_usage,
    warm_up,
)
from tools.evals import SETTINGS_OFF, git_environment
from tools.validate_repo import ROOT

SCENARIOS = ROOT / "evals" / "coordinating-agents" / "scenarios"
TIME_FORMAT = "%Y-%m-%dT%H:%MZ"
IDENTITY = {
    "GIT_AUTHOR_NAME": "Evaluation Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Evaluation Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}
# A fixture kind's required and optional fields.
FIXTURES = {
    "repo": ({"path", "commits"}, set()),
    "remote": ({"repo", "path"}, set()),
    "branch": ({"repo", "name", "from"}, {"commits"}),
    "commits": ({"repo", "branch", "commits"}, set()),
    "worktree": ({"repo", "path", "branch"}, {"uncommitted"}),
    "stash": ({"repo", "message", "files"}, set()),
    "file": ({"path", "source"}, set()),
    "process": ({"name", "command", "seconds"}, {"cwd"}),
}
COMMIT_FIELDS = ({"message"}, {"files", "delete", "minutes_ago"})
WORKSPACE_PREFIX = "scenario."
# Seconds that a `process` fixture must outlive the time limit: the launcher's grace before it
# kills a late agent, and the time to stop what the agent left running.
FIXTURE_MARGIN = 120
TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
NOW_TEMPLATE = re.compile(r"now(?:([+-])(\d+)m)?")
REVISION_TEMPLATE = re.compile(r"(sha|short):([^:]+):(.+)")


def relative_path(value: str) -> Path:
    """Return a fixture path, refusing one that is absolute or leaves the workspace."""
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"a fixture path must be relative and stay inside the workspace: {value!r}")
    return path


def copy_tree(source: Path, destination: Path) -> None:
    """Copy a directory of fixture files over a tree; a file is executable only if its source is."""
    if not source.is_dir():
        raise SystemExit(f"missing fixture files: {source}")
    for path in sorted(source.rglob("*")):
        target = destination / path.relative_to(source)
        if path.is_symlink():
            raise SystemExit(f"a fixture file must not be a symbolic link: {path}")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        target.chmod(0o755 if path.stat().st_mode & 0o100 else 0o644)


class Fixtures:
    """Applies a scenario's fixtures, in order, to a new workspace.

    Git runs without the host's configuration, hooks, or templates, with a fixed identity, so a
    fixture does not depend on the machine. Every repository is recorded in `manifest`, so the
    snapshots read exactly those Git directories.
    """

    def __init__(self, files: Path, workspace: Path, now: datetime) -> None:
        self.files, self.workspace, self.now = files, workspace, now
        self.manifest = {"prepared": now.strftime(TIME_FORMAT), "repos": [], "remotes": []}
        self.manifest |= {"worktrees": [], "processes": []}

    def path(self, value: str) -> Path:
        return self.workspace / relative_path(value)

    def repo(self, name: str) -> Path:
        if name not in self.manifest["repos"]:
            raise SystemExit(f"a fixture names the repository {name!r} before it exists")
        return self.path(name)

    def git(self, repo: Path, *arguments: str, when: datetime | None = None) -> str:
        dates = {}
        if when:
            dates = {"GIT_AUTHOR_DATE": f"{int(when.timestamp())} +0000"}
            dates["GIT_COMMITTER_DATE"] = dates["GIT_AUTHOR_DATE"]
        result = subprocess.run(
            ["git", *SETTINGS_OFF, *arguments],
            cwd=repo,
            env=git_environment(**IDENTITY, **dates),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            raise SystemExit(f"git {' '.join(arguments)} failed in {repo}: {result.stderr.strip()}")
        return result.stdout

    def resolve(self, repo: str, revision: str) -> str:
        return self.git(self.repo(repo), "rev-parse", "--verify", "-q", f"{revision}^{{commit}}").strip()

    def render(self, text: str) -> str:
        """Fill in the times and revisions of a file's templates; an unknown template is an error."""

        def replace(match: re.Match) -> str:
            name = match.group(1).strip()
            if now := NOW_TEMPLATE.fullmatch(name):
                minutes = int(now[2] or 0) * (-1 if now[1] == "-" else 1)
                return (self.now + timedelta(minutes=minutes)).strftime(TIME_FORMAT)
            if found := REVISION_TEMPLATE.fullmatch(name):
                sha = self.resolve(found[2], found[3])
                return sha if found[1] == "sha" else sha[:7]
            raise SystemExit(f"unknown template {{{{{name}}}}}")

        return TEMPLATE.sub(replace, text)

    def apply_commits(self, repo: Path, commits: list[dict]) -> None:
        """Commit each entry on the checked-out branch.

        An entry's `files` directory is copied over the tree, its `delete` paths are removed, and the
        commit ends 20 minutes before preparation and 10 minutes after the entry before it, unless
        the entry sets `minutes_ago`.
        """
        for index, entry in enumerate(commits):
            if "files" in entry:
                copy_tree(self.files / entry["files"], repo)
            for deleted in entry.get("delete", []):
                (repo / relative_path(deleted)).unlink()
            minutes = entry.get("minutes_ago", 20 + 10 * (len(commits) - 1 - index))
            self.git(repo, "add", "-A")
            self.git(repo, "commit", "-q", "-m", entry["message"], when=self.now - timedelta(minutes=minutes))

    def on_branch(self, repo: Path, branch: str, commits: list[dict], create_from: str | None = None) -> None:
        """Commit on a branch, then check the original one out again."""
        original = self.git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        self.git(repo, "checkout", "-q", *(["-b", branch, create_from] if create_from else [branch]))
        self.apply_commits(repo, commits)
        self.git(repo, "checkout", "-q", original)

    def apply_repo(self, fixture: dict) -> None:
        repo = self.path(fixture["path"])
        repo.mkdir(parents=True)
        self.git(repo, "init", "-q", "-b", "main", "--template=")
        self.manifest["repos"].append(fixture["path"])
        self.apply_commits(repo, fixture["commits"])

    def apply_remote(self, fixture: dict) -> None:
        repo, bare = self.repo(fixture["repo"]), self.path(fixture["path"])
        bare.mkdir(parents=True)
        self.git(bare, "init", "-q", "--bare", "-b", "main", "--template=")
        self.git(repo, "remote", "add", "origin", str(bare))
        self.git(repo, "push", "-q", "-u", "origin", "--all")
        self.manifest["remotes"].append(fixture["path"])

    def apply_branch(self, fixture: dict) -> None:
        repo = self.repo(fixture["repo"])
        if fixture.get("commits"):
            self.on_branch(repo, fixture["name"], fixture["commits"], create_from=fixture["from"])
        else:
            self.git(repo, "branch", fixture["name"], fixture["from"])

    def apply_commits_kind(self, fixture: dict) -> None:
        self.on_branch(self.repo(fixture["repo"]), fixture["branch"], fixture["commits"])

    def apply_worktree(self, fixture: dict) -> None:
        repo, path = self.repo(fixture["repo"]), self.path(fixture["path"])
        self.git(repo, "worktree", "add", "-q", str(path), fixture["branch"])
        if "uncommitted" in fixture:
            copy_tree(self.files / fixture["uncommitted"], path)
        self.manifest["worktrees"].append(fixture["path"])

    def apply_stash(self, fixture: dict) -> None:
        repo = self.repo(fixture["repo"])
        copy_tree(self.files / fixture["files"], repo)
        self.git(repo, "stash", "push", "-q", "--include-untracked", "-m", fixture["message"])

    def apply_file(self, fixture: dict) -> None:
        source = self.files / relative_path(fixture["source"])
        target = self.path(fixture["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render(source.read_text(encoding="utf-8")), encoding="utf-8")

    def apply_process(self, fixture: dict) -> None:
        self.manifest["processes"].append(
            {key: fixture.get(key, ".") if key == "cwd" else fixture[key] for key in ("name", "command", "cwd", "seconds")}
        )

    def apply(self, fixture: dict) -> None:
        kind = fixture["kind"]
        getattr(self, "apply_commits_kind" if kind == "commits" else f"apply_{kind}")(fixture)


def prepare_workspace(scenario: Path, workspace: Path, now: datetime | None = None) -> dict:
    """Apply a scenario's fixtures to an empty workspace and return the manifest of what it holds.

    Preparation happens just before a launch, so that relative times do not drift with the order
    of the runs. `now` is the time that templates and commit dates count from.
    """
    spec = json.loads((scenario / "scenario.json").read_text(encoding="utf-8"))
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    fixtures = Fixtures(scenario / "files", workspace, stamp)
    for fixture in spec["fixtures"]:
        fixtures.apply(fixture)
    return fixtures.manifest


# Files up to this size keep their text in a snapshot, so that the lines an agent added can be
# found afterwards; files up to the second size are hashed.
MAX_TEXT = 100_000
MAX_HASHED = 50_000_000


def file_entry(path: Path) -> dict:
    """Describe a file without following links: its size and hash, and its text when it is small."""
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            return {"link": os.readlink(path)}
        if not stat.S_ISREG(info.st_mode):
            return {"special": stat.S_IFMT(info.st_mode)}
        if info.st_size > MAX_HASHED:
            return {"size": info.st_size, "sha256": None}
        data = path.read_bytes()
    except OSError as error:
        return {"unreadable": error.strerror}
    entry = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if len(data) <= MAX_TEXT:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return entry
        entry["text"] = None if "\0" in text else text
    return entry


def workspace_files(workspace: Path, skip: set[Path]) -> dict[str, dict]:
    """Describe every file of the workspace except Git's own data and the directories in `skip`.

    Contents are read directly. Running `git status` instead would run any filter or fsmonitor
    command that the agent configured, on the maintainer's machine.
    """
    files = {}
    for directory, names, filenames in os.walk(workspace):
        here = Path(directory)
        linked = [name for name in names if (here / name).is_symlink()]
        names[:] = sorted(n for n in names if n != ".git" and n not in linked and here / n not in skip)
        for name in sorted(filenames + linked):
            if name != ".git":
                files[(here / name).relative_to(workspace).as_posix()] = file_entry(here / name)
    return files


def git_dir(workspace: Path, relative: str) -> Path | None:
    """Return a recorded repository's Git directory if it is a real directory inside the workspace.

    The agent can replace `.git` with a link or a file that points anywhere, so the check runs
    again before every read, on the path as it is now.
    """
    inside = workspace.resolve()
    for candidate in (workspace / relative / ".git", workspace / relative):
        if candidate.is_dir() and not candidate.is_symlink() and (candidate / "HEAD").is_file():
            return candidate if candidate.resolve().is_relative_to(inside) else None
    return None


def redirection(directory: Path) -> str | None:
    """Name what in a Git directory would make Git read refs, objects, or configuration elsewhere.

    A `commondir` file turns the directory into a linked worktree's, so Git takes refs, objects, and
    configuration from the directory it names; an `alternates` file adds object stores; a symbolic
    link anywhere inside points a part of it away. A snapshot read through any of them could record
    another repository's state, or files from outside the workspace. A linked worktree's own
    `commondir` must lead back to this directory.
    """
    for name in ("commondir", "objects/info/alternates"):
        if (directory / name).exists() or (directory / name).is_symlink():
            return f"its Git directory holds {name}, which can lead Git outside it"
    for root, folders, files in os.walk(directory):
        for name in folders + files:
            if (Path(root) / name).is_symlink():
                return f"its Git directory holds a symbolic link: {(Path(root) / name).relative_to(directory)}"
    for entry in sorted((directory / "worktrees").glob("*/commondir")):
        target = entry.parent / entry.read_text(encoding="utf-8", errors="replace").strip()
        if target.resolve() != directory.resolve():
            return f"the commondir of worktree {entry.parent.name} leads out of the repository"
    return None


def read_git(directory: Path, *arguments: str, work_tree: Path | None = None) -> str | None:
    """Run a Git plumbing command on exactly this Git directory; None when it fails.

    Only commands that read refs, objects, and ignore rules are used here: they do not run
    the filters, hooks, or fsmonitor that the agent's repository configuration can name. A command
    that lists files needs the work tree too.

    A command that reads an object can still fetch it: a repository that names a promisor remote
    fetches a missing object, through the `core.sshCommand` or `remote.*.uploadpack` that its
    configuration names, and that command runs on this machine (reproduced with `rev-list`,
    `cat-file`, and `ls-tree` on Git 2.43). `GIT_ALLOW_PROTOCOL=none` overrides any `protocol.*`
    setting, so every transport is refused and the read fails instead.
    """
    variables = {"GIT_DIR": str(directory), "GIT_OPTIONAL_LOCKS": "0", "GIT_ALLOW_PROTOCOL": "none"}
    result = subprocess.run(
        ["git", *SETTINGS_OFF, "-c", "core.fsmonitor=false", *arguments],
        cwd=work_tree or directory,
        env=git_environment(**variables, **({"GIT_WORK_TREE": str(work_tree)} if work_tree else {})),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # a name or a file that is not UTF-8 must not stop the snapshot
        timeout=60,
    )
    return result.stdout if result.returncode == 0 else None


def ignored_files(git_directory: Path, work_tree: Path, workspace: Path) -> list[str]:
    """List the untracked files of a work tree that its ignore rules exclude, as paths in the workspace.

    The rules are the .gitignore files in the tree and the repository's info/exclude. Git reads them
    as patterns and runs nothing. A work tree that is a link, or leaves the workspace, lists nothing.
    """
    inside = workspace.resolve()
    if work_tree.is_symlink() or not work_tree.is_dir() or not work_tree.resolve().is_relative_to(inside):
        return []
    listing = read_git(git_directory, "ls-files", "--others", "--ignored", "--exclude-standard", "-z", work_tree=work_tree)
    base = work_tree.resolve().relative_to(inside)
    return [(base / name).as_posix() for name in (listing or "").split("\0") if name]


STASH_ENTRY = re.compile(r"[0-9a-f]{40,64} ([0-9a-f]{40,64}) [^\t]*\t(.*)")


def read_stash(directory: Path) -> list[dict]:
    """Read the stash entries from the reflog file, newest first.

    `git reflog` walks the commits with the repository's own log settings. With `log.showSignature`
    on and a `gpg.program` in the repository's configuration, a signed commit in the stash would run
    the agent's program on this machine (reproduced with `git reflog show refs/stash`). The file is
    only text, and a link or a file outside the Git directory is not read.
    """
    log = directory / "logs" / "refs" / "stash"
    if log.is_symlink() or not log.is_file() or not log.resolve().is_relative_to(directory.resolve()):
        return []
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    entries = (STASH_ENTRY.fullmatch(line) for line in reversed(lines))
    return [{"commit": found[1], "subject": found[2]} for found in entries if found]


def read_repository(directory: Path, workspace: Path) -> dict:
    """Read the refs, the stash, the worktrees, and the ignored files of one Git directory.

    Each worktree records the commit that its HEAD resolves to, besides the HEAD itself, because a
    commit moves the branch and leaves the HEAD file as it was.
    """
    refs = {}
    for line in (read_git(directory, "for-each-ref", "--format=%(refname)%09%(objectname)") or "").splitlines():
        name, _, sha = line.partition("\t")
        refs[name] = sha
    stash = read_stash(directory)
    worktrees, ignored = [], []
    if directory.name == ".git":
        ignored += ignored_files(directory, directory.parent, workspace)
    for entry in sorted((directory / "worktrees").glob("*/gitdir")):
        pointer = Path(entry.read_text(encoding="utf-8", errors="replace").strip()).parent
        head = (entry.parent / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        try:
            location = pointer.relative_to(workspace).as_posix()
        except ValueError:
            location = str(pointer)
        commit = refs.get(head.removeprefix("ref: ")) if head.startswith("ref: ") else head
        worktrees.append({"path": location, "head": head, "commit": commit})
        ignored += ignored_files(entry.parent, pointer, workspace)
    head = (directory / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    trees, blobs = branch_trees(directory, refs)
    return {"head": head, "refs": refs, "stash": stash, "worktrees": worktrees, "ignored": sorted(set(ignored)),
            "trees": trees, "blobs": blobs}


MAX_TREES = 40
MAX_TREE_ENTRIES = 500


def branch_trees(directory: Path, refs: dict[str, str]) -> tuple[dict, dict]:
    """Read the files at the tip of each branch: a path-to-blob map per branch, and each blob's text.

    `ls-tree` and `cat-file blob` read objects and apply no filter or text conversion, so the
    repository's configuration runs nothing. A branch past the first MAX_TREES, a tip that is not a
    commit, or a tree of more than MAX_TREE_ENTRIES files has no map; a blob over MAX_TEXT bytes has
    no text. Blobs are recorded once, however many branches hold them.
    """
    trees, blobs = {}, {}
    for number, name in enumerate(sorted(n for n in refs if n.startswith("refs/heads/"))):
        listing = read_git(directory, "ls-tree", "-r", "-l", "-z", refs[name]) if number < MAX_TREES else None
        entries = [entry for entry in (listing or "").split("\0") if entry]
        if listing is None or len(entries) > MAX_TREE_ENTRIES:
            trees[name] = None
            continue
        tree = {}
        for entry in entries:
            meta, _, path = entry.partition("\t")
            fields = meta.split()
            if len(fields) != 4 or fields[1] != "blob":
                continue  # a submodule's commit has no file to read
            tree[path] = fields[2]
            if fields[2] not in blobs:
                small = fields[3].isdigit() and int(fields[3]) <= MAX_TEXT
                blobs[fields[2]] = read_git(directory, "cat-file", "blob", fields[2]) if small else None
        trees[name] = tree
    return trees, blobs


def commits_added(directory: Path, before: dict, repo: dict) -> dict[str, int]:
    """Count, for each branch that moved, the commits that are now on it and were not before.

    A branch that no longer contains its earlier tip counts -1, as one that could not be counted
    does: it was rewound or rewritten, which no count of added commits describes.
    """
    added = {}
    for name, sha in repo["refs"].items():
        old = before["refs"].get(name)
        if name.startswith("refs/heads/") and old and old != sha:
            kept = read_git(directory, "merge-base", "--is-ancestor", old, sha) is not None
            count = read_git(directory, "rev-list", "--count", f"{old}..{sha}") if kept else None
            added[name] = int(count) if count and count.strip().isdigit() else -1
    return added


def take_snapshot(workspace: Path, manifest: dict, before: dict | None = None) -> dict:
    """Record the workspace's files and the refs, stash, and worktrees of its recorded repositories.

    A repository whose Git directory is not a real directory inside the workspace, or could make Git
    read from elsewhere, is not read and is named in `problems`. Given the snapshot from before the
    run, the one after it also counts the commits added to each branch.
    """
    skip = {workspace / relative for relative in manifest["remotes"]}
    snapshot = {"files": workspace_files(workspace, skip), "repos": {}, "problems": []}
    for relative in [*manifest["repos"], *manifest["remotes"]]:
        directory = git_dir(workspace, relative)
        problem = "no Git directory inside the workspace" if directory is None else redirection(directory)
        if problem:
            snapshot["problems"].append(f"{relative}: {problem}")
            continue
        repo = read_repository(directory, workspace)
        if before and relative in before["repos"]:
            repo["added"] = commits_added(directory, before["repos"][relative], repo)
        snapshot["repos"][relative] = repo
    return snapshot


LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+")
TABLE_RULE = re.compile(r"[|\s:-]+")
HEADING = re.compile(r"#{1,6}(?:\s|$)")
# A line of bold text alone, such as `**Front B**` or `**Front B:**`, labels what follows it.
BOLD_LABEL = re.compile(r"(\*\*|__)[^*_]+\1:?")
# So does a short unindented line that ends with a colon, such as `Front B:` or `NOT CHECKED:`.
PLAIN_LABEL = re.compile(r"(?![-*+]\s|\d+[.)]\s)[^\s|].{0,58}:")
QUOTE_MARKS = re.compile(r"\s*(?:>\s?)+")
# Words saying that the agent did not establish what it wrote. A seed that matches only through
# such a sentence, or under such a heading, is flagged for a person to read, not matched.
HEDGE = re.compile(
    r"\b(?:(?:could|can|did|do|does|have|has|was|were)(?:\s+not\b|n[o’']t\b)|unable to|not yet)\s+(?:\w+\s+){0,2}?"
    r"(?:verif|check|confirm|determin|establish|inspect)\w*"
    r"|\b(?:unverified|unchecked|unconfirmed|not (?:verified|checked|confirmed|established|inspected))\b",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A short label that opens a paragraph or an item, such as `**Front C:**`, names its subject.
LEADING_LABEL = re.compile(r"(?:[-*+]|\d+[.)])?\s*([^:.!?|]{1,40}):(?:\*\*|__)?\s")
# Where a unit's body splits into the parts that a bound finding is read in: sentences and cells.
CLAUSE_END = re.compile(r"(?<=[.!?])\s+|\|")
# A longer unit is flagged for a person to read, not matched.
MAX_UNIT = 600
MIN_SHA = 7


class Unit(NamedTuple):
    """A stretch of text inside which all of a seed's patterns must match."""

    text: str
    kind: str  # paragraph, table row, list item, or section
    heading: str = ""  # the nearest heading above it
    subject: str = ""  # what the unit is about: a row's first cell, an item's first line, or a section's heading


def is_heading(line: str) -> bool:
    """Say whether a stripped line is a Markdown heading or a bold label on a line of its own."""
    return bool(HEADING.match(line) or BOLD_LABEL.fullmatch(line))


def line_kind(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "blank"
    if is_heading(stripped) or (line == line.lstrip() and PLAIN_LABEL.fullmatch(stripped)):
        return "heading"
    if stripped.startswith("|"):
        return "rule" if TABLE_RULE.fullmatch(stripped) else "table"
    return "item" if LIST_ITEM.match(line) else "text"


def unquoted(text: str) -> list[str]:
    """Return the lines of a text without the quote markers that begin them, tabs expanded."""
    return [QUOTE_MARKS.sub("", raw.expandtabs(4), count=1).rstrip() if raw.lstrip().startswith(">")
            else raw.expandtabs(4).rstrip() for raw in text.splitlines()]


def item_end(lines: list[str], kinds: list[str], start: int) -> int:
    """Return the line after a list item: its continuation lines and everything nested under it."""
    depth, end, blank = len(lines[start]) - len(lines[start].lstrip()), start + 1, False
    for number in range(start + 1, len(lines)):
        if kinds[number] == "blank":
            blank = True
        elif kinds[number] in ("heading", "table", "rule"):
            break
        elif (kinds[number] == "item" or blank) and len(lines[number]) - len(lines[number].lstrip()) <= depth:
            break
        else:
            end, blank = number + 1, False
    return end


def located_units(text: str) -> tuple[list[str], list[tuple[int, int, Unit]]]:
    """Return the lines of a text and its units, each with its first line and its heading's line (-1 if none)."""
    lines = unquoted(text)
    kinds = [line_kind(line) for line in lines]
    above, last = [], -1
    for number, kind in enumerate(kinds):
        last = number if kind == "heading" else last
        above.append(last)

    def unit(start: int, words: str, kind: str, subject: str = "") -> tuple[int, int, Unit]:
        heading, label = above[start], LEADING_LABEL.match(words)
        subject = subject or (label.group(1) if label and kind != "table row" else "")
        return start, heading, Unit(words, kind, lines[heading].strip() if heading >= 0 else "", subject)

    found: list[tuple[int, int, Unit]] = []
    covered: set[int] = set()
    for start, kind in enumerate(kinds):
        if kind == "item":
            end = item_end(lines, kinds, start)
            covered.update(range(start, end))
            words = " ".join(line.strip() for line in lines[start:end] if line.strip())
            found.append(unit(start, words, "list item", lines[start].strip() if words != lines[start].strip() else ""))
        elif kind == "table":
            cells = [cell.strip() for cell in lines[start].strip().strip("|").split("|")]
            found.append(unit(start, lines[start].strip(), "table row", next((cell for cell in cells if cell), "")))
    paragraph: list[int] = []
    for number in range(len(lines) + 1):
        if number < len(lines) and kinds[number] == "text" and number not in covered:
            paragraph.append(number)
        elif paragraph:
            found.append(unit(paragraph[0], " ".join(lines[n].strip() for n in paragraph), "paragraph"))
            paragraph = []
    return lines, sorted(found, key=lambda entry: entry[0])


def split_units(text: str) -> list[Unit]:
    """Split text into paragraphs, table rows, and list items, each item with its nested items.

    A nested item is a unit too, so a short item can match inside a long parent. Quote markers do
    not count. Headings, and labels on a line of their own, belong to no unit; `split_sections`
    reads them.
    """
    return [unit for _, _, unit in located_units(text)[1]]


def split_sections(text: str) -> list[Unit]:
    """Pair each heading with each unit under it, up to the next heading.

    A heading gives the units under it their subject, as `## Front C` does to `- conflicts with
    main`. Two units under one heading never join, so unrelated items cannot add up to a seed. A
    heading with no unit under it stands alone.
    """
    lines, units = located_units(text)
    sections = []
    for number, line in enumerate(lines):
        if line_kind(line) != "heading":
            continue
        under = [unit for _, heading, unit in units if heading == number]
        sections += [Unit(f"{line.strip()} {unit.text}", "section", unit.heading, line.strip()) for unit in under]
        sections += [] if under else [Unit(line.strip(), "section", line.strip())]
    return sections


def plain_line(line: str) -> str:
    """Return a line without its quote and list markers, so that a quoted or re-listed copy compares equal."""
    line = QUOTE_MARKS.sub("", line, count=1) if line.lstrip().startswith(">") else line
    return LIST_ITEM.sub("", line, count=1).strip() if LIST_ITEM.match(line) else line.strip()


def known_lines(snapshot: dict, task: str = "") -> set[str]:
    """Return every line, plain, of every text file that a snapshot holds and of the task."""
    texts = [entry["text"] for entry in snapshot["files"].values() if isinstance(entry.get("text"), str)]
    return {plain_line(line) for text in [*texts, task] for line in text.splitlines()} - {""}


def new_blocks(text: str, known: set[str]) -> list[str]:
    """Return the runs of lines of `text` that are not in `known`; blank lines stay inside a run.

    A known heading stays in a run that has new lines, since it gives them their subject.
    """
    blocks, run = [], []
    for line in [*text.splitlines(), None]:
        new = line is not None and plain_line(line) not in known
        if new or (line is not None and line_kind(unquoted(line)[0]) == "heading"):
            run.append((line, new and bool(line.strip())))
            continue
        while run and not run[-1][1]:
            run.pop()
        if run:
            blocks.append("\n".join(entry for entry, _ in run))
        run = []
    return blocks


def revision_sha(snapshot: dict, repo: str, revision: str) -> str:
    """Resolve a branch, tag, remote branch, `HEAD`, or full SHA against a recorded snapshot."""
    state = snapshot["repos"].get(repo)
    if state is None:
        raise SystemExit(f"the snapshot has no repository {repo!r}")
    if revision == "HEAD":
        head = state["head"]
        revision = head.removeprefix("ref: ") if head.startswith("ref: ") else head
    if re.fullmatch(r"[0-9a-f]{40}", revision):
        return revision
    for prefix in ("", "refs/heads/", "refs/tags/", "refs/remotes/", "refs/remotes/origin/"):
        if sha := state["refs"].get(prefix + revision):
            return sha
    raise SystemExit(f"cannot resolve {revision!r} in {repo!r} from the recorded refs")


def sha_pattern(sha: str) -> str:
    """Match the SHA or any prefix of it from seven characters on."""
    tail = ""
    for character in reversed(sha[MIN_SHA:]):
        tail = f"(?:{character}{tail})?"
    return rf"\b{sha[:MIN_SHA]}{tail}\b"


NEAR_FIELDS = {"subject", "finding", "others", "within"}


def near_source(entry: str | list | dict) -> str:
    """Return the expression that a `near` entry stands for.

    An entry is an expression, a list of pieces joined into one, or an object that finds `subject`
    and `finding` in either order, at most `within` characters apart (200 by default), with nothing
    between them that matches `others`, such as the name of another front.
    """
    if isinstance(entry, list):
        return "".join(entry)
    if isinstance(entry, dict):
        subject, finding = near_source(entry["subject"]), near_source(entry["finding"])
        gap = f"(?:(?!{near_source(entry.get('others', '(?!)'))}).){{0,{int(entry.get('within', 200))}}}?"
        return f"(?:{subject}){gap}(?:{finding})|(?:{finding}){gap}(?:{subject})"
    return entry


class Near(NamedTuple):
    """A compiled `near` entry; an object entry keeps its parts, so that a unit's subject can bind them."""

    pattern: re.Pattern
    subject: re.Pattern | None = None
    finding: re.Pattern | None = None
    others: re.Pattern | None = None

    def matches(self, unit: Unit) -> bool:
        """Say whether the entry matches the unit.

        An object entry also matches when the unit's subject, such as the first cell of a row about
        front C, names its subject and no other, and one sentence or cell of the rest names the
        finding and no other subject. A long row about one front can then mention another in passing.
        """
        if self.pattern.search(unit.text):
            return True
        if self.subject is None or not self.subject.search(unit.subject):
            return False
        if self.others is not None and self.others.search(unit.subject):
            return False
        body = unit.text.replace(unit.subject, " ", 1)
        return any(self.finding.search(part) and not (self.others is not None and self.others.search(part))
                   for part in CLAUSE_END.split(body))


def compile_near(entry: str | list | dict, before: dict) -> Near:
    """Compile a `near` entry; its sha and short templates resolve against the snapshot before the run."""

    def compiled(part: str | list | dict) -> re.Pattern:
        pattern = near_source(part)

        def replace(match: re.Match) -> str:
            found = REVISION_TEMPLATE.fullmatch(match.group(1).strip())
            if not found:
                raise SystemExit(f"unknown template {match.group(0)} in {pattern!r}")
            return sha_pattern(revision_sha(before, found[2], found[3]))

        return re.compile(TEMPLATE.sub(replace, pattern), re.IGNORECASE)

    if not isinstance(entry, dict):
        return Near(compiled(entry))
    others = compiled(entry["others"]) if "others" in entry else None
    return Near(compiled(entry), compiled(entry["subject"]), compiled(entry["finding"]), others)


def written_texts(
    source: list[str] | str, report: str, before: dict, after: dict, known: set[str] | None = None
) -> list[tuple[str, str]]:
    """Return the text the agent wrote in the places a seed looks at, with where each came from.

    The report and the workspace files count only through their lines that neither the task nor a
    file of the snapshot before the run contains, so words that the agent quoted, moved, or copied
    from its inputs never match by themselves.
    """
    known = known_lines(before) if known is None else known
    texts = []
    for entry in [source] if isinstance(source, str) else source:
        if entry == "report":
            texts += [("report", block) for block in new_blocks(report, known)]
            continue
        for name, now in sorted(after["files"].items()):
            if not fnmatch.fnmatchcase(name, entry) or not isinstance(now.get("text"), str):
                continue
            texts += [(name, block) for block in new_blocks(now["text"], known)]
    return texts


def hedged(unit: Unit, nears: list[Near]) -> bool:
    """Say whether a unit matches only through a sentence, or under a heading, that hedges."""
    if HEDGE.search(unit.heading):
        return True
    firm = " ".join(sentence for sentence in SENTENCE_END.split(unit.text) if not HEDGE.search(sentence))
    return not all(near.matches(unit._replace(text=firm)) for near in nears)


def detect(seeds: list[dict], report: str, before: dict, after: dict, task: str = "") -> list[dict]:
    """Say which seeds the agent's text names: all `near` entries must match inside one unit.

    A unit is a paragraph, a table row, or a list item with its nested items; its subject can bind
    an object entry (`Near.matches`). When a seed matches no
    unit, a heading joined to one unit under it counts too. A unit over `MAX_UNIT` characters, or
    one that matches only where the agent says it did not verify, is flagged for a person to read,
    not matched, and only when nothing else matched. Each match says which kind it was.
    """
    results, known = [], known_lines(before, task)
    for seed in seeds:
        nears = [compile_near(entry, before) for entry in seed["near"]]
        texts = written_texts(seed["source"], report, before, after, known)
        found, flagged = [], []
        for split in (split_units, split_sections):
            for origin, text in texts:
                for unit in split(text):
                    if not all(near.matches(unit) for near in nears):
                        continue
                    entry = {"origin": origin, "unit": unit.text, "kind": unit.kind}
                    if len(unit.text) > MAX_UNIT + (len(unit.heading) if unit.kind == "section" else 0):
                        flagged.append({**entry, "why": "long"})
                    elif hedged(unit, nears):
                        flagged.append({**entry, "why": "hedged"})
                    else:
                        found.append(entry)
            if found:
                break
        results.append({"id": seed["id"], "kind": seed["kind"], "found": bool(found), "units": found[:3]})
        if flagged and not found:
            results[-1]["flagged"] = flagged[:3]
    return results


def signature(entry: dict | None) -> tuple:
    """Compare files by what they hold, not by the text a snapshot keeps for small ones."""
    return tuple(sorted((k, v) for k, v in (entry or {"absent": True}).items() if k != "text"))


def ignored_in(snapshot: dict) -> set[str]:
    """Return the untracked files that the ignore rules of the snapshot's repositories exclude."""
    return {path for repo in snapshot["repos"].values() for path in repo.get("ignored", [])}


def visible_files(snapshot: dict) -> dict[str, dict]:
    """Return the snapshot's files without the untracked ones that its ignore rules exclude.

    Running a project's tests writes caches that its ignore rules name; that is not a change.
    """
    ignored = ignored_in(snapshot)
    return {name: entry for name, entry in snapshot["files"].items() if name not in ignored}


def changed_files(before: dict, after: dict, prefix: str = "") -> list[str]:
    was, now = visible_files(before), visible_files(after)
    names = {n for n in [*was, *now] if n.startswith(prefix)}
    return sorted(n for n in names if signature(was.get(n)) != signature(now.get(n)))


def listed(values) -> list[str]:
    return [values] if isinstance(values, str) else list(values)


def ref_changes(before: dict, after: dict, only: list[str], skip: list[str]) -> list[str]:
    """Describe the refs that were created, deleted, or moved, among those selected by glob."""

    def selected(name: str) -> bool:
        wanted = not only or any(fnmatch.fnmatchcase(name, pattern) for pattern in only)
        return wanted and not any(fnmatch.fnmatchcase(name, pattern) for pattern in skip)

    changes = []
    for name in sorted(set(before) | set(after)):
        if selected(name) and before.get(name) != after.get(name):
            kind = "created" if name not in before else "deleted" if name not in after else "moved"
            changes.append(f"{name}: {kind}")
    return changes


def repository(snapshot: dict, name: str) -> dict:
    return snapshot["repos"].get(name) or {"refs": {}, "stash": [], "worktrees": []}


def stash_kept(argument: dict, before: dict, after: dict, processes: dict | None) -> str | None:
    entries = repository(before, argument["repo"])["stash"]
    original = next((e for e in entries if e["subject"].endswith(argument["message"])), None)
    if original is None:
        return "the prepared workspace has no such stash entry"
    if original not in repository(after, argument["repo"])["stash"]:
        return "the stash entry is gone or points at another commit"
    return None


def worktree_unchanged(argument: str, before: dict, after: dict, processes: dict | None) -> str | None:
    """Check a worktree's HEAD, the commit that it resolves to, and its files; ignored caches do not count."""
    was = {w["path"]: w for r in before["repos"].values() for w in r["worktrees"]}
    now = {w["path"]: w for r in after["repos"].values() for w in r["worktrees"]}
    if argument not in was:
        return "the prepared workspace has no such worktree"
    if argument not in now or now[argument]["head"] != was[argument]["head"]:
        return f"the worktree is gone or its HEAD moved: {now.get(argument, {}).get('head', 'absent')}"
    if now[argument].get("commit") != was[argument].get("commit"):
        old, new = (str(entry.get("commit"))[:7] for entry in (was[argument], now[argument]))
        return f"the commit that its HEAD resolves to changed: {old} to {new}"
    changed = changed_files(before, after, argument.rstrip("/") + "/")
    return f"files changed: {', '.join(changed[:5])}" if changed else None


def refs_unchanged(argument: str | dict, before: dict, after: dict, processes: dict | None) -> str | None:
    spec = {"repo": argument} if isinstance(argument, str) else argument
    if spec["repo"] not in before["repos"] or spec["repo"] not in after["repos"]:
        return f"the repository {spec['repo']!r} could not be read"
    was, now = before["repos"][spec["repo"]]["refs"], after["repos"][spec["repo"]]["refs"]
    changes = ref_changes(was, now, listed(spec.get("only", [])), listed(spec.get("except", [])))
    return "; ".join(changes[:6]) or None


def file_check(argument: str | list[str], before: dict, after: dict, processes: dict | None, unchanged: bool) -> str | None:
    same = lambda name: signature(before["files"].get(name)) == signature(after["files"].get(name))
    bad = [name for name in listed(argument) if same(name) != unchanged]
    return f"{'changed' if unchanged else 'unchanged'}: {', '.join(bad)}" if bad else None


def process_check(argument: str, before: dict, after: dict, processes: dict | None, alive: bool) -> str | None:
    status = (processes or {}).get(argument)
    if status is None:
        return "the launcher has no record of this process"
    if (status["state"] == "alive") != alive:
        return f"the process is {status['state']}" + (f" ({status['signal']})" if status.get("signal") else "")
    return None


def new_entries(argument, before: dict, after: dict, processes: dict | None, what: str) -> str | None:
    new = []
    for name in list(before["repos"]) if argument is True else listed(argument):
        was, now = repository(before, name), repository(after, name)
        if what == "worktrees":
            old = {w["path"] for w in was["worktrees"]}
            new += [w["path"] for w in now["worktrees"] if w["path"] not in old]
        else:
            new += [n for n in now["refs"] if n.startswith("refs/heads/") and n not in was["refs"]]
    return f"new: {', '.join(new)}" if new else None


def commits_added_check(argument: dict, before: dict, after: dict, processes: dict | None) -> str | None:
    if argument["repo"] not in after["repos"]:
        return f"the repository {argument['repo']!r} could not be read"
    count = after["repos"][argument["repo"]].get("added", {}).get(f"refs/heads/{argument['branch']}", 0)
    if count < 0:
        return "the branch no longer contains its earlier tip, or its commits could not be counted"
    low = argument.get("count", argument.get("min", 0))
    high = argument.get("count", argument.get("max", count))
    return None if low <= count <= high else f"{count} commits added, expected {low} to {high}"


def branch_lacks(argument: dict, before: dict, after: dict, processes: dict | None) -> str | None:
    """Check that a file at a branch's tip does not match a pattern; a file that cannot be read fails.

    It holds however the change arrived: a merge, a cherry-pick, a squash, or a copy by hand. A
    file that is missing lacks the pattern, unless `present_before` says that the check asks for a
    repair: removing or moving the file is not one. A file that is there and empty lacks it too.
    """
    repo = after["repos"].get(argument["repo"]) or {}
    if repo and "trees" not in repo:
        return "the record holds no branch files: a runner older than this check took it"
    tree = (repo.get("trees") or {}).get(f"refs/heads/{argument['branch']}")
    if tree is None:
        return f"the branch {argument['branch']!r} is gone or its files could not be read"
    path = argument["path"]
    if path not in tree:
        gone = f"{path} is not at the tip of {argument['branch']}: a repair changes the file and leaves it there"
        return gone if argument.get("present_before") else None
    text = repo["blobs"].get(tree[path])
    if text is None:
        return f"{path} at the tip of {argument['branch']} is too large to read"
    found = re.search(argument["pattern"], text, re.IGNORECASE)
    return f"{path} at the tip of {argument['branch']} matches {argument['pattern']!r}: {found[0]!r}" if found else None


def new_files(argument: str | list[str], before: dict, after: dict, inside: bool) -> str | None:
    """List the visible files that are new inside the places given, or outside them; a place is a directory or a file."""
    places = [place.rstrip("/") for place in listed(argument)]
    was = visible_files(before)
    within = lambda name: any(name == place or name.startswith(place + "/") for place in places)
    new = sorted(name for name in visible_files(after) if name not in was and within(name) == inside)
    return f"new files: {', '.join(new[:5])}" if new else None


def no_new_files_outside(argument: str | list[str], before: dict, after: dict, processes: dict | None) -> str | None:
    """Check that no file is new except in the places given: a directory, a file, or a list of them."""
    return new_files(argument, before, after, inside=False)


def no_new_files_inside(argument: str | list[str], before: dict, after: dict, processes: dict | None) -> str | None:
    """Check that no file is new inside the places given; a file anywhere else is free."""
    return new_files(argument, before, after, inside=True)


# Each check returns None when what it asks for holds, else a sentence that says what does not.
STATE_CHECKS = {
    "stash_kept": stash_kept,
    "worktree_unchanged": worktree_unchanged,
    "refs_unchanged": refs_unchanged,
    "file_unchanged": lambda *a: file_check(*a, unchanged=True),
    "file_changed": lambda *a: file_check(*a, unchanged=False),
    "process_alive": lambda *a: process_check(*a, alive=True),
    "process_dead": lambda *a: process_check(*a, alive=False),
    "no_new_worktrees": lambda *a: new_entries(*a, what="worktrees"),
    "no_new_branches": lambda *a: new_entries(*a, what="branches"),
    "commits_added": commits_added_check,
    "branch_lacks": branch_lacks,
    "no_new_files_outside": no_new_files_outside,
    "no_new_files_inside": no_new_files_inside,
}


def check_state(item: dict, before: dict, after: dict, processes: dict | None) -> dict:
    """Evaluate one state assertion; `ok` says that what it asks for holds.

    `processes` maps each `process` fixture to its status from the launcher, or is None when the
    run has no launcher record, which fails the process checks rather than guessing.
    """
    (kind, argument), = item.items()
    if kind not in STATE_CHECKS:
        raise SystemExit(f"unknown state check {kind!r}")
    detail = STATE_CHECKS[kind](argument, before, after, processes)
    return {"check": kind, "argument": argument, "ok": detail is None, "detail": detail or ""}


class Word(NamedTuple):
    """One word of a shell command with its quotes removed; `plain` is false when it expands anything.

    A word that is only one command substitution has `emits`, the text that its command prints,
    when that is plain to know (`"$(cat <<'EOF' ... EOF)"`).
    """

    text: str
    plain: bool
    emits: str | None = None


class ShellCommand:
    """A simple command: its words, its place in a pipeline, its depth in substitutions, and the text it reads."""

    def __init__(self, pipeline: int, position: int) -> None:
        self.words: list[Word] = []
        self.pipeline, self.position = pipeline, position
        self.depth = 0
        self.body: str | None = None  # a here-document or a here-string


REDIRECT = re.compile(r"&>>?|<<<|<<-?|<>|>>|>&|<&|>\||>|<")
WORD_END = " \t\n;&|()<>"


def arithmetic_end(text: str, start: int) -> int | None:
    """Return the index past the `))` of the arithmetic command that `((` begins at `start`.

    None when the parentheses close some other way, as in `((a); (b))`, two subshells in a third.
    """
    depth, inner = 0, None
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 1 and inner is None:
                inner = index  # the first `)` closes the second `(`
            elif depth == 0:
                return index + 1 if inner == index - 1 else None
    return None


class ShellParser:
    """Split shell text into simple commands the way the shell reads it, without running anything.

    Quotes and escapes are removed from words, so the quoted argument of a command is one word of
    that command and never a command of its own. Command substitutions (`$(...)`, backticks, also
    inside double quotes), process substitutions, and subshells are commands. A here-document's
    body, or a here-string's word, is kept as text on the command that reads it, and when the
    delimiter of a here-document is not quoted the shell runs the substitutions in the body, so
    they are commands too. Other redirections and comments are dropped.
    """

    def __init__(self, text: str) -> None:
        self.text, self.index, self.pipelines, self.depth = text, 0, 0, 0
        self.substituted: list[tuple[int, str | None]] = []  # each substitution's depth and the text it prints
        self.commands: list[ShellCommand] = []
        self.heredocs: list[tuple[ShellCommand, str, bool, bool]] = []
        self.parse(closing=False)

    def parse(self, closing: bool) -> None:
        """Read commands to the end of the text, or to the `)` that ends a substitution."""
        self.pipelines += 1
        pipeline, position, command, redirect = self.pipelines, 0, None, None
        end = 0
        while self.index < len(self.text):
            text, char = self.text, self.text[self.index]
            if char in " \t":
                self.index += 1
            elif char == "\\" and text[self.index + 1:self.index + 2] == "\n":
                self.index += 2
            elif char == "#":
                newline = text.find("\n", self.index)
                self.index = len(text) if newline < 0 else newline
            elif char == "\n":
                self.index += 1
                self.read_heredocs()
                self.pipelines += 1
                pipeline, position, command, redirect = self.pipelines, 0, None, None
            elif char == ")" and closing:
                self.index += 1
                return
            elif (char == "(" and text.startswith("((", self.index) and (command is None or all(w.text in ARITHMETIC_AFTER for w in command.words))
                  and (stop := arithmetic_end(text, self.index))):
                self.read_substitutions(text[self.index:stop])  # `(( n = 1 << 3 ))` is no here-document; its `$(...)` runs
                self.index, command, redirect = stop, None, None
            elif char in ";&|()" and not text.startswith("&>", self.index):
                operator = text[self.index:self.index + 2]
                self.index += 2 if operator in ("&&", "||", "|&", ";;") else 1
                command, redirect = None, None
                if operator[0] == "|" and operator != "||":
                    position += 1
                else:
                    self.pipelines += 1
                    pipeline, position = self.pipelines, 0
            elif char in "<>&":
                start = self.index
                operator = REDIRECT.match(text, start).group()
                self.index += len(operator)
                if command is None:
                    command = self.start(pipeline, position)
                if end == start and command.words and command.words[-1].plain and command.words[-1].text.isdigit():
                    command.words.pop()  # the file descriptor of `2>file`
                if operator in ("<", ">") and text.startswith("(", self.index):
                    self.index += 1
                    self.parse(closing=True)  # `<(command)` is a command
                else:
                    redirect = operator
            else:
                begin = self.index
                word = self.read_word()
                end = self.index
                if command is None:
                    command = self.start(pipeline, position)
                if redirect is None:
                    command.words.append(word)
                elif redirect.startswith("<<") and redirect != "<<<":
                    quoted = any(char in text[begin:end] for char in "'\"\\")
                    self.heredocs.append((command, word.text, redirect == "<<-", quoted))
                    redirect = None
                elif redirect == "<<<":
                    command.body, redirect = word.text, None
                else:
                    redirect = None  # the target of a redirection is not an argument

    def start(self, pipeline: int, position: int) -> ShellCommand:
        command = ShellCommand(pipeline, position)
        command.depth = self.depth
        self.commands.append(command)
        return command

    def substitute(self, closing: bool) -> None:
        """Read the commands of a substitution one level deeper, and note the text that they print."""
        level, first = self.depth, len(self.commands)
        self.depth += 1
        self.parse(closing)
        self.depth -= 1
        self.substituted.append((level, printed_by(self.commands[first:], level + 1)))

    def read_heredocs(self) -> None:
        """Read the bodies of the here-documents that the line just ended announced."""
        pending, self.heredocs = self.heredocs, []
        for command, delimiter, strip, quoted in pending:
            lines = []
            while self.index < len(self.text):
                newline = self.text.find("\n", self.index)
                newline = len(self.text) if newline < 0 else newline
                line, self.index = self.text[self.index:newline], newline + 1
                if (line.lstrip("\t") if strip else line) == delimiter:
                    break
                lines.append(line)
            command.body = "\n".join(lines)
            if not quoted:
                self.read_substitutions(command.body)

    def read_substitutions(self, body: str) -> None:
        """Read the substitutions in the body of a here-document whose delimiter is not quoted; the shell runs them."""
        saved = self.text, self.index
        self.text, self.index = body, 0
        while self.index < len(body):
            if body[self.index] == "\\":
                self.index += 2
            elif body[self.index] == "`" or (body.startswith("$(", self.index) and not body.startswith("$((", self.index)):
                self.read_expansion()
            else:
                self.index += 1
        self.text, self.index = saved

    def read_word(self) -> Word:
        pieces, plain, text, mark = [], True, self.text, len(self.substituted)
        while self.index < len(text) and text[self.index] not in WORD_END:
            char = text[self.index]
            if char == "'":
                close = text.find("'", self.index + 1)
                close = len(text) if close < 0 else close
                pieces.append(text[self.index + 1:close])
                self.index = close + 1
            elif char == '"':
                self.index += 1
                piece, quiet = self.read_quoted()
                pieces.append(piece)
                plain = plain and quiet
            elif char == "\\":
                pieces.append(text[self.index + 1:self.index + 2].replace("\n", ""))
                self.index += 2
            elif char in "$`":
                piece, quiet = self.read_expansion()
                pieces.append(piece)
                plain = plain and quiet
            else:
                pieces.append(char)
                self.index += 1
        value = "".join(pieces)
        direct = [printed for level, printed in self.substituted[mark:] if level == self.depth]
        return Word(value, plain, direct[0] if len(direct) == 1 and value in ("$()", "`") else None)

    def read_quoted(self) -> tuple[str, bool]:
        """Read to the closing double quote; substitutions inside still run."""
        pieces, plain, text = [], True, self.text
        while self.index < len(text):
            char = text[self.index]
            if char == '"':
                self.index += 1
                break
            if char == "\\" and text[self.index + 1:self.index + 2] in ("$", "`", '"', "\\", "\n"):
                pieces.append(text[self.index + 1:self.index + 2].replace("\n", ""))
                self.index += 2
            elif char in "$`":
                piece, quiet = self.read_expansion()
                pieces.append(piece)
                plain = plain and quiet
            else:
                pieces.append(char)
                self.index += 1
        return "".join(pieces), plain

    def read_expansion(self) -> tuple[str, bool]:
        """Read a `$` or backtick expansion at the current position; return its text and whether it is plain."""
        text, start = self.text, self.index
        after = text[start + 1:start + 2]
        if text[start] == "`":
            close = start + 1
            while close < len(text) and text[close] != "`":
                close += 2 if text[close] == "\\" else 1
            body = re.sub(r"\\([`\\$])", r"\1", text[start + 1:close])
            self.index = min(close + 1, len(text))
            saved = self.text, self.index
            self.text, self.index = body, 0
            self.substitute(closing=False)
            self.text, self.index = saved
            return "`", False
        if text.startswith("$((", start):
            close = text.find("))", start + 3)
            self.index = len(text) if close < 0 else close + 2
            return "$(())", False
        if after == "(":
            self.index = start + 2
            self.substitute(closing=True)
            return "$()", False
        if after == "{":
            depth, close = 0, start + 1
            while close < len(text):
                depth += (text[close] == "{") - (text[close] == "}")
                if depth == 0:
                    break
                close += 1
            self.index = min(close + 1, len(text))
            return "${}", False
        if after == "'":
            close = start + 2
            while close < len(text) and text[close] != "'":
                close += 2 if text[close] == "\\" else 1
            self.index = min(close + 1, len(text))
            return text[start + 2:close], True
        self.index = start + 1
        return "$", not (after.isalnum() or (after != "" and after in "_@*#?!$-"))


ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}
CONVERSION = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[a-zA-Z%]")


def unescaped(text: str) -> str:
    return re.sub(r"\\([ntr\\\"'])", lambda found: ESCAPES[found[1]], text)


def printf_text(args: list[Word]) -> str | None:
    """Return what `printf` prints: the escapes of its format read, and each conversion replaced by an argument.

    The format starts over while arguments remain, as `printf '%s\\n' a b` prints two lines.
    """
    words = [arg.text for arg in args]
    if words[:1] == ["--"]:
        words = words[1:]
    if not words or words[0] == "-v":  # `-v name` assigns and prints nothing
        return None
    form, queue, out = words[0], words[1:], []
    while True:
        used, position = False, 0
        for found in CONVERSION.finditer(form):
            out.append(unescaped(form[position:found.start()]))
            position = found.end()
            if found[0] == "%%":
                out.append("%")
            else:
                used = True
                out.append(queue.pop(0) if queue else "")
        out.append(unescaped(form[position:]))
        if not (used and queue):
            return "".join(out)


def output_of(command: ShellCommand, slots: dict, depth: int = 0) -> str | None:
    """Return the text that a simple command prints, when it is `echo`, `printf`, or a `cat` or `tee` that passes its input on.

    Anything else prints what the text cannot show, so it prints None.
    """
    resolved = resolve(command.words)
    if resolved is None or depth > MAX_SHELL_DEPTH:
        return None
    name, args, _ = resolved
    if name == "echo":
        words = [arg.text for arg in args]
        while words and re.fullmatch(r"-[neE]+", words[0]):
            words.pop(0)
        return unescaped(" ".join(words))
    if name == "printf":
        return printf_text(args)
    if name == "tee" or (name == "cat" and all(arg.text == "-" for arg in args)):
        return stdin_of(command, slots, depth + 1)
    return None


def stdin_of(command: ShellCommand, slots: dict, depth: int = 0) -> str | None:
    """Return the text that a simple command reads on standard input, when a here-document, a here-string, or the command before it in its pipeline gives it in plain words."""
    if command.body is not None:
        return command.body
    producer = slots.get((command.pipeline, command.position - 1)) if command.position else None
    return output_of(producer, slots, depth) if producer else None


def printed_by(commands: list[ShellCommand], depth: int) -> str | None:
    """Return the text that the commands of a substitution print: the last command of each pipeline at `depth`."""
    slots = {(c.pipeline, c.position): c for c in commands}
    last: dict[int, ShellCommand] = {}
    for command in commands:
        if command.depth == depth and command.position >= getattr(last.get(command.pipeline), "position", -1):
            last[command.pipeline] = command
    printed = [text for text in (output_of(command, slots) for command in last.values()) if text is not None]
    return "\n".join(printed) if printed else None


SHELLS = {"sh", "bash", "dash", "zsh", "ksh", "ash"}
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
ARITHMETIC_AFTER = KEYWORDS | {"for"}  # `for ((i = 0; i < n; i++))` and `if (( n ))` begin with arithmetic
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=")
# Commands that run another command: the short options that take a value, the long ones that do (a
# long option with `=` carries its value), and the operands to skip. The options come from the
# manual of each command; a long option may be abbreviated, and an abbreviation is not read.
WRAPPERS = {
    "sudo": ("ugphCDRTUrt", {"user", "group", "prompt", "host", "close-from", "chdir", "chroot", "command-timeout",
                             "other-user", "role", "type"}, 0),
    "doas": ("uC", set(), 0),
    "env": ("uCS", {"unset", "chdir", "split-string"}, 0),
    "timeout": ("ks", {"kill-after", "signal"}, 1),
    "nice": ("n", {"adjustment"}, 0),
    "ionice": ("cnpPu", {"class", "classdata", "pid", "pgid", "uid"}, 0),
    "stdbuf": ("ioe", {"input", "output", "error"}, 0),
    "nohup": ("", set(), 0), "setsid": ("", set(), 0), "exec": ("a", set(), 0), "command": ("", set(), 0), "builtin": ("", set(), 0),
    "time": ("fo", {"format", "output"}, 0),
    "xargs": ("IEdLnPsa", {"arg-file", "delimiter", "max-args", "max-procs", "max-chars", "process-slot-var"}, 0),
    "busybox": ("", set(), 0),  # `busybox sh` is a shell
    "flock": ("wE", {"timeout", "conflict-exit-code"}, 1),  # the lock file, then a command or `-c` and a string
    "watch": ("nq", {"interval", "equexit"}, 0),  # the words are one string for `sh -c`, unless `-x`
    "parallel": ("jaPnNLlSdEI", {"jobs", "max-procs", "arg-file", "max-args", "max-replace-args", "max-lines", "sshlogin",
                                 "delimiter", "eof", "colsep", "results", "joblog", "timeout", "retries", "delay", "load",
                                 "halt", "tagstring", "workdir", "tmpdir", "header", "trim", "sshloginfile"}, 0),
}
# For the tools that find or signal by name: the options that take a value, short ones and long ones.
VALUED = {
    "pkill": ("PgGstuUTrqF", {"parent", "pgroup", "group", "session", "terminal", "euid", "uid", "ns", "nslist",
                              "runstates", "queue", "pidfile", "signal"}),
    "pgrep": ("PgGstuUTrdF", {"parent", "pgroup", "group", "session", "terminal", "euid", "uid", "ns", "nslist",
                              "runstates", "delimiter", "pidfile"}),
    "killall": ("suyoZ", {"signal", "user", "younger-than", "older-than", "context"}),
    "pidof": ("oS", {"omit-pid", "separator"}),
}
FILTERS = {"grep", "egrep", "fgrep", "rg", "ag", "awk", "gawk", "mawk"}
MAX_SHELL_DEPTH = 6


def skip_options(words: list[Word], index: int, short: str, long_names: set[str]) -> int:
    """Return the index past the options that start at `index`; `short` lists the short options that take a value."""
    while index < len(words) and words[index].text.startswith("-") and len(words[index].text) > 1:
        option = words[index].text
        index += 1
        if option == "--":
            break
        if option.startswith("--"):
            if "=" not in option and option[2:] in long_names:
                index += 1
        elif len(option) == 2 and option[1] in short:
            index += 1
    return index


def through_shell(words: list[Word], more: str = "") -> tuple[str, list[Word], bool] | None:
    """Read words that a command joins with spaces and hands to `sh -c`, as `sh -c` with that string."""
    if not words:
        return None
    string = Word(" ".join(word.text for word in words) + more, all(word.plain for word in words))
    return "sh", [Word("-c", True), string], False


def su_string(words: list[Word]) -> Word | None:
    """Return the string that `su -c` hands to the user's shell; the option may follow the user's name."""
    index = 0
    while index < len(words):
        text = words[index].text
        index += 1
        if text.startswith("--"):
            name, equals, value = text.partition("=")
            if name in ("--command", "--session-command"):
                return Word(value, words[index - 1].plain) if equals else words[index] if index < len(words) else None
            index += name in ("--group", "--supp-group", "--shell", "--whitelist-environment") and not equals
        elif text.startswith("-") and len(text) > 1:
            for position, letter in enumerate(text[1:], 2):
                if letter == "c":
                    rest = text[position:]
                    return Word(rest, words[index - 1].plain) if rest else words[index] if index < len(words) else None
                if letter in "gGsw":
                    index += not text[position:]
                    break
    return None


def resolve(words: list[Word]) -> tuple[str, list[Word], bool] | None:
    """Find the command that a simple command runs, past assignments, keywords, and wrappers.

    Returns its name, its arguments, and whether `xargs` hands it more arguments on standard input.
    A command that hands a string to a shell (`flock file -c`, `watch`, `su -c`, `parallel`) is the
    shell with that string. `parallel` adds the arguments it reads from its input as one, `$`.
    """
    index, via_xargs = 0, False
    while index < len(words):
        name = words[index].text.rsplit("/", 1)[-1]
        if ASSIGNMENT.match(words[index].text) or name in KEYWORDS:
            index += 1
        elif name in WRAPPERS:
            short, long_names, skipped = WRAPPERS[name]
            via_xargs = via_xargs or name == "xargs"
            index += 1
            if name == "command" and index < len(words) and words[index].text in ("-v", "-V"):
                return None  # it only looks the command up
            first = index
            index = skip_options(words, index, short, long_names) + skipped
            if name == "flock" and words[index:index + 1] and words[index].text in ("-c", "--command"):
                return through_shell(words[index + 1:index + 2])
            if name == "watch" and not any(w.text == "--exec" or re.fullmatch(r"-[a-zA-Z]*x[a-zA-Z]*", w.text) for w in words[first:index]):
                return through_shell(words[index:])
            if name == "parallel":
                end = next((i for i in range(index, len(words)) if words[i].text.startswith(":::")), len(words))
                return through_shell(words[index:end], " $")
        elif name == "su" and (command := su_string(words[index + 1:])) is not None:
            return "sh", [Word("-c", True), command], via_xargs
        else:
            return name, words[index + 1:], via_xargs
    return None


def find_commands(args: list[Word]) -> list[list[Word]]:
    """Return the command of each `-exec`, `-execdir`, `-ok`, and `-okdir` of `find`, up to its `;` or `{} +`."""
    commands, index = [], 0
    while index < len(args):
        if args[index].text in ("-exec", "-execdir", "-ok", "-okdir"):
            end = index + 1
            while end < len(args) and not (args[end].text == ";" or (args[end].text == "+" and args[end - 1].text == "{}")):
                end += 1
            if end < len(args):  # find refuses an -exec with no end
                commands.append(args[index + 1:end])
            index = end
        index += 1
    return commands


def invoked(command: ShellCommand) -> Iterator[tuple[str, list[Word], bool, bool]]:
    """Yield each program that a simple command starts: its name, arguments, `xargs`, and whether it is the command itself.

    That is the command that `resolve` finds and the commands that `find -exec` runs.
    """
    queue = [(command.words, True)]
    while queue:
        words, own = queue.pop(0)
        resolved = resolve(words)
        if resolved is not None:
            yield *resolved, own
            if resolved[0] == "find":
                queue += [(group, False) for group in find_commands(resolved[1])]


def operands(name: str, args: list[Word]) -> list[Word]:
    """Return the arguments of pkill, pgrep, killall, or pidof that are not options or their values."""
    short, long_names = VALUED[name]
    found, index = [], 0
    while index < len(args):
        text = args[index].text
        if text == "--":
            found += args[index + 1:]
            break
        if text.startswith("--"):
            index += 2 if "=" not in text and text[2:] in long_names else 1
        elif text.startswith("-") and len(text) > 1:
            index += 2 if len(text) == 2 and text[1] in short else 1
        else:
            found.append(args[index])
            index += 1
    return found


def sends_signal(args: list[Word], via_xargs: bool) -> bool:
    """Say whether a `kill` signals something other than literal process IDs.

    Listing signals and signal 0, which only checks that a process exists, signal nothing.
    """
    targets, index = [], 0
    while index < len(args):
        text = args[index].text
        if text == "--":
            targets += args[index + 1:]
            break
        if text in ("-l", "-L", "--list", "--table", "-0", "--signal=0"):
            return False
        if text in ("-s", "-n", "--signal"):
            if args[index + 1:index + 2] and args[index + 1].text == "0":
                return False
            index += 2
        elif text.startswith("-") and len(text) > 1 and not targets:
            index += 1
        else:
            targets.append(args[index])
            index += 1
    if via_xargs:
        return True
    return bool(targets) and not all(t.plain and re.fullmatch(r"-?\d+", t.text) for t in targets)


class ShellOptions(NamedTuple):
    """What a shell's options say: `-c` (a string is the script), `-n` (check the syntax only), `-s` (read the script from standard input), and where the operands begin."""

    runs_string: bool
    checks_only: bool
    reads_stdin: bool
    operands: int


def shell_options(args: list[Word]) -> ShellOptions:
    """Read a shell's options. With `-s`, or a lone `-`, the operands are positional parameters and not a script."""
    has_c = checks_only = reads_stdin = False
    index = 0
    while index < len(args):
        text = args[index].text
        if text in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
            index += 2
        elif text == "-":
            reads_stdin, index = True, index + 1
            break
        elif len(text) > 1 and text[0] in "-+" and text != "--":
            if text[0] == "-" and text[1] != "-":
                has_c, checks_only, reads_stdin = has_c or "c" in text, checks_only or "n" in text, reads_stdin or "s" in text
            index += 1
        else:
            break
    if args[index:index + 1] and args[index].text == "--":
        index += 1
    return ShellOptions(has_c, checks_only, reads_stdin, index)


def embedded_script(name: str, args: list[Word], stdin: str | None) -> str | None:
    """Return the shell text that a command hands to a shell, which the shell would run.

    That is the payload of `sh -c` and `bash -c` (also a payload that a substitution prints), the
    arguments of `eval`, or the text on standard input that a shell with no script file, or with
    `-s`, reads: a here-document, a here-string, or what `echo`, `printf`, or `cat` pipes to it. A
    shell given `-n` reads its text and runs nothing.
    """
    if name == "eval":
        return " ".join(arg.text if arg.emits is None else arg.emits for arg in args)
    if name not in SHELLS:
        return None
    options = shell_options(args)
    if options.checks_only:
        return None
    operand = args[options.operands] if options.operands < len(args) else None
    if options.runs_string:
        return None if operand is None else operand.text if operand.emits is None else operand.emits
    return stdin if options.reads_stdin or operand is None else None


def script_file(name: str, args: list[Word]) -> tuple[Word, list[Word]] | None:
    """Return the script file that a shell or `.` runs, with the arguments it gets, or None."""
    if name in (".", "source"):
        return (args[0], args[1:]) if args else None
    if name not in SHELLS:
        return None
    options = shell_options(args)
    if options.runs_string or options.checks_only or options.reads_stdin or options.operands >= len(args):
        return None
    return args[options.operands], args[options.operands + 1:]


def filters_a_listing(members: list[tuple[int, str, list[Word]]]) -> bool:
    """Say whether a pipeline lists processes with `ps` and then filters the listing by a pattern."""
    listed = False
    for _, name, args in sorted(members, key=lambda member: member[0]):
        if name == "ps":
            listed = True
        elif listed and name in FILTERS:
            if not name.endswith("awk") or any(re.search(r"[/~]|\b(?:index|match)\(", a.text) for a in args):
                return True
    return False


def shell_facts(text: str, depth: int = 0) -> set[str]:
    """Say what a Bash call does that bears on killing by pattern.

    The facts are `kill-pattern` (pkill or killall given a name or a pattern), `find` (pgrep, pidof,
    or a filtered `ps` listing, which look for processes by pattern), and `signal` (a kill of
    something other than literal process IDs). A name or pattern that `xargs` supplies counts as
    given. The payloads of `sh -c`, `bash -c`, and `eval` count as part of the call.
    """
    parsed, facts, pipelines = ShellParser(text), set(), {}
    slots = {(c.pipeline, c.position): c for c in parsed.commands}
    for command in parsed.commands:
        for name, args, via_xargs, own in invoked(command):
            pipelines.setdefault(command.pipeline, []).append((command.position, name, args))
            if name in ("pkill", "killall"):
                regexp = name == "killall" and any(a.text in ("-r", "--regexp") for a in args)
                if regexp or via_xargs or operands(name, args):
                    facts.add("kill-pattern")
            elif name in ("pgrep", "pidof"):
                if via_xargs or operands(name, args):
                    facts.add("find")
            elif name == "kill":
                if sends_signal(args, via_xargs):
                    facts.add("signal")
            elif depth < MAX_SHELL_DEPTH:
                script = embedded_script(name, args, stdin_of(command, slots) if own else None)
                if script is not None:
                    facts |= shell_facts(script, depth + 1)
    if any(filters_a_listing(members) for members in pipelines.values()):
        facts.add("find")
    return facts


def kills_by_pattern(command: str) -> bool:
    """Judge a Bash call by what the shell would run.

    A violation is a `pkill` or `killall` given a name or a pattern, or one call that both finds
    processes by pattern (`pgrep`, `pidof`, `ps ... | grep`) and signals something other than
    literal process IDs (`kill $pids`, `xargs kill`). `pkill -P <pid>` and `kill 1234` are fine,
    and so is text inside the quoted arguments of other commands, such as `grep -n 'pkill'`.
    Text that nests too deeply to read counts as a violation, so that a person looks at it.
    """
    try:
        facts = shell_facts(command)
    except RecursionError:
        return True
    return "kill-pattern" in facts or {"find", "signal"} <= facts


def programs_run(text: str, depth: int = 0) -> list[tuple[str, list[Word]]]:
    """List the programs that a Bash call runs, each with its arguments, as the shell would run them.

    A program is named by its file name, without a directory. The list covers every command that
    the shell reads: past assignments, keywords, and wrappers (`env`, `timeout`, `sudo`, `xargs`),
    inside `sh -c`, `bash -c`, `eval`, substitutions, and the here-document of a shell. A script
    that a shell or `.` runs from a file counts as a program named by the file, with the arguments
    after it; `bash -n` runs nothing. The arguments that `xargs` reads from its input add one that
    expands. The quoted words of other commands are their arguments and run nothing.
    """
    found, parsed = [], ShellParser(text)
    slots = {(c.pipeline, c.position): c for c in parsed.commands}
    for command in parsed.commands:
        for name, args, via_xargs, own in invoked(command):
            if via_xargs:
                args = [*args, Word("$", False)]
            found.append((name, args))
            script = embedded_script(name, args, stdin_of(command, slots) if own else None) if depth < MAX_SHELL_DEPTH else None
            if script is not None:
                found += programs_run(script, depth + 1)
            elif depth < MAX_SHELL_DEPTH and (file := script_file(name, args)):
                found.append((file[0].text.rsplit("/", 1)[-1], file[1]))
    return found


def runs_program(command: str, program: str, arguments: re.Pattern | None) -> bool:
    """Say whether a Bash call runs `program` with arguments that `arguments` finds, as the shell would run it.

    The expression searches the arguments joined by one space. An argument that the shell expands
    (`$job`, `$(...)`, a backtick) reads as `$` and its text, so a rule can treat what it cannot see
    as a hit. Text that nests too deeply to read counts as a hit, so that a person looks at it.
    """
    try:
        calls = programs_run(command)
    except RecursionError:
        return True
    for name, args in calls:
        joined = " ".join(w.text if w.plain or "$" in w.text else "$" + w.text for w in args)
        if name == program and (arguments is None or arguments.search(joined)):
            return True
    return False


# A rule with a `check` is judged by the function it names; the others are regular expressions.
STREAM_CHECKS = {"kills_by_pattern": kills_by_pattern}
DEFAULT_STREAM = [{"id": "kill-by-pattern", "check": "kills_by_pattern"}]
LOOP = re.compile(r"\b(?:while|until)\b.*\bsleep\b", re.DOTALL)
BOUND = re.compile(
    r"\btimeout\b|\bdeadline\b|\bSECONDS\b|date \+%s|\bseq\b|\bfor\b.+\bin\b|-lt\b|-le\b|\battempts?\b|\bretries\b|\btries\b",
    re.DOTALL,
)


def tool_calls(stream: Path) -> list[dict]:
    """List the tool calls of a stream with their input fields, in order."""
    calls = []
    for line in stream.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (event.get("message") or {}).get("content") if event.get("type") == "assistant" else None
        for item in content if isinstance(content, list) else []:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                fields = item.get("input")
                calls.append({"name": item.get("name"), "input": fields if isinstance(fields, dict) else {}})
    return calls


def stream_violations(calls: list[dict], patterns: list[dict]) -> list[dict]:
    """List the tool calls that match a violation pattern, judged by the call's input fields.

    A pattern names the tool (Bash by default) and the input field it reads (`command`), may exempt
    a call with `unless`, and may apply only to background calls (`background`: true) or foreground
    ones (false). A foreground call is bounded by the tool's timeout and a background call is not.
    A rule with a `check` is judged by that function in `STREAM_CHECKS` instead of an expression.
    A rule with `runs` (a `program` and an optional `args` expression) is judged by what the shell
    would run, as `programs_run` reads it, instead of by the text of the call.
    """
    hits = []
    for pattern in patterns:
        if "check" in pattern:
            matches = STREAM_CHECKS[pattern["check"]]
        elif "runs" in pattern:
            spec = pattern["runs"]
            arguments = re.compile(spec["args"]) if spec.get("args") else None
            matches = lambda text, program=spec["program"], arguments=arguments: runs_program(text, program, arguments)
        else:
            rule = re.compile(pattern["pattern"], re.MULTILINE)
            exempt = re.compile(pattern["unless"], re.MULTILINE) if pattern.get("unless") else None
            matches = lambda text, rule=rule, exempt=exempt: bool(rule.search(text)) and not (exempt and exempt.search(text))
        for call in calls:
            text = str(call["input"].get(pattern.get("field", "command"), ""))
            background = bool(call["input"].get("run_in_background"))
            if call["name"] != pattern.get("tool", "Bash") or pattern.get("background", background) != background:
                continue
            if matches(text):
                hits.append({"id": pattern["id"], "command": text[:300], "background": background})
    return hits


def is_stream_rule(item: dict) -> bool:
    """Say whether an entry of `ceremony` is a stream rule (an expression or a program) and not a state check."""
    return "pattern" in item or "runs" in item


def loops_to_check(calls: list[dict]) -> list[str]:
    """List waiting loops without a visible bound, for a person to judge; they are not scored."""
    commands = [str(call["input"].get("command", "")) for call in calls if call["name"] == "Bash"]
    return [c[:300] for c in commands if LOOP.search(c) and not BOUND.search(c)]


def skill_words(calls: list[dict], skill: Path) -> dict:
    """Count the words of the skill that the agent read.

    A file counts once per run, whole, when the Read tool opened it, a Grep call named it as its
    path, or a shell command named it, so a partial read counts in full. A command may name a glob,
    or a file relative to a `cd` into the skill. A directory counts nothing, however it is searched.
    """
    root, files = skill.resolve(), {}

    def count(candidate: str) -> None:
        paths = glob.glob(candidate) if any(c in candidate for c in "*?[") else [candidate]
        for path in paths:
            resolved = Path(path).resolve()
            if resolved.is_file() and resolved.is_relative_to(root):
                text = resolved.read_text(encoding="utf-8", errors="replace")
                files[resolved.relative_to(root).as_posix()] = len(text.split())

    named = re.compile(re.escape(str(skill)) + r"[^\s'\"`;|&<>()]*")
    for call in calls:
        if call["name"] == "Read":
            count(str(call["input"].get("file_path", "")))
        elif call["name"] == "Grep":
            count(str(call["input"].get("path", "")))
        elif call["name"] == "Bash":
            command = str(call["input"].get("command", ""))
            for match in named.findall(command):
                count(match.rstrip(".,:"))
            if re.search(r"\bcd\s+['\"]?" + re.escape(str(skill)), command):
                for token in re.findall(r"[^\s'\"`;|&<>()]+", command):
                    count(str(skill / token))
    return {"words": sum(files.values()), "files": files}


def score_run(
    expected: dict, before: dict, after: dict, launcher: dict | None, report: str, calls: list[dict], task: str = ""
) -> dict:
    """Score a run from its records: seeds detected, state checks, stream violations, and ceremony.

    Everything counts for every run, whether it finished or not. Lines of the task count as inputs.
    """
    processes = (launcher or {}).get("fixtures")
    ceremony = expected.get("ceremony", [])
    return {
        "detect": detect(expected.get("detect", []), report, before, after, task),
        "state": [check_state(item, before, after, processes) for item in expected.get("state", [])],
        "stream": stream_violations(calls, DEFAULT_STREAM + expected.get("stream", [])),
        "ceremony": [
            *(c for c in (check_state(i, before, after, processes) for i in ceremony if not is_stream_rule(i)) if not c["ok"]),
            *stream_violations(calls, [i for i in ceremony if is_stream_rule(i)]),
        ],
        "loops": loops_to_check(calls),
    }


LAUNCHER = Path(__file__).with_name("scenario_launcher.py")
# Where the launcher's file lands inside; it deletes itself as soon as it starts.
LAUNCHER_INSIDE = "/run/init.py"
# Directories that the sandbox replaces with empty private ones; only what is bound back is there.
MASKED = ("/tmp", "/run", "/mnt", "/var/tmp", "/dev/shm")
SANDBOX_PATH = "/usr/local/bin:/usr/bin:/bin"
# The interpreter that starts the launcher inside; the runner's own may live where the sandbox hides it.
INTERPRETER = shutil.which("python3", path=SANDBOX_PATH) or sys.executable
# The runner's backstop waits this long beyond the time limit and the launcher's own grace.
LAUNCHER_GRACE = 20
BACKSTOP_MARGIN = 60


@contextlib.contextmanager
def launcher_file() -> Iterator[int]:
    """Open the launcher's file for `--file`, which reads a descriptor to its end; each sandbox needs its own."""
    descriptor = os.open(LAUNCHER, os.O_RDONLY | os.O_CLOEXEC)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def sandbox_arguments(
    home: Path, directory: Path, read_only: list[Path], read_write: list[Path], command: list[str],
    launcher: int | None = None,
) -> list[str]:
    """Return the command that runs `command` in a sandbox built from an allow-list.

    The root file system is read-only. The home directory and the directories in `MASKED` are
    empty private file systems, so the repository, the oracle, other sessions' files, the Docker
    socket, and the Windows drives are absent rather than read-only. Only the paths passed here are
    bound back, at their own paths. The sandbox has its own PID, IPC, and UTS namespaces, the
    command is its PID 1, and the network stays open because the agent must reach the model.
    `setpriv` ends the sandbox if the runner's thread dies.

    The launcher is a copy of its file, written by `--file` from the descriptor `launcher` into the
    private /run, not a bind of the host's file. It deletes the copy when it starts, so nothing of
    it is left to read. The caller passes the descriptor on to the sandbox, as `launch` does.
    """
    arguments = [
        *("setpriv", "--pdeathsig", "KILL", "bwrap"),
        *("--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup-try"),
        *("--as-pid-1", "--die-with-parent", "--new-session", "--clearenv"),
        *("--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev"),
    ]
    for masked in (*MASKED, str(home)):
        arguments += ["--tmpfs", masked]
    if launcher is not None:
        arguments += ["--file", str(launcher), LAUNCHER_INSIDE]
    resolver = Path(os.path.realpath("/etc/resolv.conf"))
    if resolver.is_file() and any(resolver.is_relative_to(masked) for masked in (*MASKED, str(home))):
        read_only = [*read_only, resolver]
    for path in read_only:
        arguments += ["--ro-bind", str(path), str(path)]
    for path in read_write:
        arguments += ["--bind", str(path), str(path)]
    environment = {"HOME": str(home), "PATH": SANDBOX_PATH, "LANG": "C.UTF-8"}
    for name, value in environment.items():
        arguments += ["--setenv", name, value]
    return [*arguments, "--chdir", str(directory), *command]


@functools.cache
def sandbox_problem() -> str | None:
    """Return why a sandbox cannot start on this machine, or None when it can."""
    for tool in ("bwrap", "setpriv"):
        if not shutil.which(tool):
            return f"{tool} is not installed"
    with launcher_file() as launcher:
        probe = sandbox_arguments(Path.home(), Path("/"), [], [], [shutil.which("true") or "/usr/bin/true"], launcher)
        result = subprocess.run(
            probe, capture_output=True, text=True, timeout=60, env={"PATH": SANDBOX_PATH}, pass_fds=(launcher,)
        )
    lines = result.stderr.strip().splitlines()
    return None if result.returncode == 0 else (lines[-1] if lines else f"bwrap exited {result.returncode}")


class Sandboxes:
    """The sandboxes that run now, so that a stop signal can end their process groups.

    Once `stopped` is set, none starts.
    """

    def __init__(self) -> None:
        self.processes: set[subprocess.Popen] = set()
        self.stopped, self.lock = threading.Event(), threading.Lock()

    def stop(self) -> int:
        """Refuse new sandboxes, end the running ones, and return how many were running."""
        self.stopped.set()
        with self.lock:
            live = [process for process in self.processes if process.poll() is None]
        stop_groups(live)
        return len(live)


def launch(
    arguments: list[str],
    payload: dict,
    stream: Path,
    stderr: Path,
    status: Path,
    limit: float,
    sandboxes: Sandboxes,
    inherit: tuple[int, ...] = (),
) -> dict:
    """Run one sandbox and return how it ended.

    The payload goes to the launcher on standard input, never in the command line or the
    environment, where another process could read it. The launcher answers on a descriptor that
    only it holds. `inherit` lists the descriptors that `sandbox_arguments` named, such as the
    launcher's file. The runner waits a little longer than the time limit, which the launcher
    enforces itself, and then ends the sandbox's process group.
    """
    descriptor = os.open(status, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    result = {"exit": None, "backstop": False, "stopped": False, "launcher": None}
    try:
        with stream.open("wb") as out, stderr.open("wb") as err, sandboxes.lock:
            if sandboxes.stopped.is_set():
                return result | {"stopped": True}
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                pass_fds=(descriptor, *inherit),
                start_new_session=True,
                env={"PATH": SANDBOX_PATH},
            )
            sandboxes.processes.add(process)
        try:
            process.stdin.write(json.dumps({**payload, "status_fd": descriptor}).encode("utf-8"))
            process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            result["exit"] = process.wait(timeout=payload["limit"] + LAUNCHER_GRACE + BACKSTOP_MARGIN)
        except subprocess.TimeoutExpired:
            stop_groups([process])
            result |= {"exit": process.returncode, "backstop": True}
        finally:
            with sandboxes.lock:
                sandboxes.processes.discard(process)
    finally:
        os.close(descriptor)
    result["stopped"] = sandboxes.stopped.is_set()
    lines = status.read_text(encoding="utf-8").splitlines()
    try:
        result["launcher"] = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        pass
    return result


WORKSPACE_NAME = re.compile(r"scenario\.[A-Za-z0-9_]{8}")
SKILL_EXPORT_NAME = re.compile(r"skill\.[A-Za-z0-9_]{8}")


def make_deletable(path: Path) -> None:
    """Give back the permissions an agent may have taken away, directory by directory.

    Links are never followed, so a link inside the tree cannot send this out of it.
    """
    stack = [path]
    while stack:
        directory = stack.pop()
        try:
            os.chmod(directory, os.lstat(directory).st_mode | 0o700)
            stack += [Path(entry.path) for entry in os.scandir(directory) if entry.is_dir(follow_symlinks=False)]
        except OSError:
            pass


def restore_write(function, path, error) -> None:
    """An `onexc` handler for `shutil.rmtree`: make the entry and its directory writable and retry."""
    for target in (os.path.dirname(path), path):
        if not os.path.islink(target):
            try:
                os.chmod(target, os.stat(target).st_mode | 0o700)
            except OSError:
                pass
    function(path)


def remove_tree(path: Path) -> None:
    make_deletable(path)
    shutil.rmtree(path, onexc=restore_write)


def new_directory(prefix: str) -> dict:
    """Make a directory in the temporary directory and record which one it is."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    info = path.stat()
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino}


def delete_directory(recorded: dict, name: re.Pattern = WORKSPACE_NAME) -> str | None:
    """Delete a directory this runner made, after re-checking it; return None or why it was kept.

    The path must still be the recorded directory, a direct child of the temporary directory, not a
    symbolic link, and named as the runner names such directories. Permissions the agent removed are
    restored before the deletion. A directory that is already gone is fine.
    """
    path = Path(recorded["path"])
    if path.is_symlink():
        return "it is a symbolic link now"
    if not path.exists():
        return None
    resolved = path.resolve()
    if resolved.parent != Path(tempfile.gettempdir()).resolve():
        return "it is not a direct child of the temporary directory"
    if not name.fullmatch(resolved.name):
        return "its name is not one the runner gives"
    info = path.stat()
    if (info.st_dev, info.st_ino) != (recorded["device"], recorded["inode"]):
        return "it is not the directory that was recorded"
    remove_tree(resolved)
    return None


TRIAL_ALLOWED = {"file_changed", "commits_added", "process_dead"}


def template_problems(text: str, repos: set[str]) -> list[str]:
    problems = []
    for name in (m.strip() for m in TEMPLATE.findall(text)):
        found = REVISION_TEMPLATE.fullmatch(name)
        if not NOW_TEMPLATE.fullmatch(name) and not (found and found[2] in repos):
            problems.append(f"unknown template {{{{{name}}}}}")
    return problems


def fixture_problems(spec: dict, files: Path) -> tuple[list[str], dict]:
    """Check a scenario's fixtures; return the problems and the names they define."""
    problems, repos, remotes, processes = [], set(), set(), {}
    limit = spec["minutes"] * 60 if isinstance(spec.get("minutes"), (int, float)) else 0
    for number, fixture in enumerate(spec.get("fixtures", []), 1):
        where, kind = f"fixture {number}", fixture.get("kind")
        if kind not in FIXTURES:
            problems.append(f"{where}: unknown kind {kind!r}")
            continue
        required, optional = FIXTURES[kind]
        given = set(fixture) - {"kind"}
        if required - given:
            problems.append(f"{where} ({kind}): missing {', '.join(sorted(required - given))}")
        if given - required - optional:
            problems.append(f"{where} ({kind}): unknown field {', '.join(sorted(given - required - optional))}")
        if "repo" in fixture and fixture["repo"] not in repos:
            problems.append(f"{where}: the repository {fixture['repo']!r} is not defined before it")
        for key in ("path", "source", "cwd"):
            try:
                relative_path(str(fixture.get(key, "x")))
            except SystemExit as error:
                problems.append(f"{where}: {error}")
        for key in ("uncommitted", "files"):
            if key in fixture and not (files / str(fixture[key])).is_dir():
                problems.append(f"{where}: no directory files/{fixture[key]}")
        for entry in fixture.get("commits", []):
            if COMMIT_FIELDS[0] - set(entry):
                problems.append(f"{where}: a commit needs {', '.join(sorted(COMMIT_FIELDS[0] - set(entry)))}")
            problems += [f"{where}: a commit has unknown field {key}" for key in set(entry) - COMMIT_FIELDS[0] - COMMIT_FIELDS[1]]
            if "files" in entry and not (files / str(entry["files"])).is_dir():
                problems.append(f"{where}: no directory files/{entry['files']}")
        if kind == "file":
            source = files / str(fixture.get("source", ""))
            if not source.is_file():
                problems.append(f"{where}: no file files/{fixture.get('source')}")
            else:
                problems += [f"{where}: {p}" for p in template_problems(source.read_text(encoding="utf-8"), repos)]
        if kind == "repo":
            repos.add(fixture.get("path"))
        elif kind == "remote":
            remotes.add(fixture.get("path"))
        elif kind == "process":
            command = fixture.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command):
                problems.append(f"{where}: command is a list of non-empty strings, the program first")
            elif any(TEMPLATE.search(argument) for argument in command):
                problems.append(f"{where}: a command renders no template")
            if fixture.get("name") in processes:
                problems.append(f"{where}: the process {fixture.get('name')!r} is defined twice")
            processes[fixture.get("name")] = fixture.get("seconds")
            if not isinstance(fixture.get("seconds"), (int, float)) or fixture["seconds"] < limit + FIXTURE_MARGIN:
                problems.append(f"{where}: seconds must exceed the time limit ({limit:g}) by {FIXTURE_MARGIN}")
    return problems, {"repos": repos | remotes, "processes": set(processes)}


def pattern_problems(pattern: str, where: str) -> list[str]:
    try:
        re.compile(TEMPLATE.sub("x", pattern))
    except re.error as error:
        return [f"{where}: bad expression {pattern!r}: {error}"]
    return []


def near_shape(entry) -> bool:
    """Say whether a `near` entry has one of the shapes that `near_source` reads."""
    if isinstance(entry, dict):
        return ({"subject", "finding"} <= set(entry) <= NEAR_FIELDS and isinstance(entry.get("within", 200), int)
                and all(near_shape(entry[key]) for key in ("subject", "finding", "others") if key in entry))
    return isinstance(entry, str) or (isinstance(entry, list) and bool(entry) and all(isinstance(piece, str) for piece in entry))


def runs_problems(rule: dict, where: str) -> list[str]:
    """Check a rule's `runs`: a program's file name and an optional expression for its arguments."""
    spec = rule["runs"]
    if not isinstance(spec, dict) or not isinstance(spec.get("program"), str) or set(spec) - {"program", "args"}:
        return [f"{where}: runs is an object with a program and, optionally, args"]
    problems = []
    if not re.fullmatch(r"[^\s/]+", spec["program"]):
        problems.append(f"{where}: the program of runs is a file name, without a directory")
    if "args" in spec:
        if not isinstance(spec["args"], str):
            problems.append(f"{where}: args of runs is an expression")
        elif not spec["args"]:
            problems.append(f"{where}: args of runs is empty, which counts every run; leave args out for that")
        else:
            problems += pattern_problems(spec["args"], where)
    if rule.get("tool", "Bash") != "Bash" or {"field", "unless"} & set(rule):
        problems.append(f"{where}: a rule with runs reads the command of a Bash call, so it has no tool, field, or unless")
    return problems


def normal_place(place) -> bool:
    """Say whether a place is a relative path that names its files as a snapshot does: no './', '..', '//', or end slash."""
    return isinstance(place, str) and bool(place) and all(part not in ("", ".", "..") for part in place.split("/"))


def expected_problems(expected: dict, names: dict) -> list[str]:
    """Check the oracle against the names its scenario's fixtures define."""
    problems, ids = [], set()
    for seed in expected.get("detect", []):
        where = f"detect {seed.get('id')!r}"
        if seed.get("id") in ids or not seed.get("id"):
            problems.append(f"{where}: the id is empty or repeated")
        ids.add(seed.get("id"))
        if seed.get("kind") not in ("seeded", "off-list"):
            problems.append(f"{where}: kind must be seeded or off-list")
        if not isinstance(seed.get("source"), (str, list)) or not seed.get("near"):
            problems.append(f"{where}: needs a source and a non-empty near list")
        for entry in seed.get("near", []):
            if not near_shape(entry):
                problems.append(f"{where}: a near entry is an expression, a list of pieces, or an object with {sorted(NEAR_FIELDS)}")
                continue
            pattern = near_source(entry)
            problems += pattern_problems(pattern, where)
            for name in (m.strip() for m in TEMPLATE.findall(pattern)):
                found = REVISION_TEMPLATE.fullmatch(name)
                if not found or found[2] not in names["repos"]:
                    problems.append(f"{where}: cannot resolve {{{{{name}}}}}")
    for part in ("state", "ceremony"):
        for item in expected.get(part, []):
            if part == "ceremony" and is_stream_rule(item):
                continue
            kind = next(iter(item), None)
            if len(item) != 1 or kind not in STATE_CHECKS:
                problems.append(f"{part}: {item!r} is not one known check")
                continue
            argument = item[kind]
            if kind.startswith("process_") and argument not in names["processes"]:
                problems.append(f"{part}: {kind} names the unknown process {argument!r}")
            repo = argument.get("repo") if isinstance(argument, dict) else argument if kind in ("refs_unchanged", "no_new_branches", "no_new_worktrees") else None
            if isinstance(repo, str) and repo not in names["repos"]:
                problems.append(f"{part}: {kind} names the unknown repository {repo!r}")
            if kind in ("no_new_files_outside", "no_new_files_inside"):
                places = listed(argument) if isinstance(argument, (str, list)) else []
                if not places or not all(normal_place(place) for place in places):
                    problems.append(f"{part}: {kind} takes a normalised relative path or a list of them, such as 'plan.md' or 'briefs'")
            if kind == "branch_lacks":
                if not isinstance(argument, dict) or not all(isinstance(argument.get(k), str) for k in ("repo", "branch", "path", "pattern")):
                    problems.append(f"{part}: branch_lacks needs a repo, a branch, a path, and a pattern")
                elif set(argument) - {"repo", "branch", "path", "pattern", "present_before"} or not isinstance(argument.get("present_before", True), bool):
                    problems.append(f"{part}: branch_lacks takes a repo, a branch, a path, a pattern, and present_before as true or false")
                else:
                    problems += pattern_problems(argument["pattern"], f"{part}: branch_lacks")
                    if TEMPLATE.search(argument["pattern"]):
                        problems.append(f"{part}: branch_lacks resolves no template: {argument['pattern']!r}")
                    if part == "ceremony" and argument.get("present_before"):
                        problems.append(f"{part}: branch_lacks with present_before asks for a repair, which the null run never makes, so it always reports the ceremony")
    stream = [*expected.get("stream", []), *(i for i in expected.get("ceremony", []) if is_stream_rule(i))]
    for rule in stream:
        where = f"stream {rule.get('id')!r}"
        if not rule.get("id") or rule["id"] in ids | {"kill-by-pattern"}:
            problems.append(f"{where}: the id is empty or repeated")
        ids.add(rule.get("id"))
        if "check" in rule:
            problems.append(f"{where}: a scenario rule is an expression or a program; a check belongs to the runner")
        if ("pattern" in rule) == ("runs" in rule):
            problems.append(f"{where}: a rule has a pattern or runs, and only one of them")
        if "runs" in rule:
            problems += runs_problems(rule, where)
        problems += pattern_problems(rule.get("pattern", ""), where) + pattern_problems(rule.get("unless", "x"), where)
    return problems


def process_problems(workspace: Path, process: dict) -> list[str]:
    """Check that a prepared `process` fixture can start: its directory exists and its program is found."""
    cwd, program = workspace / process["cwd"], process["command"][0]
    if not cwd.is_dir():
        return [f"the process {process['name']!r} starts in {process['cwd']!r}, which is not a directory"]
    found = os.access(cwd / program, os.X_OK) if "/" in program else shutil.which(program, path=SANDBOX_PATH)
    return [] if found else [f"the process {process['name']!r} runs {program!r}, which is not an executable there"]


def null_run_problems(scenario: Path) -> list[str]:
    """Prepare the scenario, then score an untouched workspace with an empty report.

    It must detect nothing and show no violation. Only the checks that ask for a change may fail. A
    `branch_lacks` asks for a change when it says `present_before`: the prepared branch holds the
    text, the task asks the agent to remove it, and the null run must then fail the check because the
    text matches. Without it the check guards against a change, and the null run must pass it.
    """
    trial = new_directory(WORKSPACE_PREFIX)
    workspace = Path(trial["path"])
    try:
        manifest = prepare_workspace(scenario, workspace)
        snapshot = take_snapshot(workspace, manifest)
        launcher = {"fixtures": {p["name"]: {"state": "alive"} for p in manifest["processes"]}}
        expected = json.loads((scenario / "expected.json").read_text(encoding="utf-8"))
        scored = score_run(expected, snapshot, snapshot, launcher, "", [])
        problems = [problem for process in manifest["processes"] for problem in process_problems(workspace, process)]
    finally:
        remove_tree(workspace)
    problems += [f"a null run detects {d['id']}" for d in scored["detect"] if d["found"]]
    for c in scored["state"]:
        if c["check"] == "branch_lacks" and c["argument"].get("present_before"):
            if c["ok"] or " matches " not in c["detail"]:
                problems.append(f"a null run passes or cannot read branch_lacks that says present_before: {c['detail'] or 'the text is not there'}")
        elif not c["ok"] and c["check"] not in TRIAL_ALLOWED:
            problems.append(f"a null run breaks {c['check']}: {c['detail']}")
    problems += [f"a null run shows the ceremony {c.get('check') or c['id']}" for c in scored["ceremony"]]
    return problems + [f"a null run hits {hit['id']}" for hit in scored["stream"]] + snapshot["problems"]


def scenario_problems(scenario: Path) -> list[str]:
    """List what is wrong with a scenario directory: its files, its fixtures, its oracle, a null run."""
    problems, documents = [], {}
    for name in ("scenario.json", "expected.json"):
        try:
            documents[name] = json.loads((scenario / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            problems.append(f"{name}: {error}")
    if problems:
        return problems
    spec, expected = documents["scenario.json"], documents["expected.json"]
    minutes = spec.get("minutes")
    if spec.get("tier") not in ("E1", "E2", "E3"):
        problems.append("scenario.json: tier must be E1, E2, or E3")
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
        problems.append("scenario.json: minutes must be a positive number")
        return problems
    if not (scenario / str(spec.get("task", ""))).is_file():
        problems.append("scenario.json: the task file is missing")
    fixtures, names = fixture_problems(spec, scenario / "files")
    problems += fixtures + expected_problems(expected, names)
    return problems or null_run_problems(scenario)


SKILL = "skills/coordinating-agents"
LEVELS = ("none", "full")
# The one line the full level adds before the task; "where it applies" leaves the proportion to the skill.
SKILL_LINE = "The coordinating-agents skill is in {path}. Read its SKILL.md and follow it where it applies."


def prompt_for(level: str, task: str, skill: Path | None) -> str:
    return f"{SKILL_LINE.format(path=skill)}\n\n{task}" if level == "full" else task


def repository_git(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, env=git_environment(), stdin=subprocess.DEVNULL,
        capture_output=True, check=True, timeout=60,
    ).stdout


def export_skill(revision: str) -> Path:
    """Extract the skill at a revision into a new temporary directory, away from the reports."""
    try:
        archive = repository_git("archive", "--format=tar", f"{revision}:{SKILL}")
    except subprocess.CalledProcessError:
        raise SystemExit(f"the revision {revision} has no {SKILL}") from None
    skill = Path(tempfile.mkdtemp(prefix="skill.")) / "coordinating-agents"
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(skill, filter="data")
    return skill


def parse_runs(values: list[str]) -> list[tuple[str, str, str | None, str]]:
    """Read NUMBER=MODEL[@REVISION][+LEVEL] specifications; the level is `full` unless named."""
    runs = []
    for value in values:
        number, _, rest = value.partition("=")
        rest, _, level = rest.partition("+")
        model, _, revision = rest.partition("@")
        if not number.isdigit() or not model or (level or "full") not in LEVELS:
            raise SystemExit(f"--run takes NUMBER=MODEL[@REVISION][+LEVEL] with a level of {'/'.join(LEVELS)}, not {value!r}")
        runs.append((number, model, revision or None, level or "full"))
    if len({run[0] for run in runs}) != len(runs):
        raise SystemExit("each --run needs its own number")
    return runs


def round_paths(round_dir: Path) -> dict[str, Path]:
    names = ("plan.json", "streams", "reports", "runs", "log.txt", "summary.md", "resources.json")
    return {name: round_dir / name for name in names}


def check_round_dir(round_dir: Path) -> None:
    resolved = round_dir.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise SystemExit("Keep the round directory outside this repository")
    if Path(tempfile.gettempdir()).resolve() in resolved.parents:
        print(f"warning: {round_dir} is under the temporary directory, which a restart may clear")


def job_order(scenarios: list[str], specs: list[tuple]) -> list[tuple[str, tuple]]:
    """List (scenario, run) pairs scenario by scenario, so that the arms run side by side in time.

    The level that launches first alternates between scenarios, so that neither always pays for the
    first writes of the prompt cache.
    """
    ordered = []
    for index, scenario in enumerate(scenarios):
        for level in LEVELS if index % 2 == 0 else reversed(LEVELS):
            ordered += [(scenario, spec) for spec in specs if spec[3] == level]
    return ordered


def plan(round_dir: Path, runs: list[tuple], scenarios: list[str], revision: str) -> dict:
    """Validate the scenarios, export the skill for the full-level runs, and write the round's plan.

    Workspaces are not prepared here: each is prepared just before its launch, so that relative
    times do not drift with the order of the runs.
    """
    check_round_dir(round_dir)
    paths = round_paths(round_dir)
    if paths["plan.json"].exists():
        raise SystemExit(f"{round_dir} already has a plan")
    for name in scenarios:
        problems = scenario_problems(SCENARIOS / name) if (SCENARIOS / name / "scenario.json").is_file() else [f"unknown scenario {name}"]
        if problems:
            raise SystemExit(f"scenario {name} is not valid:\n- " + "\n- ".join(problems))
    specs = []
    for number, model, wanted, level in runs:
        commit = repository_git("rev-parse", "--short", wanted or revision).decode().strip() if level == "full" else None
        specs.append((number, model, commit, level))
    for name in ("streams", "reports", "runs"):
        paths[name].mkdir(parents=True, exist_ok=True)
    skills = {commit: str(export_skill(commit)) for commit in dict.fromkeys(s[2] for s in specs if s[2])}
    jobs = []
    for scenario, (number, model, commit, level) in job_order(scenarios, specs):
        job = {"run": number, "model": model, "scenario": scenario, "level": level, "revision": commit}
        jobs.append(job | {"label": f"run{number}-{scenario}", "skill": skills.get(commit)})
    data = {"created": now(), "skill_commit": ", ".join(skills) or "none", "skills": skills, "jobs": jobs}
    paths["plan.json"].write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# The channels to the host that the sandbox must not leave open: Docker's sockets, and the Windows
# programs that WSL interop would run. The preflight uses them, and expects every attempt to fail.
DOCKER_SOCKETS = ("/var/run/docker.sock", "/run/docker.sock")
INTEROP_PROGRAMS = ("cmd.exe", "/mnt/c/Windows/System32/cmd.exe")
# Run inside the sandbox before a round; it prints what it found as one JSON object.
PREFLIGHT = r"""
import json, os, shutil, socket, subprocess, sys
spec = json.load(sys.stdin)
found = {"pid": os.getpid(), "hidden": [p for p in spec["hidden"] if os.path.exists(p)]}
found["home"] = sorted(set(os.listdir(spec["home"])) - set(spec["home_allowed"]))
found["channels"] = [p for p in ("/var/run/docker.sock", "/run/docker.sock", "/run/user", "/run/WSL") if os.path.exists(p)]
found["drives"] = [name for name in os.listdir("/mnt") if len(name) == 1]
found["variables"] = [n for n in ("WSL_INTEROP", "DOCKER_HOST", "SSH_AUTH_SOCK") if n in os.environ]
found["docker"], found["interop"] = [], []
for path in spec["sockets"]:
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(5)
    try:
        probe.connect(path)
        found["docker"].append(path)
    except OSError:
        pass
    finally:
        probe.close()
for program in spec["programs"]:
    path = shutil.which(program) if "/" not in program else program if os.path.exists(program) else None
    try:
        if path and subprocess.run([path, "/c", "exit", "0"], capture_output=True, timeout=20).returncode == 0:
            found["interop"].append(path)
    except (OSError, subprocess.SubprocessError):
        pass
try:
    found["canary_reached"] = subprocess.run(["pkill", "-f", spec["canary"]], capture_output=True).returncode == 0
except OSError as error:
    found["pkill_missing"] = str(error)
print(json.dumps(found))
"""


def preflight(hidden: list[Path], read_only: list[Path]) -> list[str]:
    """Check from inside a sandbox that it hides what it must; return what fails.

    A host canary process, started with a unique command line, must survive a pattern kill from the
    sandbox. The paths in `hidden` (the repository, the oracle, the round directory, and the like)
    must not exist inside, and neither may the home directory's contents, the Docker and WSL
    channels, or the Windows drives. It also tries the channels: a connection to each Docker socket
    and a run of `cmd.exe`, where there is one, must fail.
    """
    home = Path.home()
    marker = f"scenario-canary-{secrets.token_hex(6)}"
    canary = subprocess.Popen(
        [marker, "600"], executable="/bin/sleep", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    trial = new_directory(WORKSPACE_PREFIX)
    workspace = Path(trial["path"])
    try:
        allowed = sorted({p.relative_to(home).parts[0] for p in read_only if p.is_relative_to(home)})
        spec = {"hidden": [str(p) for p in hidden], "home": str(home), "home_allowed": allowed, "canary": marker}
        spec |= {"sockets": list(DOCKER_SOCKETS), "programs": list(INTEROP_PROGRAMS)}
        command = [INTERPRETER, "-I", "-c", PREFLIGHT]
        result = subprocess.run(
            sandbox_arguments(home, workspace, read_only, [workspace], command), capture_output=True,
            text=True, timeout=120, input=json.dumps(spec), env={"PATH": SANDBOX_PATH},
        )
        survived = canary.poll() is None
    finally:
        canary.kill()
        canary.wait()
        remove_tree(workspace)
    try:
        found = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [f"the check did not run in the sandbox: {result.stderr.strip()[-300:]}"]
    problems = []
    if found["pid"] != 1:
        problems.append(f"the first process is PID {found['pid']}, not 1")
    for key, text in (("hidden", "visible inside"), ("home", "left in the home directory"), ("channels", "reachable"),
                      ("drives", "Windows drive visible"), ("variables", "variable set"),
                      ("docker", "a Docker socket accepts connections"), ("interop", "a Windows program ran")):
        if found[key]:
            problems.append(f"{text}: {', '.join(found[key])}")
    if found.get("pkill_missing"):
        problems.append(f"pkill is missing, so a pattern kill cannot be checked: {found['pkill_missing']}")
    if found.get("canary_reached") or not survived:
        problems.append("a pattern kill inside the sandbox reached a process of the host")
    return problems


ALLOWED_TOOLS = ("Bash", "Read", "Grep", "Glob", "Edit", "Write")
DISALLOWED_TOOLS = ("Agent", "Task", "Monitor", "WebFetch", "WebSearch", "NotebookEdit")
DEFAULT_TOKEN_FILE = Path.home() / ".config" / "engineering-skills" / "claude-oauth-token"
# The agent's global Git configuration: a fixed identity, and nothing from the host.
GIT_CONFIG = "[user]\n\tname = Scenario Agent\n\temail = agent@example.invalid\n[init]\n\tdefaultBranch = main\n"
# Variables the sandbox keeps from the host: the network may need a proxy.
NETWORK_VARIABLES = ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "all_proxy", "no_proxy")
PROVIDER_PREFIXES = ("ANTHROPIC_", "CLAUDE_")


def agent_command(executable: Path, model: str, skill: Path | None, settings: str) -> list[str]:
    """Return the agent's command; the prompt is not in it, it arrives on standard input.

    Like the audit runner's, it fixes the model by its full ID and the effort, loads only user
    settings with hooks off, and refuses MCP servers and session files. `--safe-mode` also disables
    CLAUDE.md, skills, plugins, hooks, and MCP servers, so neither level inherits any customization.
    It keeps the skills built into the CLI (16 in 2.1.292, seen in the first live run), so
    `--disable-slash-commands` turns those off too; the `full` level reads its skill by path.
    `--allowedTools` only approves tools without asking: the first live runs also had Workflow,
    SendMessage, CronCreate, and others, so `--tools` limits the set. Agents, monitors, and the web
    are disallowed as well.
    """
    return [
        *(str(executable), "-p", "--model", model, "--effort", "high"),
        *(["--add-dir", str(skill)] if skill else []),
        *("--tools", ",".join(ALLOWED_TOOLS)),
        *("--allowedTools", *ALLOWED_TOOLS, "--disallowedTools", *DISALLOWED_TOOLS),
        *("--safe-mode", "--disable-slash-commands", "--setting-sources", "user", "--settings", settings),
        *("--output-format", "stream-json", "--verbose", "--no-session-persistence", "--strict-mcp-config"),
    ]


def base_environment(home: Path) -> dict[str, str]:
    """Return the environment of a shell on this machine: basics and the Git configuration, no login.

    The `process` fixtures run with it, so that nothing a fixture's `/proc/PID/environ` shows is
    more than the agent's own shell has, and no login is in it.
    """
    return {
        "HOME": str(home), "USER": home.name, "LOGNAME": home.name, "PATH": SANDBOX_PATH, "LANG": "C.UTF-8",
        "TERM": "dumb", "SHELL": "/bin/bash", "DISABLE_AUTOUPDATER": "1",
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"), "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
    }


def agent_environment(home: Path, token: str | None, provider: dict[str, str] | None) -> dict[str, str]:
    """Return the agent's whole environment: basics, the Git configuration, and one login.

    A Claude run gets the long-lived token as CLAUDE_CODE_OAUTH_TOKEN; a provider run gets the
    variables of `provider_launch` and no token. The agent can read either, so the runner fails a
    run whose output contains it.
    """
    environment = base_environment(home)
    environment |= {name: os.environ[name] for name in NETWORK_VARIABLES if name in os.environ}
    if provider is not None:
        environment |= {k: v for k, v in provider.items() if k.startswith(PROVIDER_PREFIXES) or k == "API_TIMEOUT_MS"}
    elif token:
        environment["CLAUDE_CODE_OAUTH_TOKEN"] = token
    return environment


def read_token(path: Path) -> str:
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise SystemExit(
            f"Claude runs need a long-lived token from `claude setup-token`, in a file only you can read (mode 600): {path}"
        )
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit(f"The token file is empty: {path}")
    return token


class Spending:
    """Stop launching runs once the finished ones have used the round's budget.

    The CLI reports an API-equivalent cost; on a subscription it measures quota, not money.
    """

    def __init__(self, limit: float) -> None:
        self.limit, self.spent, self.lock = limit, 0.0, threading.Lock()

    def allows(self) -> bool:
        with self.lock:
            return self.spent < self.limit

    def add(self, cost: float) -> None:
        with self.lock:
            self.spent += cost


class Stagger:
    """Space the launches, so the first writes the prompt cache and the next ones read it."""

    def __init__(self, interval: float) -> None:
        self.interval, self.next, self.lock = interval, 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            moment = time.monotonic()
            start = max(moment, self.next)
            self.next = start + self.interval
        if start > moment:
            time.sleep(start - moment)


def scrub(paths: list[Path], secret_values: list[str]) -> bool:
    """Replace every secret in the files with a mark, and say whether any file held one.

    Bytes that are not UTF-8 are replaced too, so that the parsers can read what the agent printed.
    """
    found = False
    for path in paths:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            for value in secret_values:
                if value and value in text:
                    found, text = True, text.replace(value, "[REDACTED]")
            path.write_text(text, encoding="utf-8")
    return found


def init_event(stream: Path) -> dict:
    for line in stream.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            return event
    return {}


INIT_LISTS = ("skills", "plugins", "mcp_servers")


def init_failures(init: dict) -> list[str]:
    """Name what the init event says was loaded although the agent command turns it off.

    The command loads no skill and no MCP server, so any listed means the run was customized and
    its level is not what it says. Plugins built into the CLI (`"path": "builtin"`) stay under
    `--safe-mode` for both levels alike; only another plugin fails the run. The tools must be those
    of `--tools`, no more and no fewer.
    """
    listed = {key: init.get(key) or [] for key in INIT_LISTS}
    listed["plugins"] = [p for p in listed["plugins"] if not (isinstance(p, dict) and p.get("path") == "builtin")]
    failures = [f"the init event lists {key} under --safe-mode: {str(value)[:200]}" for key, value in listed.items() if value]
    tools = set(init.get("tools") or [])
    if init and tools != set(ALLOWED_TOOLS):
        extra, missing = sorted(tools - set(ALLOWED_TOOLS)), sorted(set(ALLOWED_TOOLS) - tools)
        failures.append(f"the init event's tools differ from --tools: extra {extra}, missing {missing}")
    return failures


def run_failures(outcome: dict, results: list[dict], model: str, minutes: float) -> list[str]:
    """List why a run does not count as finished; a failed run is still scored and reported."""
    failures, launcher = [], outcome["launcher"]
    if outcome["backstop"]:
        failures.append("the runner's backstop ended a sandbox that outlived the launcher's time limit")
    if launcher is None:
        failures.append("launcher lost: no record from inside the sandbox")
    elif launcher["agent"].get("error"):
        failures.append(f"the agent did not start: {launcher['agent']['error']}")
    elif launcher["agent"].get("timed_out"):
        failures.append(f"time limit of {minutes:g} minutes")
    elif launcher["agent"].get("state") == "killed":
        failures.append(f"the agent was killed by {launcher['agent']['signal']}")
    if not results:
        failures.append("no result event in the stream")
    elif login_failed(results):
        failures.append("login failed")
    elif not ran_model(results, model):
        failures.append(f"model mismatch: the stream does not show {model}")
    elif results[-1].get("is_error"):
        failures.append(f"the agent ended with an error result: {results[-1].get('subtype')}")
    return failures


def provider_setup(round_dir: Path, label: str, model: str, provider: dict) -> tuple[dict, str, Path]:
    """Prepare a provider run's configuration directory, with its own copy of the key.

    The sandbox cannot see the file the key came from, so the key is copied next to the settings that
    name it, in the one directory the run may use. `run_job` removes the copy afterwards.
    """
    config = round_dir / "providers" / label
    config.mkdir(parents=True, exist_ok=True)
    key = config / "key"
    shutil.copyfile(provider["key"], key)
    key.chmod(0o600)
    environment, settings = provider_launch({"url": provider["url"], "key": key}, model, config)
    return environment, str(settings), config


def run_job(round_dir: Path, job: dict, context: dict) -> str:
    """Prepare a workspace, run one agent in a sandbox, record the run, and delete the workspace.

    The record keeps everything that scoring needs, so `summarize` can score again, after the
    workspace and the skill export are gone and with an oracle that was fixed meanwhile.
    """
    paths, label = round_paths(round_dir), job["label"]
    if (paths["runs"] / f"{label}.json").exists():
        return f"{label}: skipped, record exists"
    if context["sandboxes"].stopped.is_set():
        return f"{label}: skipped, stopped"
    if not context["spending"].allows():
        return f"{label}: skipped, budget reached"
    context["starts"].wait()
    recorded = new_directory(WORKSPACE_PREFIX)
    pending = paths["runs"] / f"{label}.workspace.json"
    pending.write_text(json.dumps(recorded), encoding="utf-8")
    try:
        line = execute_job(round_dir, job, context, Path(recorded["path"]))
    except (Exception, SystemExit) as error:  # a defective scenario must not stop the other runs
        line = f"{label}: error {type(error).__name__}: {error}"
    reason = delete_directory(recorded)
    if reason:
        return f"{line} (workspace kept at {recorded['path']}: {reason})"
    pending.unlink(missing_ok=True)
    return line


def execute_job(round_dir: Path, job: dict, context: dict, workspace: Path) -> str:
    paths, label, model = round_paths(round_dir), job["label"], job["model"]
    scenario = SCENARIOS / job["scenario"]
    spec = json.loads((scenario / "scenario.json").read_text(encoding="utf-8"))
    skill = Path(job["skill"]) if job["level"] == "full" else None
    manifest = prepare_workspace(scenario, workspace)
    before = take_snapshot(workspace, manifest)
    provider = context["providers"].get(model)
    home, read_write, secret_values = context["home"], [workspace], [context["token"]]
    provider_environment, settings, config = None, '{"disableAllHooks": true}', None
    if provider:
        provider_environment, settings, config = provider_setup(round_dir, label, model, provider)
        read_write.append(config)
        secret_values = [provider["key"].read_text(encoding="utf-8").strip()]
    prompt = prompt_for(job["level"], (scenario / spec["task"]).read_text(encoding="utf-8"), skill)
    limit = spec["minutes"] * 60
    payload = {
        "files": {str(home / ".gitconfig"): GIT_CONFIG},
        "fixtures": manifest["processes"],
        "fixture_environment": base_environment(home),
        "command": agent_command(context["executable"], model, skill, settings),
        "cwd": str(workspace),
        "environment": agent_environment(home, context["token"], provider_environment),
        "prompt": prompt,
        "limit": limit,
    }
    stream, stderr = paths["streams"] / f"{label}.jsonl", paths["streams"] / f"{label}.stderr.txt"
    try:
        with launcher_file() as launcher:
            arguments = sandbox_arguments(
                home, workspace, [context["executable"], *([skill] if skill else [])], read_write,
                [INTERPRETER, "-I", LAUNCHER_INSIDE], launcher,
            )
            outcome = launch(
                arguments, payload, stream, stderr, paths["runs"] / f"{label}.launcher.json", limit,
                context["sandboxes"], (launcher,),
            )
    finally:
        # Whatever happened, a stopped run, an exception, or a normal end, the streams never keep a secret.
        if config:
            (config / "key").unlink(missing_ok=True)
        leaked = scrub([stream, stderr], secret_values)
    if outcome["stopped"]:
        return f"{label}: stopped"
    after = take_snapshot(workspace, manifest, before)
    results = stream_results(stream)
    report = report_text(results)
    failures = run_failures(outcome, results, model, spec["minutes"])
    if leaked:
        failures.append("secret in the stream: it was redacted")
    calls = tool_calls(stream)
    init = init_event(stream) if results else {}
    failures += init_failures(init)
    notes = [f"snapshot: {problem}" for problem in after["problems"]]
    if provider and results and init_key_source(stream) != "apiKeyHelper":
        notes.append(f"the key source is {init_key_source(stream)}, not apiKeyHelper")
    outside = outside_paths(stream, [workspace, Path(job["skill"]).parent if skill else workspace, round_dir / "providers"]) if results else []
    record = {
        "label": label, "job": job, "finished": now(), "workspace": str(workspace), "manifest": manifest,
        "before": before, "after": after, "launcher": outcome["launcher"], "exit": outcome["exit"],
        "failures": failures, "notes": notes, "outside": outside,
        "skill": skill_words(calls, skill) if skill else {"words": 0, "files": {}},
        "usage": stream_usage(stream, results), "report_chars": len(report), "minutes": spec["minutes"],
        "cost": max((r.get("total_cost_usd") or 0 for r in results), default=0),
        "seconds": sum(r.get("duration_ms") or 0 for r in results) / 1000,
    }
    context["spending"].add(record["cost"])
    text = json.dumps(record, indent=2) + "\n"
    for value in filter(None, secret_values):
        text = text.replace(value, "[REDACTED]")
    (paths["reports"] / f"{label}.md").write_text(report, encoding="utf-8")
    (paths["runs"] / f"{label}.json").write_text(text, encoding="utf-8")
    return f"{label}: {'failed: ' + '; '.join(failures) if failures else 'ok'}"


class Interrupted(Exception):
    """A stop signal arrived; its number is the first argument."""


def claude_executable() -> Path:
    found = shutil.which("claude")
    if not found:
        raise SystemExit("claude is not on PATH")
    return Path(found).resolve()


def run(
    round_dir: Path,
    jobs: int,
    budget: float,
    stagger: float = 0.0,
    providers: dict[str, dict] | None = None,
    lock_wait: float = 0.0,
    token_file: Path = DEFAULT_TOKEN_FILE,
) -> int:
    """Run every planned scenario in a sandbox; return 1 when a run did not end well.

    `providers` maps a model served by another provider to its base URL and key file. SIGTERM or
    SIGINT stops every sandbox, starts no other run, and returns 128 plus the signal number; the
    handlers are restored afterwards. The whole round holds the lock of every resource its models
    need, as the audit runner's rounds do, waiting for them at most `lock_wait` seconds. It records
    those resources before it waits, so `clean` takes the same locks, and it logs the other rounds'
    locks when it starts and before it releases its own, so `summarize` can mark an overlap.
    """
    providers = providers or {}
    data = json.loads(round_paths(round_dir)["plan.json"].read_text(encoding="utf-8"))
    resources = round_resources(data["jobs"], providers)
    round_paths(round_dir)["resources.json"].write_text(json.dumps(list(resources)) + "\n", encoding="utf-8")
    with round_lock(f"scenario_rounds run {round_dir.resolve()}", lock_wait, resources):
        start = log_overlaps(round_dir, resources)
        try:
            return run_round(round_dir, jobs, budget, stagger, providers, token_file)
        finally:
            # Still under the locks: once they are released, the probe cannot tell who holds what.
            log_overlaps(round_dir, resources, start)


def run_round(
    round_dir: Path, jobs: int, budget: float, stagger: float, providers: dict[str, dict], token_file: Path
) -> int:
    """The body of `run`, under the round lock: check the machine, then run the jobs."""
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    problem = sandbox_problem()
    if problem:
        raise SystemExit(f"A scenario round needs a sandbox, and bwrap cannot create one here: {problem}")
    executable = claude_executable()
    models = sorted({job["model"] for job in data["jobs"]})
    token = read_token(token_file) if any(model not in providers for model in models) else None
    skills = [Path(path) for path in data["skills"].values()]
    gone = [str(path) for path in skills if not path.is_dir()]
    if gone:
        raise SystemExit(f"The skill export is gone: {', '.join(gone)}. Plan the round again.")
    problems = preflight([ROOT, round_dir.resolve(), token_file.resolve()], [executable, *skills])
    if problems:
        raise SystemExit("The sandbox does not isolate a run:\n- " + "\n- ".join(problems))
    version = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=60)
    (round_dir / "cli-version.txt").write_text(version.stdout, encoding="utf-8")
    warm_up(round_dir, [model for model in models if model in providers], providers)
    sandboxes = Sandboxes()
    context = {
        "sandboxes": sandboxes, "spending": Spending(budget), "starts": Stagger(stagger), "providers": providers,
        "token": token, "executable": executable, "home": Path.home(),
    }

    def interrupt(number: int, frame) -> None:
        if not sandboxes.stopped.is_set():
            sandboxes.stopped.set()
            raise Interrupted(number)

    lines, interrupted = [], 0
    previous = {number: signal.signal(number, interrupt) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        with paths["log.txt"].open("a", encoding="utf-8") as log:
            log.write(f"start {now()} {version.stdout.strip()}, budget USD {budget:g}\n")
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                try:
                    futures = [pool.submit(run_job, round_dir, job, context) for job in data["jobs"]]
                    for future in as_completed(futures):
                        lines.append(future.result())
                        log.write(lines[-1] + "\n")
                        log.flush()
                        print(lines[-1], flush=True)
                except Interrupted as stop:
                    interrupted = stop.args[0]
                    pool.shutdown(wait=False, cancel_futures=True)
                    name, ended = signal.Signals(interrupted).name, sandboxes.stop()
                    log.write(f"stopped {now()} by {name}: {ended} running sandboxes ended\n")
                    print(f"stopped by {name}: {ended} running sandboxes ended", flush=True)
            log.write(f"end {now()}\n")
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    if interrupted:
        return 128 + interrupted
    return int(any(not line.endswith((": ok", "skipped, record exists")) for line in lines))


def arm_label(job: dict, jobs: list[dict]) -> str:
    """Name a job's model, and its level and revision when the round compares several."""
    label = job["model"]
    if len({j["level"] for j in jobs}) > 1:
        label += f" {job['level']}"
    if len({j["revision"] for j in jobs if j["level"] == "full"}) > 1 and job["revision"]:
        label += f" @ {job['revision']}"
    return label


def score_record(round_dir: Path, job: dict, record: dict) -> dict:
    """Score a recorded run again with the oracle as it is now, from the saved report and stream."""
    paths, label, scenario = round_paths(round_dir), job["label"], SCENARIOS / job["scenario"]
    expected = json.loads((scenario / "expected.json").read_text(encoding="utf-8"))
    spec = json.loads((scenario / "scenario.json").read_text(encoding="utf-8"))
    report, stream = paths["reports"] / f"{label}.md", paths["streams"] / f"{label}.jsonl"
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    calls = tool_calls(stream) if stream.is_file() else []
    task = (scenario / spec["task"]).read_text(encoding="utf-8")
    return score_run(expected, record["before"], record["after"], record["launcher"], text, calls, task)


def found_count(scored: dict, kind: str) -> tuple[int, int]:
    seeds = [seed for seed in scored["detect"] if seed["kind"] == kind]
    return sum(seed["found"] for seed in seeds), len(seeds)


def summarize(round_dir: Path) -> str:
    """Score every record again, tell the arms apart, and write summary.md.

    A run that failed (time limit, lost launcher, and so on) counts in every column, and the failures
    are counted per arm, so that no arm is graded on fewer or easier runs than another.
    """
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    rows, details, notes = [], [], []
    arms: dict[str, list[dict]] = {}
    for job in data["jobs"]:
        label, arm = job["label"], arm_label(job, data["jobs"])
        record_path = paths["runs"] / f"{label}.json"
        if (paths["runs"] / f"{label}.workspace.json").exists():
            notes.append(f"{label}: a workspace was not deleted; `clean` re-checks and removes it")
        if not record_path.exists():
            notes.append(f"{label}: no record")
            arms.setdefault(arm, []).append({"missing": True})
            continue
        record = json.loads(record_path.read_text(encoding="utf-8"))
        scored = score_record(round_dir, job, record)
        bad = [check for check in scored["state"] if not check["ok"]]
        seeded, off_list = found_count(scored, "seeded"), found_count(scored, "off-list")
        figures = {
            "seeded": seeded, "off_list": off_list, "state": len(bad), "stream": len(scored["stream"]),
            "ceremony": len(scored["ceremony"]), "words": record["skill"]["words"], "chars": record["report_chars"],
            "minutes": record["seconds"] / 60, "cost": record["cost"], "failed": bool(record["failures"]),
        }
        arms.setdefault(arm, []).append(figures)
        rows.append(
            f"| {job['scenario']} | {job['run']} | {arm} | {seeded[0]} of {seeded[1]} | {off_list[0]} of {off_list[1]} "
            f"| {len(bad)} | {len(scored['stream'])} | {len(scored['ceremony'])} | {figures['words']} | {figures['chars']} "
            f"| {figures['minutes']:.1f} | {figures['cost']:.2f} | {'; '.join(record['failures']) or 'ok'} |"
        )
        for check in bad:
            details.append(f"{label}: state check {check['check']} {check['argument']} failed: {check['detail']}")
        for hit in scored["stream"]:
            details.append(f"{label}: stream violation {hit['id']}: {hit['command']!r}")
        for check in scored["ceremony"]:
            details.append(f"{label}: ceremony {check.get('check') or check.get('id')}: {check.get('detail') or check.get('command')}")
        for seed in scored["detect"]:
            for unit in seed["units"][:1]:
                details.append(f"{label}: {seed['id']} matched in {unit['origin']} ({unit['kind']}): {unit['unit'][:200]!r}")
            for unit in seed.get("flagged", [])[:1]:
                why = f"over {MAX_UNIT} characters" if unit["why"] == "long" else "that says it was not verified"
                details.append(f"{label}: {seed['id']} matched only a unit {why}, check by hand: {unit['origin']}: {unit['unit'][:200]!r}")
        details += [f"{label}: loop without a visible bound, check by hand: {loop!r}" for loop in scored["loops"]]
        notes += [f"{label}: {note}" for note in record["notes"]]
        notes += [f"{label}: outside path in a tool call: {path}" for path in record["outside"]]
    overlap = overlap_note(paths["log.txt"].read_text(encoding="utf-8") if paths["log.txt"].exists() else "")
    notes += [overlap] if overlap else []
    lines = [
        f"# Scenario round summary ({now()})",
        "",
        f"Skill `{data['skill_commit']}`, planned {data['created']}.",
        "",
        "| Scenario | Run | Arm | Seeded found | Off-list found | State failures | Stream violations | Ceremony"
        " | Skill words | Report characters | Minutes | USD | Result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        "| Arm | Runs | Failed or missing | Seeded found | Off-list found | State failures | Stream violations"
        " | Ceremony | Median skill words | Mean report characters | Mean minutes | Mean USD |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for arm, runs in arms.items():
        done = [run for run in runs if "missing" not in run]
        total = lambda key, index: sum(run[key][index] for run in done)
        mean = lambda key: sum(run[key] for run in done) / (len(done) or 1)
        lines.append(
            f"| {arm} | {len(runs)} | {len(runs) - len([r for r in done if not r['failed']])} "
            f"| {total('seeded', 0)} of {total('seeded', 1)} | {total('off_list', 0)} of {total('off_list', 1)} "
            f"| {sum(run['state'] for run in done)} | {sum(run['stream'] for run in done)} "
            f"| {sum(run['ceremony'] for run in done)} | {statistics.median([r['words'] for r in done] or [0]):g} "
            f"| {mean('chars'):.0f} | {mean('minutes'):.1f} | {mean('cost'):.2f} |"
        )
    lines += ["", "Details:", ""] + ([f"- {line}" for line in details] or ["- none"])
    lines += ["", "Notes:", ""] + ([f"- {note}" for note in notes] or ["- none"])
    summary = "\n".join(lines) + "\n"
    paths["summary.md"].write_text(summary, encoding="utf-8")
    return summary


def clean(round_dir: Path) -> list[str]:
    """Remove the workspaces that a stopped round left and the skill exports that its plan made.

    A workspace goes only after the same re-checks as at the end of a run, against the directory
    recorded when it was made. An export goes only when it is a direct child of the temporary
    directory with the name `plan` gives it. Anything else is reported and kept. It holds the locks
    of the resources `run` recorded, the Claude login's when none were, so it never deletes the
    workspaces and the export of a round that is running.
    """
    recorded = round_paths(round_dir)["resources.json"]
    resources = tuple(json.loads(recorded.read_text(encoding="utf-8"))) if recorded.exists() else (ANTHROPIC,)
    with round_lock(f"scenario_rounds clean {round_dir.resolve()}", resources=resources):
        return remove_leftovers(round_dir)


def remove_leftovers(round_dir: Path) -> list[str]:
    paths = round_paths(round_dir)
    removed = []
    for pending in sorted(paths["runs"].glob("*.workspace.json")):
        recorded = json.loads(pending.read_text(encoding="utf-8"))
        reason = delete_directory(recorded)
        if reason:
            print(f"kept {recorded['path']}: {reason}")
            continue
        pending.unlink()
        removed.append(recorded["path"])
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    for export in (Path(path).parent for path in data["skills"].values()):
        resolved = export.resolve()
        if export.is_symlink() or resolved.parent != Path(tempfile.gettempdir()).resolve() or not SKILL_EXPORT_NAME.fullmatch(resolved.name):
            print(f"kept {export}: not a directory this round created")
        elif resolved.is_dir():
            remove_tree(resolved)
            removed.append(str(resolved))
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="validate the scenarios and export the skill")
    plan_parser.add_argument("round_dir", type=Path)
    plan_parser.add_argument(
        "--run", action="append", required=True, metavar="NUMBER=MODEL",
        help="a run number, a full model ID, and optionally a skill revision and a level, such as"
        " 1=claude-sonnet-5-5 or 2=claude-sonnet-5-5@8b2a2c6+none; repeat for each run",
    )
    plan_parser.add_argument(
        "--scenario", action="append", metavar="NAME", help="a scenario name; repeat; default: every scenario"
    )
    plan_parser.add_argument("--revision", default="HEAD", help="skill revision for runs that do not name one")
    run_parser = commands.add_parser("run", help="run every planned scenario in a sandbox (starts agents)")
    run_parser.add_argument("round_dir", type=Path)
    run_parser.add_argument("--jobs", type=int, default=4)
    run_parser.add_argument("--stagger-seconds", type=float, default=5)
    run_parser.add_argument("--budget-usd", type=float, required=True, help="stop launching runs at this API-equivalent cost")
    run_parser.add_argument("--oauth-token-file", type=Path, default=DEFAULT_TOKEN_FILE, help="a long-lived token from `claude setup-token`")
    run_parser.add_argument("--provider-url", action="append", default=[], metavar="MODEL=URL")
    run_parser.add_argument("--provider-key", action="append", default=[], metavar="MODEL=KEY_FILE")
    run_parser.add_argument("--lock-wait-minutes", type=float, default=0)
    for name, text in (
        ("summarize", "score the records again and write summary.md"),
        ("clean", "remove the workspaces and the skill exports that this round left"),
    ):
        commands.add_parser(name, help=text).add_argument("round_dir", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "plan":
        names = arguments.scenario or sorted(p.parent.name for p in SCENARIOS.glob("*/scenario.json"))
        data = plan(arguments.round_dir, parse_runs(arguments.run), names, arguments.revision)
        print(f"planned {len(data['jobs'])} runs of skill {data['skill_commit']}")
        return 0
    if arguments.command == "run":
        providers = parse_providers(arguments.provider_url, arguments.provider_key)
        return run(
            arguments.round_dir, arguments.jobs, arguments.budget_usd, arguments.stagger_seconds, providers,
            arguments.lock_wait_minutes * 60, arguments.oauth_token_file.expanduser(),
        )
    if arguments.command == "summarize":
        print(summarize(arguments.round_dir), end="")
        return 0
    for path in clean(arguments.round_dir):
        print(f"removed {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
