"""Check the coordination-scenario runner: its fixtures, snapshots, oracle, sandbox, and rounds.

Nothing here calls a model. Tests that start a sandbox use a stand-in `claude` and skip, with a
reason, where `bwrap` cannot create a namespace.
"""

import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tools import scenario_rounds
from tools.evals import SETTINGS_OFF, git_environment

NOW = datetime(2026, 10, 18, 12, 30, 45, tzinfo=timezone.utc)


def git(repo, *arguments):
    """Read from a prepared repository with Git, without any host configuration."""
    return subprocess.run(
        ["git", *SETTINGS_OFF, *arguments], cwd=repo, env=git_environment(), capture_output=True,
        text=True, check=True,
    ).stdout


def write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode:
        path.chmod(mode)


def make_scenario(root, fixtures, files, minutes=15, name="scenario"):
    """Write a scenario directory: `files` maps paths under files/ to their text."""
    scenario = root / name
    scenario.mkdir()
    spec = {"tier": "E1", "minutes": minutes, "task": "task.md", "fixtures": fixtures}
    write(scenario / "scenario.json", json.dumps(spec))
    write(scenario / "task.md", "Do the task.\n")
    for name, text in files.items():
        write(scenario / "files" / name, text)
    return scenario


class TemporaryTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def prepare(self, fixtures, files, now=NOW):
        """Prepare a new scenario into a new workspace, which is `self.workspace` afterwards."""
        number = len(list(self.root.glob("scenario*")))
        scenario = make_scenario(self.root, fixtures, files, name=f"scenario{number}")
        self.workspace = self.root / f"workspace{number}"
        self.workspace.mkdir()
        return scenario_rounds.prepare_workspace(scenario, self.workspace, now)


