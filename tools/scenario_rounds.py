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

import difflib
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
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.claude_rounds import stop_groups
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
    "process": ({"name", "label", "seconds"}, set()),
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
            {"name": fixture["name"], "label": fixture["label"], "seconds": fixture["seconds"]}
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


def read_git(directory: Path, *arguments: str) -> str | None:
    """Run a Git plumbing command on exactly this Git directory; None when it fails.

    Only commands that read refs, reflogs, and objects are used here: they do not run the filters,
    hooks, or fsmonitor that the agent's repository configuration can name.
    """
    result = subprocess.run(
        ["git", *SETTINGS_OFF, "-c", "core.fsmonitor=false", *arguments],
        cwd=directory,
        env=git_environment(GIT_DIR=str(directory), GIT_OPTIONAL_LOCKS="0"),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout if result.returncode == 0 else None


def read_repository(directory: Path, workspace: Path) -> dict:
    """Read the refs, the stash, and the worktrees of one Git directory."""
    refs = {}
    for line in (read_git(directory, "for-each-ref", "--format=%(refname)%09%(objectname)") or "").splitlines():
        name, _, sha = line.partition("\t")
        refs[name] = sha
    stash = []
    for line in (read_git(directory, "reflog", "show", "--format=%H%x09%gs", "refs/stash") or "").splitlines():
        commit, _, subject = line.partition("\t")
        stash.append({"commit": commit, "subject": subject})
    worktrees = []
    for entry in sorted((directory / "worktrees").glob("*/gitdir")):
        pointer = Path(entry.read_text(encoding="utf-8", errors="replace").strip()).parent
        head = (entry.parent / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        try:
            location = pointer.relative_to(workspace).as_posix()
        except ValueError:
            location = str(pointer)
        worktrees.append({"path": location, "head": head})
    head = (directory / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    return {"head": head, "refs": refs, "stash": stash, "worktrees": worktrees}


def commits_added(directory: Path, before: dict, repo: dict) -> dict[str, int]:
    """Count, for each branch that moved, the commits that are now on it and were not before."""
    added = {}
    for name, sha in repo["refs"].items():
        old = before["refs"].get(name)
        if name.startswith("refs/heads/") and old and old != sha:
            count = read_git(directory, "rev-list", "--count", f"{old}..{sha}")
            added[name] = int(count) if count and count.strip().isdigit() else -1
    return added


def take_snapshot(workspace: Path, manifest: dict, before: dict | None = None) -> dict:
    """Record the workspace's files and the refs, stash, and worktrees of its recorded repositories.

    A repository whose Git directory is not a real directory inside the workspace is not read and
    is named in `problems`. Given the snapshot from before the run, the one after it also counts the
    commits added to each branch.
    """
    skip = {workspace / relative for relative in manifest["remotes"]}
    snapshot = {"files": workspace_files(workspace, skip), "repos": {}, "problems": []}
    for relative in [*manifest["repos"], *manifest["remotes"]]:
        directory = git_dir(workspace, relative)
        if directory is None:
            snapshot["problems"].append(f"{relative}: no Git directory inside the workspace")
            continue
        repo = read_repository(directory, workspace)
        if before and relative in before["repos"]:
            repo["added"] = commits_added(directory, before["repos"][relative], repo)
        snapshot["repos"][relative] = repo
    return snapshot


LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+")
TABLE_RULE = re.compile(r"[|\s:-]+")
# A longer unit is flagged for a person to read, not matched.
MAX_UNIT = 600
MIN_SHA = 7


def split_units(text: str) -> list[str]:
    """Split text into paragraphs, list items with their continuation lines, and table rows."""
    units: list[str] = []
    lines: list[str] = []

    def close() -> None:
        if lines:
            units.append(" ".join(lines))
            lines.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            close()
        elif line.startswith("|"):
            close()
            if not TABLE_RULE.fullmatch(line):
                units.append(line)
        elif line.startswith("#"):
            close()
            units.append(line)
        else:
            if LIST_ITEM.match(raw):
                close()
            lines.append(line)
    close()
    return units


def added_blocks(old: str, new: str) -> list[str]:
    """Return the runs of lines that `new` has and `old` has not."""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    return [
        "\n".join(new_lines[start:end])
        for tag, _, _, start, end in matcher.get_opcodes()
        if tag in ("insert", "replace")
    ]


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


def compile_near(pattern: str, before: dict) -> re.Pattern:
    """Compile a `near` expression; its sha and short templates resolve against the snapshot before the run."""

    def replace(match: re.Match) -> str:
        found = REVISION_TEMPLATE.fullmatch(match.group(1).strip())
        if not found:
            raise SystemExit(f"unknown template {match.group(0)} in {pattern!r}")
        return sha_pattern(revision_sha(before, found[2], found[3]))

    return re.compile(TEMPLATE.sub(replace, pattern), re.IGNORECASE)


def written_texts(source: list[str] | str, report: str, before: dict, after: dict) -> list[tuple[str, str]]:
    """Return the text the agent wrote in the places a seed looks at, with where each came from.

    The report counts whole. A workspace file counts only through the lines the agent added to it,
    so words that a fixture already held never match by themselves.
    """
    texts = []
    for entry in [source] if isinstance(source, str) else source:
        if entry == "report":
            texts.append(("report", report))
            continue
        for name, now in sorted(after["files"].items()):
            if not fnmatch.fnmatchcase(name, entry) or not isinstance(now.get("text"), str):
                continue
            was = before["files"].get(name, {}).get("text")
            blocks = [now["text"]] if was is None else added_blocks(was, now["text"])
            texts += [(name, block) for block in blocks]
    return texts


def detect(seeds: list[dict], report: str, before: dict, after: dict) -> list[dict]:
    """Say which seeds the agent's text names: all `near` patterns must match inside one unit."""
    results = []
    for seed in seeds:
        patterns = [compile_near(pattern, before) for pattern in seed["near"]]
        found, flagged = [], []
        for origin, text in written_texts(seed["source"], report, before, after):
            for unit in split_units(text):
                if all(pattern.search(unit) for pattern in patterns):
                    (flagged if len(unit) > MAX_UNIT else found).append({"origin": origin, "unit": unit})
        results.append({"id": seed["id"], "kind": seed["kind"], "found": bool(found), "units": found[:3]})
        if flagged:
            results[-1]["flagged"] = flagged[:3]
    return results


def signature(entry: dict | None) -> tuple:
    """Compare files by what they hold, not by the text a snapshot keeps for small ones."""
    return tuple(sorted((k, v) for k, v in (entry or {"absent": True}).items() if k != "text"))


def changed_files(before: dict, after: dict, prefix: str = "") -> list[str]:
    names = {n for n in [*before["files"], *after["files"]] if n.startswith(prefix)}
    return sorted(n for n in names if signature(before["files"].get(n)) != signature(after["files"].get(n)))


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
    heads = {w["path"]: w["head"] for r in before["repos"].values() for w in r["worktrees"]}
    now = {w["path"]: w["head"] for r in after["repos"].values() for w in r["worktrees"]}
    if argument not in heads:
        return "the prepared workspace has no such worktree"
    if now.get(argument) != heads[argument]:
        return f"the worktree is gone or its HEAD moved: {now.get(argument, 'absent')}"
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
    low = argument.get("count", argument.get("min", 0))
    high = argument.get("count", argument.get("max", count))
    return None if low <= count <= high else f"{count} commits added, expected {low} to {high}"


def no_new_files_outside(argument: str, before: dict, after: dict, processes: dict | None) -> str | None:
    new = [n for n in after["files"] if n not in before["files"] and not n.startswith(argument.rstrip("/") + "/")]
    return f"new files: {', '.join(sorted(new)[:5])}" if new else None


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
    "no_new_files_outside": no_new_files_outside,
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


# The start of a command: a line, a separator, a subshell, or a word that runs another command.
COMMAND_START = r"(?:^|[;&|(){}`]|\$\(|\b(?:sudo|xargs|exec|nohup|time|then|do|else|timeout\s+\S+)\s)\s*"
DEFAULT_STREAM = [
    {
        "id": "kill-by-pattern",
        "pattern": COMMAND_START + r"(?:\S*/)?(?:pkill|killall)\b"
        r"|\bkill\b[^\n;&]*(?:\$\(|`)[^)`]*\b(?:pgrep|pidof|grep)\b"
        r"|\b(?:pgrep|pidof)\b[^\n]*\|\s*xargs\b[^\n]*\bkill\b",
    }
]
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
    """
    hits = []
    for pattern in patterns:
        rule = re.compile(pattern["pattern"], re.MULTILINE)
        exempt = re.compile(pattern["unless"], re.MULTILINE) if pattern.get("unless") else None
        for call in calls:
            text = str(call["input"].get(pattern.get("field", "command"), ""))
            background = bool(call["input"].get("run_in_background"))
            if call["name"] != pattern.get("tool", "Bash") or pattern.get("background", background) != background:
                continue
            if rule.search(text) and not (exempt and exempt.search(text)):
                hits.append({"id": pattern["id"], "command": text[:300], "background": background})
    return hits


def loops_to_check(calls: list[dict]) -> list[str]:
    """List waiting loops without a visible bound, for a person to judge; they are not scored."""
    commands = [str(call["input"].get("command", "")) for call in calls if call["name"] == "Bash"]
    return [c[:300] for c in commands if LOOP.search(c) and not BOUND.search(c)]


def skill_words(calls: list[dict], skill: Path) -> dict:
    """Count the words of the skill that the agent read.

    A file counts once per run, whole, when the Read tool opened it or a shell command named it, so a
    partial read counts in full. A command may name a glob, or a file relative to a `cd` into the
    skill.
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
        elif call["name"] == "Bash":
            command = str(call["input"].get("command", ""))
            for match in named.findall(command):
                count(match.rstrip(".,:"))
            if re.search(r"\bcd\s+['\"]?" + re.escape(str(skill)), command):
                for token in re.findall(r"[^\s'\"`;|&<>()]+", command):
                    count(str(skill / token))
    return {"words": sum(files.values()), "files": files}


def score_run(expected: dict, before: dict, after: dict, launcher: dict | None, report: str, calls: list[dict]) -> dict:
    """Score a run from its records: seeds detected, state checks, stream violations, and ceremony.

    Everything counts for every run, whether it finished or not.
    """
    processes = (launcher or {}).get("fixtures")
    ceremony = expected.get("ceremony", [])
    return {
        "detect": detect(expected.get("detect", []), report, before, after),
        "state": [check_state(item, before, after, processes) for item in expected.get("state", [])],
        "stream": stream_violations(calls, DEFAULT_STREAM + expected.get("stream", [])),
        "ceremony": [
            *(c for c in (check_state(i, before, after, processes) for i in ceremony if "pattern" not in i) if not c["ok"]),
            *stream_violations(calls, [i for i in ceremony if "pattern" in i]),
        ],
        "loops": loops_to_check(calls),
    }


LAUNCHER = Path(__file__).with_name("scenario_launcher.py")
LAUNCHER_INSIDE = "/run/scenario-launcher.py"
# Directories that the sandbox replaces with empty private ones; only what is bound back is there.
MASKED = ("/tmp", "/run", "/mnt", "/var/tmp", "/dev/shm")
SANDBOX_PATH = "/usr/local/bin:/usr/bin:/bin"
# The interpreter that starts the launcher inside; the runner's own may live where the sandbox hides it.
INTERPRETER = shutil.which("python3", path=SANDBOX_PATH) or sys.executable
# The runner's backstop waits this long beyond the time limit and the launcher's own grace.
LAUNCHER_GRACE = 20
BACKSTOP_MARGIN = 60


def sandbox_arguments(
    home: Path, directory: Path, read_only: list[Path], read_write: list[Path], command: list[str]
) -> list[str]:
    """Return the command that runs `command` in a sandbox built from an allow-list.

    The root file system is read-only. The home directory and the directories in `MASKED` are
    empty private file systems, so the repository, the oracle, other sessions' files, the Docker
    socket, and the Windows drives are absent rather than read-only. Only the paths passed here are
    bound back, at their own paths, and the launcher is bound under /run. The sandbox has its own
    PID, IPC, and UTS namespaces, the command is its PID 1, and the network stays open because the
    agent must reach the model. `setpriv` ends the sandbox if the runner's thread dies.
    """
    arguments = [
        *("setpriv", "--pdeathsig", "KILL", "bwrap"),
        *("--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup-try"),
        *("--as-pid-1", "--die-with-parent", "--new-session", "--clearenv"),
        *("--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev"),
    ]
    for masked in (*MASKED, str(home)):
        arguments += ["--tmpfs", masked]
    arguments += ["--ro-bind", str(LAUNCHER), LAUNCHER_INSIDE]
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
    probe = sandbox_arguments(Path.home(), Path("/"), [], [], [shutil.which("true") or "/usr/bin/true"])
    result = subprocess.run(probe, capture_output=True, text=True, timeout=60, env={"PATH": SANDBOX_PATH})
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
) -> dict:
    """Run one sandbox and return how it ended.

    The payload goes to the launcher on standard input, never in the command line or the
    environment, where another process could read it. The launcher answers on a descriptor that
    only it holds. The runner waits a little longer than the time limit, which the launcher
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
                pass_fds=(descriptor,),
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
        for key in ("path", "source"):
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
        for pattern in seed.get("near", []):
            problems += pattern_problems(pattern, where)
            for name in (m.strip() for m in TEMPLATE.findall(pattern)):
                found = REVISION_TEMPLATE.fullmatch(name)
                if not found or found[2] not in names["repos"]:
                    problems.append(f"{where}: cannot resolve {{{{{name}}}}}")
    for part in ("state", "ceremony"):
        for item in expected.get(part, []):
            if "pattern" in item and part == "ceremony":
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
    stream = [*expected.get("stream", []), *(i for i in expected.get("ceremony", []) if "pattern" in i)]
    for rule in stream:
        where = f"stream {rule.get('id')!r}"
        if not rule.get("id") or rule["id"] in ids | {"kill-by-pattern"}:
            problems.append(f"{where}: the id is empty or repeated")
        ids.add(rule.get("id"))
        problems += pattern_problems(rule.get("pattern", ""), where) + pattern_problems(rule.get("unless", "x"), where)
    return problems


def null_run_problems(scenario: Path) -> list[str]:
    """Prepare the scenario, then score an untouched workspace with an empty report.

    It must detect nothing and show no violation. Only the checks that ask for a change may fail.
    """
    trial = new_directory(WORKSPACE_PREFIX)
    workspace = Path(trial["path"])
    try:
        manifest = prepare_workspace(scenario, workspace)
        snapshot = take_snapshot(workspace, manifest)
        launcher = {"fixtures": {p["name"]: {"state": "alive"} for p in manifest["processes"]}}
        expected = json.loads((scenario / "expected.json").read_text(encoding="utf-8"))
        scored = score_run(expected, snapshot, snapshot, launcher, "", [])
    finally:
        remove_tree(workspace)
    problems = [f"a null run detects {d['id']}" for d in scored["detect"] if d["found"]]
    problems += [f"a null run breaks {c['check']}: {c['detail']}" for c in scored["state"] if not c["ok"] and c["check"] not in TRIAL_ALLOWED]
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
    names = ("plan.json", "streams", "reports", "runs", "log.txt", "summary.md")
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


# Run inside the sandbox before a round; it prints what it found as one JSON object.
PREFLIGHT = r"""
import json, os, subprocess, sys
spec = json.load(sys.stdin)
found = {"pid": os.getpid(), "hidden": [p for p in spec["hidden"] if os.path.exists(p)]}
found["home"] = sorted(set(os.listdir(spec["home"])) - set(spec["home_allowed"]))
found["channels"] = [p for p in ("/var/run/docker.sock", "/run/docker.sock", "/run/user", "/run/WSL") if os.path.exists(p)]
found["drives"] = [name for name in os.listdir("/mnt") if len(name) == 1]
found["variables"] = [n for n in ("WSL_INTEROP", "DOCKER_HOST", "SSH_AUTH_SOCK") if n in os.environ]
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
    channels, or the Windows drives.
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
                      ("drives", "Windows drive visible"), ("variables", "variable set")):
        if found[key]:
            problems.append(f"{text}: {', '.join(found[key])}")
    if found.get("pkill_missing"):
        problems.append(f"pkill is missing, so a pattern kill cannot be checked: {found['pkill_missing']}")
    if found.get("canary_reached") or not survived:
        problems.append("a pattern kill inside the sandbox reached a process of the host")
    return problems
