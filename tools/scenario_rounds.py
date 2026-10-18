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

import json
import re
import shutil
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