class FixtureTests(TemporaryTestCase):
    REPO = {"kind": "repo", "path": "repo", "commits": [
        {"files": "one", "message": "feat: first"},
        {"files": "two", "message": "feat: second"},
    ]}
    FILES = {"one/app.py": "print(1)\n", "two/app.py": "print(2)\n", "two/extra.txt": "extra\n"}

    def commits(self, ref="HEAD"):
        lines = git(self.workspace / "repo", "log", "--format=%ct %an <%ae> %s", ref).splitlines()
        return [line.split(" ", 1) for line in lines]

    def test_a_repository_gets_one_commit_per_entry_with_a_fixed_identity_and_dates(self):
        with mock.patch.dict(os.environ, {"GIT_AUTHOR_NAME": "Someone", "GIT_CONFIG_GLOBAL": "/nonexistent"}):
            manifest = self.prepare([self.REPO], self.FILES)
        (second, subject2), (first, subject1) = self.commits()
        self.assertEqual(subject2, "Evaluation Fixture <fixture@example.invalid> feat: second")
        self.assertEqual(subject1, "Evaluation Fixture <fixture@example.invalid> feat: first")
        stamp = int(datetime(2026, 10, 18, 12, 30, tzinfo=timezone.utc).timestamp())
        self.assertEqual((int(second), int(first)), (stamp - 20 * 60, stamp - 30 * 60))
        self.assertEqual(manifest["repos"], ["repo"])
        self.assertEqual((self.workspace / "repo" / "app.py").read_text(), "print(2)\n")

    def test_an_entry_can_set_its_age_and_delete_files(self):
        fixture = {"kind": "repo", "path": "repo", "commits": [
            {"files": "one", "message": "feat: first", "minutes_ago": 300},
            {"files": "two", "message": "feat: second", "delete": ["app.py"], "minutes_ago": 100},
        ]}
        self.prepare([fixture], self.FILES)
        (second, _), (first, _) = self.commits()
        self.assertEqual(int(second) - int(first), 200 * 60)
        self.assertEqual(sorted(p.name for p in (self.workspace / "repo").iterdir() if p.name != ".git"), ["extra.txt"])

    def test_branches_and_later_commits_build_a_history_that_diverges(self):
        fixtures = [
            self.REPO,
            {"kind": "branch", "repo": "repo", "name": "feature", "from": "main", "commits": [
                {"files": "feature", "message": "feat: on a branch"}]},
            {"kind": "commits", "repo": "repo", "branch": "main", "commits": [
                {"files": "later", "message": "fix: on main after the cut"}]},
            {"kind": "branch", "repo": "repo", "name": "copy", "from": "feature"},
        ]
        files = self.FILES | {"feature/feature.txt": "f\n", "later/app.py": "print(3)\n"}
        self.prepare(fixtures, files)
        repo = self.workspace / "repo"
        self.assertEqual(git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip(), "main")
        self.assertEqual(git(repo, "rev-parse", "copy"), git(repo, "rev-parse", "feature"))
        self.assertEqual(git(repo, "rev-list", "--count", "main..feature").strip(), "1")
        self.assertEqual(git(repo, "rev-list", "--count", "feature..main").strip(), "1")
        self.assertEqual((repo / "app.py").read_text(), "print(3)\n")
        self.assertFalse((repo / "feature.txt").exists())
        self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_a_remote_receives_every_branch_that_exists_at_that_point(self):
        fixtures = [
            self.REPO,
            {"kind": "branch", "repo": "repo", "name": "early", "from": "main"},
            {"kind": "remote", "repo": "repo", "path": "origin.git"},
            {"kind": "branch", "repo": "repo", "name": "late", "from": "main"},
        ]
        manifest = self.prepare(fixtures, self.FILES)
        bare = self.workspace / "origin.git"
        heads = git(bare, "for-each-ref", "--format=%(refname)", "refs/heads").split()
        self.assertEqual(heads, ["refs/heads/early", "refs/heads/main"])
        self.assertEqual(git(self.workspace / "repo", "remote", "get-url", "origin").strip(), str(bare))
        self.assertEqual(manifest["remotes"], ["origin.git"])

    def test_a_worktree_holds_its_uncommitted_files_and_a_stash_keeps_its_message(self):
        fixtures = [
            self.REPO,
            {"kind": "branch", "repo": "repo", "name": "wip", "from": "main"},
            {"kind": "worktree", "repo": "repo", "path": "trees/wip", "branch": "wip", "uncommitted": "dirty"},
            {"kind": "stash", "repo": "repo", "message": "wip: before a rebase", "files": "stashed"},
        ]
        files = self.FILES | {"dirty/app.py": "print('dirty')\n", "stashed/app.py": "print('stashed')\n"}
        manifest = self.prepare(fixtures, files)
        tree = self.workspace / "trees" / "wip"
        self.assertEqual(git(tree, "status", "--porcelain").strip(), "M app.py")
        repo = self.workspace / "repo"
        self.assertEqual(git(repo, "status", "--porcelain"), "")
        self.assertIn("wip: before a rebase", git(repo, "stash", "list"))
        self.assertEqual((repo / "app.py").read_text(), "print(2)\n")
        self.assertEqual(manifest["worktrees"], ["trees/wip"])

    def test_files_render_times_and_revisions_and_keep_their_other_braces(self):
        fixtures = [
            self.REPO,
            {"kind": "file", "path": "notes/handoff.md", "source": "handoff.md"},
        ]
        text = ("{{now}} {{now-40m}} {{now+20m}} {{ now+5m }}\n{{sha:repo:main}} {{short:repo:HEAD~1}}\n"
                "keep {braces} and {single}\n")
        self.prepare(fixtures, self.FILES | {"handoff.md": text})
        repo = self.workspace / "repo"
        head, parent = git(repo, "rev-parse", "HEAD").strip(), git(repo, "rev-parse", "HEAD~1").strip()
        first, second, third = (self.workspace / "notes" / "handoff.md").read_text().splitlines()
        self.assertEqual(first, "2026-10-18T12:30Z 2026-10-18T11:50Z 2026-10-18T12:50Z 2026-10-18T12:35Z")
        self.assertEqual(second, f"{head} {parent[:7]}")
        self.assertEqual(third, "keep {braces} and {single}")

    def test_an_unknown_template_is_an_error(self):
        fixtures = [{"kind": "file", "path": "note.md", "source": "note.md"}]
        with self.assertRaises(SystemExit) as caught:
            self.prepare(fixtures, {"note.md": "{{nowish}}\n"})
        self.assertIn("unknown template {{nowish}}", str(caught.exception))

    def test_a_process_fixture_is_recorded_for_the_launcher_and_starts_nothing(self):
        fixture = {"kind": "process", "name": "live", "label": "sh wait.sh gate front-a", "seconds": 4000}
        manifest = self.prepare([fixture], {})
        self.assertEqual(manifest["processes"], [{"name": "live", "label": "sh wait.sh gate front-a", "seconds": 4000}])
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_a_fixture_cannot_leave_the_workspace_or_use_a_repository_before_it_exists(self):
        for fixtures in (
            [{"kind": "file", "path": "../outside.md", "source": "note.md"}],
            [{"kind": "file", "path": "/tmp/outside.md", "source": "note.md"}],
            [{"kind": "branch", "repo": "repo", "name": "x", "from": "main"}],
        ):
            with self.subTest(fixtures=fixtures), self.assertRaises(SystemExit):
                self.prepare(fixtures, {"note.md": "text\n"})

    def test_a_file_is_executable_only_when_its_source_is(self):
        fixture = {"kind": "repo", "path": "repo", "commits": [{"files": "one", "message": "feat: tools"}]}
        scenario = make_scenario(self.root, [fixture], {}, name="modes")
        write(scenario / "files" / "one" / "run.sh", "#!/bin/sh\n", 0o755)
        write(scenario / "files" / "one" / "data.txt", "data\n", 0o664)
        self.workspace = self.root / "modes-workspace"
        self.workspace.mkdir()
        scenario_rounds.prepare_workspace(scenario, self.workspace, NOW)
        repo = self.workspace / "repo"
        self.assertEqual((repo / "run.sh").stat().st_mode & 0o777, 0o755)
        self.assertEqual((repo / "data.txt").stat().st_mode & 0o777, 0o644)
        self.assertEqual(git(repo, "ls-files", "--stage").count("100755"), 1)


if __name__ == "__main__":
    unittest.main()
