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
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
