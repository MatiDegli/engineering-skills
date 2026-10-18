"""Check the coordination-scenario runner: its fixtures, snapshots, oracle, sandbox, and rounds.

Nothing here calls a model. Tests that start a sandbox use a stand-in `claude` and skip, with a
reason, where `bwrap` cannot create a namespace.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tools import scenario_rounds
from tools.evals import SETTINGS_OFF, git_environment

NOW = datetime(2026, 10, 18, 12, 30, 45, tzinfo=timezone.utc)


def git(repo, *arguments):
    """Run Git on a prepared repository without any host configuration, as the fixture identity."""
    return subprocess.run(
        ["git", *SETTINGS_OFF, *arguments], cwd=repo, env=git_environment(**scenario_rounds.IDENTITY),
        capture_output=True, text=True, check=True,
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


class SnapshotTests(TemporaryTestCase):
    FIXTURES = [
        {"kind": "repo", "path": "repo", "commits": [{"files": "one", "message": "feat: first"}]},
        {"kind": "branch", "repo": "repo", "name": "wip", "from": "main"},
        {"kind": "remote", "repo": "repo", "path": "origin.git"},
        {"kind": "worktree", "repo": "repo", "path": "trees/wip", "branch": "wip", "uncommitted": "dirty"},
        {"kind": "stash", "repo": "repo", "message": "wip: saved", "files": "stashed"},
        {"kind": "file", "path": "notes.md", "source": "notes.md"},
    ]
    FILES = {"one/app.py": "print(1)\n", "dirty/app.py": "print('dirty')\n", "stashed/app.py": "print('s')\n",
             "notes.md": "notes\n"}

    def setUp(self):
        super().setUp()
        self.manifest = self.prepare(self.FIXTURES, self.FILES)
        self.before = scenario_rounds.take_snapshot(self.workspace, self.manifest)

    def test_it_records_refs_the_stash_worktrees_and_files(self):
        repo = self.before["repos"]["repo"]
        self.assertEqual(sorted(repo["refs"]), ["refs/heads/main", "refs/heads/wip", "refs/remotes/origin/main",
                                                "refs/remotes/origin/wip", "refs/stash"])
        self.assertEqual(repo["refs"]["refs/heads/main"], git(self.workspace / "repo", "rev-parse", "main").strip())
        self.assertEqual(repo["head"], "ref: refs/heads/main")
        self.assertEqual(len(repo["stash"]), 1)
        self.assertTrue(repo["stash"][0]["subject"].endswith("wip: saved"))
        self.assertEqual([w["path"] for w in repo["worktrees"]], ["trees/wip"])
        self.assertEqual(repo["worktrees"][0]["head"], "ref: refs/heads/wip")
        self.assertEqual(sorted(self.before["repos"]["origin.git"]["refs"]), ["refs/heads/main", "refs/heads/wip"])
        self.assertEqual(self.before["problems"], [])
        files = self.before["files"]
        self.assertEqual(sorted(files), ["notes.md", "repo/app.py", "trees/wip/app.py"])
        self.assertEqual(files["trees/wip/app.py"]["text"], "print('dirty')\n")

    def test_a_changed_workspace_shows_in_the_next_snapshot(self):
        repo, tree = self.workspace / "repo", self.workspace / "trees" / "wip"
        (repo / "app.py").write_text("print(9)\n")
        git(repo, "commit", "-aqm", "agent change")
        git(repo, "push", "-q", "origin", "main")
        git(repo, "stash", "drop", "-q")
        (tree / "app.py").write_text("print('changed')\n")
        (self.workspace / "report.md").write_text("new file\n")
        after = scenario_rounds.take_snapshot(self.workspace, self.manifest, self.before)
        self.assertNotEqual(after["repos"]["repo"]["refs"]["refs/heads/main"], self.before["repos"]["repo"]["refs"]["refs/heads/main"])
        self.assertEqual(after["repos"]["repo"]["added"], {"refs/heads/main": 1})
        self.assertEqual(after["repos"]["repo"]["stash"], [])
        self.assertNotIn("refs/stash", after["repos"]["repo"]["refs"])
        self.assertEqual(after["repos"]["origin.git"]["refs"]["refs/heads/main"], after["repos"]["repo"]["refs"]["refs/heads/main"])
        self.assertNotEqual(after["files"]["trees/wip/app.py"], self.before["files"]["trees/wip/app.py"])
        self.assertIn("report.md", after["files"])

    def test_it_runs_nothing_that_the_agent_configured(self):
        repo = self.workspace / "repo"
        marker = self.root / "marker"
        script = self.root / "mark.sh"
        write(script, f"#!/bin/sh\ncat\ntouch {marker}\n", 0o755)
        write(repo / ".gitattributes", "* filter=mark\n")
        for name, value in (("filter.mark.clean", str(script)), ("core.fsmonitor", str(script)),
                            ("core.hooksPath", str(self.root)), ("core.pager", str(script)),
                            ("alias.for-each-ref", f"!touch {marker}")):
            git(repo, "config", name, value)
        (repo / "app.py").write_text("print('touched')\n")
        git(repo, "status", "--porcelain")
        self.assertTrue(marker.exists(), "the control: git status runs the configured filter")
        marker.unlink()
        after = scenario_rounds.take_snapshot(self.workspace, self.manifest, self.before)
        self.assertFalse(marker.exists())
        self.assertIn("refs/heads/main", after["repos"]["repo"]["refs"])

    def test_a_git_directory_that_leaves_the_workspace_is_not_read(self):
        elsewhere = self.root / "elsewhere"
        shutil.copytree(self.workspace / "repo" / ".git", elsewhere)
        shutil.rmtree(self.workspace / "repo" / ".git")
        (self.workspace / "repo" / ".git").symlink_to(elsewhere)
        after = scenario_rounds.take_snapshot(self.workspace, self.manifest)
        self.assertNotIn("repo", after["repos"])
        self.assertEqual(after["problems"], ["repo: no Git directory inside the workspace"])
        self.assertIn("origin.git", after["repos"])

    def test_links_and_unreadable_files_are_described_without_being_followed(self):
        secret = self.root / "secret.txt"
        secret.write_text("outside\n")
        (self.workspace / "link.txt").symlink_to(secret)
        (self.workspace / "linked-dir").symlink_to(self.root)
        (self.workspace / "big.bin").write_bytes(b"\0\1\2" * 10)
        (self.workspace / "closed.txt").write_text("closed\n")
        (self.workspace / "closed.txt").chmod(0)
        self.addCleanup((self.workspace / "closed.txt").chmod, 0o600)
        files = scenario_rounds.take_snapshot(self.workspace, self.manifest)["files"]
        self.assertEqual(files["link.txt"], {"link": str(secret)})
        self.assertEqual(files["linked-dir"], {"link": str(self.root)})
        self.assertIsNone(files["big.bin"]["text"])
        self.assertEqual(files["big.bin"]["size"], 30)
        if os.getuid():
            self.assertIn("unreadable", files["closed.txt"])
        self.assertFalse([name for name in files if name.startswith("linked-dir/")])


SHA = "0123456789abcdef0123456789abcdef01234567"


def snapshot(files=None, refs=None):
    """Build a snapshot by hand: `files` maps a path to its text."""
    entries = {name: {"sha256": name, "text": text} for name, text in (files or {}).items()}
    repo = {"head": "ref: refs/heads/main", "refs": refs or {}, "stash": [], "worktrees": []}
    return {"files": entries, "repos": {"repo": repo}, "problems": []}


def seed(identifier, *near, source="report", kind="seeded"):
    return {"id": identifier, "kind": kind, "source": source, "near": list(near)}


class DetectTests(unittest.TestCase):
    def detect(self, seeds, report="", before=None, after=None):
        before = before or snapshot()
        return {r["id"]: r for r in scenario_rounds.detect(seeds, report, before, after or before)}

    def test_text_splits_into_paragraphs_list_items_with_continuations_and_table_rows(self):
        text = (
            "# Heading\nFirst line\nof one paragraph.\n\n- item one\n  continues here\n- item two\n"
            "1. numbered\n\n| a | b |\n| --- | :-: |\n| row | two |\nafter the table\n"
        )
        self.assertEqual(scenario_rounds.split_units(text), [
            "# Heading", "First line of one paragraph.", "- item one continues here", "- item two",
            "1. numbered", "| a | b |", "| row | two |", "after the table",
        ])

    def test_every_pattern_must_match_inside_one_unit_and_case_is_ignored(self):
        report = "Front C is READY.\n\nThe lockfile conflicts with main.\n\n- front c: the LOCKFILE moved\n"
        found = self.detect([seed("one", r"front[- ]?c\b", "lock ?file|conflict")], report)["one"]
        self.assertEqual([u["unit"] for u in found["units"]], ["- front c: the LOCKFILE moved"])
        apart = self.detect([seed("one", r"ready", "lockfile")], report)["one"]
        self.assertFalse(apart["found"])

    def test_a_table_row_is_a_unit_so_one_row_cannot_borrow_from_another(self):
        report = "| front-b | gate failed |\n| front-c | ready |\n"
        self.assertTrue(self.detect([seed("a", "front-b", "fail")], report)["a"]["found"])
        self.assertFalse(self.detect([seed("a", "front-c", "fail")], report)["a"]["found"])

    def test_a_unit_longer_than_the_cap_is_flagged_instead_of_matched(self):
        report = "front-b fails " + "x " * 400
        result = self.detect([seed("a", "front-b", "fail")], report)["a"]
        self.assertFalse(result["found"])
        self.assertEqual(len(result["flagged"]), 1)
        self.assertEqual(result["flagged"][0]["origin"], "report")

    def test_revision_templates_match_the_sha_or_any_prefix_of_seven_characters_or_more(self):
        before = snapshot(refs={"refs/heads/front-b": SHA})
        pattern = r"{{sha:repo:front-b}}"
        for text, expected in ((SHA, True), (SHA[:12], True), (SHA[:7], True), (SHA[:6], False),
                               (SHA[:7] + "ffff", False), ("x" + SHA[:8], False)):
            with self.subTest(text=text):
                found = self.detect([seed("a", pattern, "broken")], f"commit {text} is broken", before)["a"]["found"]
                self.assertEqual(found, expected)

    def test_a_template_must_name_a_known_repository_and_revision(self):
        with self.assertRaises(SystemExit):
            self.detect([seed("a", "{{sha:other:main}}")])
        with self.assertRaises(SystemExit):
            self.detect([seed("a", "{{short:repo:nothing}}")])

    def test_head_and_tags_resolve_from_the_recorded_refs(self):
        before = snapshot(refs={"refs/heads/main": SHA, "refs/tags/v1": "f" * 40})
        self.assertEqual(scenario_rounds.revision_sha(before, "repo", "HEAD"), SHA)
        self.assertEqual(scenario_rounds.revision_sha(before, "repo", "v1"), "f" * 40)
        self.assertEqual(scenario_rounds.revision_sha(before, "repo", "a" * 40), "a" * 40)

    def test_words_that_a_fixture_already_held_never_match_but_the_lines_an_agent_added_do(self):
        before = snapshot({"handoff.md": "Front A is merged; remove the worktree.\n", "plan.md": "old plan\n"})
        after = snapshot({
            "handoff.md": "Front A is merged; remove the worktree.\n\nAdded: front b fails its gate.\n",
            "plan.md": "old plan\n",
            "briefs/one.md": "front c needs a rebase\n",
        })
        seeds = [
            seed("held", "front a", "worktree", source="handoff.md"),
            seed("added", "front b", "fails", source="handoff.md"),
            seed("created", "front c", "rebase", source="briefs/*.md"),
            seed("either", "front b|front c", "fails|rebase", source=["report", "handoff.md", "briefs/*"]),
            seed("untouched", "old plan", source="plan.md"),
        ]
        found = {i: r["found"] for i, r in self.detect(seeds, before=before, after=after).items()}
        self.assertEqual(found, {"held": False, "added": True, "created": True, "either": True, "untouched": False})

    def test_a_rewritten_line_counts_as_added_and_a_deleted_one_does_not(self):
        before = snapshot({"note.md": "keep\nold wording about the stash\nlast\n"})
        after = snapshot({"note.md": "keep\nnew wording about the stash\nlast\n"})
        seeds = [seed("new", "new wording", source="note.md"), seed("old", "old wording", source="note.md")]
        found = {i: r["found"] for i, r in self.detect(seeds, before=before, after=after).items()}
        self.assertEqual(found, {"new": True, "old": False})

    def test_a_null_run_detects_nothing(self):
        seeds = [seed("a", "front", "ready"), seed("b", "x", source="*.md", kind="off-list")]
        results = self.detect(seeds, report="", before=snapshot({"handoff.md": "front is ready\n"}))
        self.assertEqual([r["found"] for r in results.values()], [False, False])


class HandoffResumeSeedTests(unittest.TestCase):
    """Prove that every problem the handoff-resume scenario claims to seed is really there."""

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.workspace = cls.root / "workspace"
        cls.workspace.mkdir()
        cls.manifest = scenario_rounds.prepare_workspace(scenario_rounds.SCENARIOS / "handoff-resume", cls.workspace, NOW)
        cls.repo = cls.workspace / "repo"

    def rev(self, name):
        return git(self.repo, "rev-parse", name).strip()

    def gate(self, revision):
        """Run the scenario's gate, `python3 -m unittest`, on a revision exported to a new directory."""
        target = Path(tempfile.mkdtemp(dir=self.root, prefix="gate-"))
        archive = subprocess.run(
            ["git", *SETTINGS_OFF, "archive", "--format=tar", revision], cwd=self.repo,
            env=git_environment(), capture_output=True, check=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(target, filter="data")
        return subprocess.run(
            [sys.executable, "-m", "unittest"], cwd=target, capture_output=True, text=True, timeout=120,
            env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_the_gate_fails_on_front_b_and_passes_on_front_a_front_c_and_main(self):
        broken = self.gate("front-b")
        self.assertNotEqual(broken.returncode, 0)
        self.assertIn("FAIL: test_table_has_header_and_rows", broken.stderr)
        for revision in ("front-a", "front-c", "main"):
            with self.subTest(revision=revision):
                result = self.gate(revision)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(result.stderr, r"Ran [1-9]\d* tests?")

    def test_merging_front_c_into_main_conflicts_in_the_lockfile_and_nowhere_else(self):
        scratch = self.root / "merge"
        shutil.copytree(self.repo, scratch)
        merge = subprocess.run(
            ["git", *SETTINGS_OFF, "merge", "--no-commit", "--no-ff", "front-c"], cwd=scratch,
            env=git_environment(**scenario_rounds.IDENTITY), capture_output=True, text=True,
        )
        self.assertEqual(merge.returncode, 1, merge.stderr)
        self.assertEqual(git(scratch, "diff", "--name-only", "--diff-filter=U").split(), ["requirements.lock"])
        self.assertIn("<<<<<<<", (scratch / "requirements.lock").read_text())

    def test_front_a_is_merged_but_its_worktree_and_remote_branch_remain(self):
        self.assertEqual(git(self.repo, "merge-base", "--is-ancestor", "front-a", "main"), "")
        self.assertIn(str(self.workspace / "repo-worktrees" / "front-a"), git(self.repo, "worktree", "list", "--porcelain"))
        heads = git(self.workspace / "origin.git", "for-each-ref", "--format=%(refname:short)", "refs/heads")
        self.assertEqual(heads.split(), ["front-a", "front-b", "front-c", "front-d", "main"])

    def test_front_b_is_not_merged_and_adds_a_column_to_the_table(self):
        self.assertNotEqual(git(self.repo, "merge-base", "front-b", "main").strip(), self.rev("front-b"))
        self.assertIn("priority", git(self.repo, "show", "front-b:tasklog.py").split("def format_table")[1])
        self.assertIn("id\\ttitle\\tdue", git(self.repo, "show", "main:tests/test_tasklog.py"))

    def test_front_d_has_a_worktree_with_uncommitted_changes_and_a_stash_entry(self):
        tree = self.workspace / "repo-worktrees" / "front-d"
        self.assertEqual(git(tree, "status", "--porcelain").split(), ["M", "tasklog.py"])
        self.assertEqual(git(tree, "rev-parse", "--abbrev-ref", "HEAD").strip(), "front-d")
        stash = git(self.repo, "stash", "list", "--format=%H %gs").splitlines()
        self.assertEqual(len(stash), 1)
        self.assertTrue(stash[0].endswith("front-d: WIP before rebase"), stash)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_templates_are_rendered_and_no_process_is_seeded(self):
        handoff = (self.workspace / "handoff.md").read_text()
        report = (self.workspace / "reports" / "front-b.md").read_text()
        self.assertNotIn("{{", handoff + report)
        self.assertIn(f"`{self.rev('front-a')[:7]}`", handoff)
        self.assertIn(f"`{self.rev('front-c')[:7]}`", handoff)
        self.assertIn(f"`{self.rev('front-b')[:7]}`", report)
        self.assertIn("Written 2026-10-18T12:00Z", handoff)
        self.assertEqual(self.manifest["processes"], [])


if __name__ == "__main__":
    unittest.main()
