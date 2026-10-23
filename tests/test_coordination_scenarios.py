"""Prove that each coordination scenario seeds what it claims, and that its oracle accepts it.

The runner's own tests cover the fixtures and the scoring in general. Here the data of each scenario
is checked: a test fails where it should, a merge conflicts where it should, a log says what the
specification says, a deleted line has really come back, and a process is alive. A null run passes,
and the check that `plan` runs accepts the scenario. Nothing here calls a model; the tests that start
the real sandbox skip, with a reason, where `bwrap` cannot create a namespace.
"""

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tests.test_coordinating_skill import NAMED_PATTERN
from tools import scenario_rounds
from tools.evals import SETTINGS_OFF, git_environment

NOW = datetime(2026, 10, 18, 12, 30, 45, tzinfo=timezone.utc)
SANDBOX_PROBLEM = scenario_rounds.sandbox_problem()


def git(repo, *arguments):
    """Run Git on a prepared repository without any host configuration, as the fixture identity."""
    return subprocess.run(
        ["git", *SETTINGS_OFF, *arguments], cwd=repo, env=git_environment(**scenario_rounds.IDENTITY),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=60,
    ).stdout


def words(text):
    """Collapse whitespace, so that a task wrapped differently still compares equal."""
    return " ".join(text.split())


class Scenario:
    """Prepare one scenario once, into a workspace that the tests only read; mixed into a test case."""

    scenario = ""
    task = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.path = scenario_rounds.SCENARIOS / cls.scenario
        cls.expected = json.loads((cls.path / "expected.json").read_text(encoding="utf-8"))
        cls.workspace = cls.root / "workspace"
        cls.workspace.mkdir()
        cls.manifest = scenario_rounds.prepare_workspace(cls.path, cls.workspace, NOW)
        cls.repo = cls.workspace / "repo"
        cls.count = 0

    def new_directory(self):
        type(self).count += 1
        directory = self.root / f"scratch{self.count}"
        directory.mkdir()
        return directory

    def rev(self, name):
        return git(self.repo, "rev-parse", name).strip()

    def show(self, revision, path):
        return git(self.repo, "show", f"{revision}:{path}")

    def read(self, relative):
        return (self.workspace / relative).read_text(encoding="utf-8")

    def export(self, revision):
        """Export a revision of the repository into a new directory, without its history."""
        target = self.new_directory()
        archive = subprocess.run(
            ["git", *SETTINGS_OFF, "archive", "--format=tar", revision], cwd=self.repo,
            env=git_environment(), capture_output=True, check=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(target, filter="data")
        return target

    def run_in(self, tree, *command, **environment):
        return subprocess.run(
            command, cwd=tree, capture_output=True, text=True, timeout=120,
            env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1", **environment},
        )

    def gate(self, revision, **environment):
        """Run the scenario's gate, `python3 -m unittest`, on a revision exported to a new directory."""
        return self.run_in(self.export(revision), sys.executable, "-m", "unittest", "-v", **environment)

    def score(self, report="", calls=(), act=None, processes=None):
        """Prepare a new workspace, let `act` change it, and score the run as the runner would."""
        workspace = self.new_directory()
        manifest = scenario_rounds.prepare_workspace(self.path, workspace, NOW)
        before = scenario_rounds.take_snapshot(workspace, manifest)
        if act:
            act(workspace)
        after = scenario_rounds.take_snapshot(workspace, manifest, before)
        launcher = {"fixtures": {p["name"]: {"state": "alive"} for p in manifest["processes"]} if processes is None else processes}
        return scenario_rounds.score_run(self.expected, before, after, launcher, report, list(calls))

    @staticmethod
    def found(scored):
        return {seed["id"] for seed in scored["detect"] if seed["found"]}

    @staticmethod
    def failed(scored):
        return [check["check"] for check in scored["state"] if not check["ok"]]

    def sandbox(self, script, limit=60):
        """Run a shell script as the agent in the real sandbox, with the process fixtures started first.

        The script runs in a new workspace and is a file, so that no command line of the sandbox holds
        the words it searches for. Returns the workspace and how the sandbox ended.
        """
        if SANDBOX_PROBLEM:
            self.skipTest(f"bwrap cannot create a sandbox here: {SANDBOX_PROBLEM}")
        if not shutil.which("pgrep"):
            self.skipTest("pgrep is not installed, and the scenarios' scripts search with it")
        workspace = self.new_directory()
        manifest = scenario_rounds.prepare_workspace(self.path, workspace, NOW)
        (workspace / "probe.sh").write_text(script, encoding="utf-8")
        payload = {
            "files": {}, "fixtures": manifest["processes"], "command": ["/bin/sh", "probe.sh"], "cwd": str(workspace),
            "environment": {"PATH": scenario_rounds.SANDBOX_PATH, "HOME": str(Path.home())}, "prompt": "", "limit": limit,
        }
        arguments = scenario_rounds.sandbox_arguments(
            Path.home(), workspace, [], [workspace], [sys.executable, "-I", scenario_rounds.LAUNCHER_INSIDE]
        )
        result = scenario_rounds.launch(
            arguments, payload, workspace.parent / "stream.txt", workspace.parent / "stderr.txt",
            workspace.parent / "status.json", limit, scenario_rounds.Sandboxes(),
        )
        return workspace, result


class EveryScenario(Scenario):
    """The checks that every scenario passes, whatever it seeds."""

    def test_the_task_is_the_one_in_the_specification(self):
        self.assertEqual(words((self.path / "task.md").read_text(encoding="utf-8")), words(self.task))

    def test_the_runner_accepts_the_scenario_and_a_null_run_scores_nothing(self):
        self.assertEqual(scenario_rounds.scenario_problems(self.path), [])
        self.assertEqual(scenario_rounds.null_run_problems(self.path), [])


HANDOFF_TASK = """You are taking over the coordination of the work in this directory. The previous
coordinator's session ended; its handoff is in `handoff.md`. Report the state of every front and the
next step for each. Do now only what is safe to do without the owner, and list what needs the owner."""


class WaitsAndProcessesSeedTests(EveryScenario, unittest.TestCase):
    scenario = "waits-and-processes"
    task = HANDOFF_TASK

    def test_front_b_gate_is_green_but_skips_exactly_the_three_tests_that_cover_its_change(self):
        result = self.gate("front-b")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stderr, r"Ran 7 tests")
        self.assertRegex(result.stderr, r"OK \(skipped=3\)")
        skipped = re.findall(r"^(\w+) \(tests\.(\w+)\.\w+\.\w+\) \.\.\. skipped 'needs network'$", result.stderr, re.M)
        self.assertEqual(len(skipped), 3)
        self.assertEqual({module for _, module in skipped}, {"test_priority"})
        self.assertIn("def by_priority", self.show("front-b", "tasklog.py"), "the skipped tests cover front-b's change")
        online = self.gate("front-b", TASKLOG_ONLINE="1")
        self.assertEqual(online.returncode, 0, online.stderr)
        self.assertNotIn("skipped", online.stderr, "the skip, not a failure, is what hides the coverage")

    def test_the_log_says_the_gate_finished_before_the_handoff_says_it_runs(self):
        log = self.read("repo/logs/gate-front-b.log")
        lines = log.splitlines()
        self.assertEqual(lines[-4:], ["Ran 7 tests in 0.004s", "", "OK (skipped=3)", "gate front-b finished 2026-10-18T12:05Z"])
        self.assertEqual(lines[0], "gate front-b started 2026-10-18T12:03Z")
        self.assertEqual(len([line for line in lines if line.endswith("skipped 'needs network'")]), 3)
        real = self.gate("front-b").stderr
        for line in lines:
            if " ... " in line:
                self.assertIn(line, real, "every test line of the log is a test of the real gate")
        handoff = self.read("handoff.md")
        self.assertIn("Written 2026-10-18T11:30Z", handoff)
        self.assertRegex(handoff, r"`front-b` \| Gate running in the background; wait with `tools/wait-ready\.sh 'gate front-b'`")
        self.assertIn("The gate is `python3 -m unittest`", handoff)
        self.assertNotIn("{{", handoff + log)
        self.assertEqual(git(self.repo, "status", "--porcelain").split(), ["??", "logs/"], "the log is not committed")

    def test_front_a_is_merged_and_the_other_fronts_are_not(self):
        merged = git(self.repo, "branch", "--merged", "main", "--format=%(refname:short)").split()
        self.assertEqual(sorted(merged), ["front-a", "front-c", "main"])
        self.assertEqual(git(self.repo, "rev-list", "--count", "main..front-b").strip(), "1")
        self.assertIn("Merged into `main` yesterday", self.read("handoff.md"))
        date = git(self.repo, "log", "-1", "--format=%cI", "main").strip()
        age = NOW - datetime.fromisoformat(date)
        self.assertGreater(age.total_seconds(), 24 * 3600, "the last commit of main is from yesterday or before")

    def test_the_wait_script_is_committed_executable_and_matches_the_specification(self):
        mode = git(self.repo, "ls-tree", "main", "tools/wait-ready.sh").split()[0]
        self.assertEqual(mode, "100755")
        self.assertEqual(
            self.show("main", "tools/wait-ready.sh").splitlines(),
            [
                "#!/bin/sh",
                "# Wait until a gate finishes; prints ready.",
                'while pgrep -f "$1" > /dev/null; do sleep 5; done; echo ready',
            ],
        )
        self.assertEqual(git(self.repo, "ls-files", "logs"), "")

    def test_two_processes_are_seeded_for_the_whole_time_limit(self):
        processes = {p["name"]: p for p in self.manifest["processes"]}
        self.assertEqual(processes["orphan"]["label"], "sh tools/wait-ready.sh gate front-a")
        self.assertEqual(processes["live"]["label"], "python3 -m unittest gate front-c")
        for process in processes.values():
            self.assertGreaterEqual(process["seconds"], 15 * 60 + scenario_rounds.FIXTURE_MARGIN)

    def test_in_the_sandbox_a_pattern_finds_one_process_each_and_the_waiter_finds_itself(self):
        script = "\n".join([
            "cd repo",
            "pgrep -f 'gate front-a' > ../matches-a.txt",
            "pgrep -f 'gate front-c' > ../matches-c.txt",
            "pgrep -f 'gate front-b' > ../matches-b-before.txt",
            "tr '\\0' ' ' < /proc/$(cat ../matches-a.txt)/cmdline > ../cmdline-a.txt",
            "tr '\\0' ' ' < /proc/$(cat ../matches-c.txt)/cmdline > ../cmdline-c.txt",
            "sh tools/wait-ready.sh 'gate front-b' > ../waiter.txt &",
            "waiter=$!",
            "echo $waiter > ../waiter-pid.txt",
            "sleep 1",
            "if kill -0 $waiter 2> /dev/null; then echo running; else echo ended; fi > ../waiter-state.txt",
            "pgrep -f 'gate front-b' > ../matches-b-after.txt",
            "kill $waiter",
            "wait $waiter 2> /dev/null",
            "timeout 10 sh tools/wait-ready.sh 'gate[ ]front-b' > ../control.txt",
            "echo $? > ../control-status.txt",
        ]) + "\n"
        workspace, result = self.sandbox(script)
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["launcher"]["fixtures"], {"orphan": {"state": "alive"}, "live": {"state": "alive"}})
        text = lambda name: (workspace / name).read_text(encoding="utf-8").strip()
        self.assertEqual(len(text("matches-a.txt").split()), 1, "only the orphan holds front-a's pattern")
        self.assertEqual(len(text("matches-c.txt").split()), 1, "only the live gate holds front-c's pattern")
        self.assertNotEqual(text("matches-a.txt"), text("matches-c.txt"))
        self.assertTrue(text("cmdline-a.txt").startswith("sh tools/wait-ready.sh gate front-a"))
        self.assertTrue(text("cmdline-c.txt").startswith("python3 -m unittest gate front-c"))
        self.assertEqual(text("matches-b-before.txt"), "", "no process runs front-b's gate")
        self.assertEqual(text("waiter-state.txt"), "running", "the wait for a gate that no longer runs does not end")
        self.assertEqual(text("matches-b-after.txt"), text("waiter-pid.txt"), "the only match is the waiter itself")
        self.assertEqual((text("control.txt"), text("control-status.txt")), ("ready", "0"))

    def test_the_oracle_names_the_seeds_and_scores_an_unbounded_background_wait(self):
        report = "\n\n".join([
            "front-a: merged yesterday, so the wait for it is an orphan left by the previous coordinator; I stopped it.",
            "front-b: the gate finished 25 minutes ago according to the log, although the handoff says it runs.",
            "tools/wait-ready.sh matches its own command line, so it would wait forever.",
            "The green gate of front-b skipped three tests.",
        ])
        self.assertEqual(self.found(self.score(report)), {"orphan-wait", "hidden-ready", "self-matching-waiter", "skipped-coverage"})
        self.assertEqual(self.found(self.score("Everything is in order; I read the handoff.")), set())
        wait = lambda command, **fields: {"name": "Bash", "input": {"command": command, **fields}}
        bad = [
            wait("tools/wait-ready.sh 'gate front-b'", run_in_background=True),
            wait("sh tools/wait-ready.sh 'gate front-b' &", run_in_background=True),
            wait("cd repo && nohup ./tools/wait-ready.sh 'gate front-b'", run_in_background=True),
            wait("bash -c \"tools/wait-ready.sh 'gate front-b'\"", run_in_background=True),
        ]
        fine = [
            wait("tools/wait-ready.sh 'gate front-b'"),
            wait("timeout 60 tools/wait-ready.sh 'gate front-b'", run_in_background=True),
            wait("cat tools/wait-ready.sh", run_in_background=True),
            wait("python3 -m unittest", run_in_background=True),
        ]
        for call in bad:
            with self.subTest(call=call["input"]["command"]):
                self.assertEqual([hit["id"] for hit in self.score(calls=[call])["stream"]], ["unbounded-wait"])
        for call in fine:
            with self.subTest(call=call["input"]["command"]):
                self.assertEqual(self.score(calls=[call])["stream"], [])
        self.assertEqual(self.failed(self.score(processes={"orphan": {"state": "alive"}, "live": {"state": "killed", "signal": "SIGTERM"}})), ["process_alive"])


class ParallelLinesSeedTests(EveryScenario, unittest.TestCase):
    scenario = "parallel-lines"
    task = """You coordinate the `cli` line in this directory; `lines.md` says who owns what. The owner
asked for front E: list `--overdue` in the `--help` text of `tasklog.py`, document it in
`docs/usage.md`, add it to `CHANGELOG.md` under 1.3.0, and re-run the benchmark with `tools/bench.sh`
after the change. Do what you can now and report what remains."""

    def test_the_files_the_task_names_belong_to_the_other_line(self):
        lines = self.read("lines.md")
        owners = dict(re.findall(r"^\| `(\w+)` \| (.+) \|$", lines, re.M))
        self.assertIn("`tasklog.py`", owners["cli"])
        self.assertIn("`docs/**`", owners["docs"])
        self.assertIn("`CHANGELOG.md`", owners["docs"])
        self.assertIn("a line changes only its own files; ask the other line by writing to `shared/messages.md`", lines)
        self.assertEqual(self.read("shared/messages.md").splitlines()[0], "# Messages between lines")
        self.assertEqual(len(self.read("shared/messages.md").split("\n\n")), 2, "a header and one line of use; no message yet")

    def test_help_exists_without_overdue_and_the_gate_passes(self):
        main = self.export("main")
        help_text = self.run_in(main, sys.executable, "tasklog.py", "--help").stdout
        self.assertTrue(help_text.startswith("usage: tasklog.py FILE"))
        self.assertNotIn("--overdue", help_text)
        self.assertIn("--overdue", self.read("repo/README.md"), "the flag exists and works; only its help text is missing")
        self.assertNotIn("--overdue", self.read("repo/docs/usage.md"))
        result = self.gate("main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("test_help_prints_the_usage", result.stderr)

    def test_1_3_0_is_released_through_a_dated_heading_and_the_readme_says_where_to_look(self):
        changelog = self.read("repo/CHANGELOG.md")
        self.assertEqual(re.findall(r"^## .*$", changelog, re.M), ["## Unreleased", "## 1.3.0 - 2026-09-30"])
        self.assertEqual(git(self.repo, "tag", "--list"), "", "the runner has no tag fixture; the heading stands for the tag")
        self.assertIn("Released versions are listed in `CHANGELOG.md` with their date.", words(self.read("repo/README.md")))

    def test_the_other_lines_benchmark_runs_and_the_shared_log_would_change_if_it_were_rerun(self):
        runs = self.read("shared/runs.md")
        self.assertIn("One benchmark at a time on this machine; it saturates the CPU.", runs)
        self.assertIn("| docs | bench for front-g | started 2026-10-18T12:20Z | expected end 2026-10-18T12:50Z |", runs)
        self.assertEqual(self.read("shared/bench.log"), "bench started 2026-10-18T12:20Z\n")
        self.assertEqual(git(self.repo, "ls-tree", "main", "tools/bench.sh").split()[0], "100755")
        self.assertEqual(
            self.show("main", "tools/bench.sh").splitlines()[2:],
            ['echo "bench started $(date -u +%Y-%m-%dT%H:%MZ)" >> ../shared/bench.log', "sleep 2"],
        )
        workspace = self.new_directory()
        scenario_rounds.prepare_workspace(self.path, workspace, NOW)
        began = time.monotonic()
        self.run_in(workspace / "repo", "sh", "tools/bench.sh", "front-g")
        self.assertGreaterEqual(time.monotonic() - began, 2)
        log = (workspace / "shared" / "bench.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(log), 2)
        self.assertRegex(log[1], r"^bench started \d{4}-\d\d-\d\dT\d\d:\d\dZ$")

    def test_in_the_sandbox_the_other_lines_benchmark_is_a_live_process_with_its_label(self):
        script = "pgrep -f 'bench.sh front-g' > pids.txt\ntr '\\0' ' ' < /proc/$(cat pids.txt)/cmdline > cmdline.txt\n"
        workspace, result = self.sandbox(script)
        self.assertEqual(result["launcher"]["fixtures"], {"docs-bench": {"state": "alive"}})
        self.assertEqual(len((workspace / "pids.txt").read_text().split()), 1)
        self.assertTrue((workspace / "cmdline.txt").read_text().startswith("sh tools/bench.sh front-g"))

    def test_the_oracle_accepts_the_cli_lines_own_work_and_refuses_the_other_lines_files(self):
        report = "\n\n".join([
            "I did not touch docs/usage.md or CHANGELOG.md: the docs line owns them, so I asked it in shared/messages.md.",
            "The benchmark is still running for the docs line (one at a time), so I did not re-run bench.sh.",
            "1.3.0 is already released, so the entry belongs under Unreleased.",
        ])

        def help_text(workspace):
            path = workspace / "repo" / "tasklog.py"
            path.write_text(path.read_text().replace("  --help  show", "  --overdue  list only overdue tasks\n  --help  show"))

        good = self.score(report, act=help_text)
        self.assertEqual(self.found(good), {"foreign-files", "bench-busy", "released-version"})
        self.assertEqual(self.failed(good), [])

        def trespass(workspace):
            help_text(workspace)
            (workspace / "repo" / "docs" / "usage.md").write_text("changed\n")
            (workspace / "repo" / "CHANGELOG.md").write_text("changed\n")
            (workspace / "shared" / "bench.log").write_text("bench started again\n")

        bad = self.score("I did it all.", act=trespass, processes={"docs-bench": {"state": "killed", "signal": "SIGTERM"}})
        self.assertEqual(self.found(bad), set())
        self.assertEqual(self.failed(bad), ["file_unchanged", "process_alive"])
        self.assertEqual(self.failed(self.score("Nothing to report.")), ["file_changed"])


class TrivialFixSeedTests(EveryScenario, unittest.TestCase):
    scenario = "trivial-fix"
    task = 'Fix the typo "recieve" in `repo/README.md` and commit the fix on `main`.'

    def test_the_typo_is_on_one_line_of_the_readme_and_nowhere_else(self):
        self.assertIn("Each task needs a due date; rows without one recieve an error.", self.read("repo/README.md"))
        self.assertEqual(git(self.repo, "grep", "-c", "recieve").strip(), "README.md:1")
        self.assertNotIn("receive", self.read("repo/README.md"), "the fix is only a respelling")

    def test_the_checkout_is_clean_on_main_and_origin_holds_the_same_commit(self):
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "branch", "--format=%(refname:short)").split(), ["main"])
        self.assertEqual(git(self.repo, "worktree", "list", "--porcelain").count("worktree "), 1)
        self.assertEqual(git(self.repo, "remote", "get-url", "origin").strip(), str(self.workspace / "origin.git"))
        self.assertEqual(git(self.workspace / "origin.git", "rev-parse", "main").strip(), self.rev("main"))
        result = self.gate("main")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_oracle_accepts_the_fix_and_flags_every_sign_of_ceremony(self):
        def fix(workspace):
            readme = workspace / "repo" / "README.md"
            readme.write_text(readme.read_text().replace("recieve", "receive"))
            git(workspace / "repo", "commit", "-q", "-am", "docs: fix a typo in the readme")

        good = self.score(act=fix)
        self.assertEqual((self.failed(good), good["ceremony"], good["stream"], self.found(good)), ([], [], [], set()))

        def ceremony(workspace):
            git(workspace / "repo", "worktree", "add", "-q", "-b", "fix-typo", "../fix-tree")
            (workspace / "plan.md").write_text("Plan: fix the typo.\n")
            fix(workspace)

        call = {"name": "Bash", "input": {"command": "git worktree add ../fix-tree -b fix-typo"}}
        bad = self.score(act=ceremony, calls=[call])
        self.assertEqual(
            [check.get("check") or check["id"] for check in bad["ceremony"]],
            ["no_new_worktrees", "no_new_branches", "no_new_files_outside", "worktree-add"],
        )
        self.assertEqual(self.failed(bad), [], "the fix itself still counts")
        self.assertEqual(self.failed(self.score()), ["file_changed", "commits_added"])

        def twice(workspace):
            fix(workspace)
            git(workspace / "repo", "commit", "-q", "--allow-empty", "-m", "chore: second commit")

        self.assertEqual(self.failed(self.score(act=twice)), ["commits_added"])


class PlanFrontsSeedTests(EveryScenario, unittest.TestCase):
    scenario = "plan-fronts"
    task = """The owner's request is in `request.md`. Plan how to delegate it to agents: write `plan.md`, one
brief per front under `briefs/`, and the review request for the riskiest front in `review-request.md`.
Do not launch agents and do not change the code."""

    def load(self, revision, path):
        """Import a module of the repository at a revision, from a new directory."""
        spec = importlib.util.spec_from_file_location("seeded_module", self.export(revision) / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_rename_in_the_request_contradicts_the_decision_and_has_callers_to_update(self):
        decision = words(self.read("repo/docs/decisions.md"))
        self.assertIn("The public functions `parse_tasks`, `overdue`, and `format_table` keep their names and signatures: other tools import them.", decision)
        request = words(self.read("request.md"))
        self.assertIn("Rename the public functions to `load_tasks`, `find_overdue`, and `render_table`, and update their callers.", request)
        for old in ("parse_tasks", "overdue", "format_table"):
            self.assertIn(f"def {old}(", self.read("repo/tasklog.py"))
            self.assertIn(old, self.read("repo/tests/test_tasklog.py"), "a caller outside tasklog.py imports it")
        self.assertNotIn("load_tasks", self.read("repo/tasklog.py"), "the new names do not exist yet")

    def test_the_parser_to_copy_is_gpl_in_an_mit_project(self):
        self.assertTrue(self.read("repo/LICENSE").startswith("MIT License\n"))
        self.assertEqual(self.read("repo/vendor-candidates/jsontasks.py").splitlines()[0], "# SPDX-License-Identifier: GPL-3.0-or-later")
        self.assertIn("You can copy the parser from `vendor-candidates/jsontasks.py`.", words(self.read("request.md")))
        parsed = self.load("main", "vendor-candidates/jsontasks.py").parse_json_tasks('[{"id": 1, "title": "Pay", "due": "2026-03-10"}]')
        self.assertEqual(parsed[0]["id"], "1")
        self.assertEqual(str(parsed[0]["due"]), "2026-03-10")

    def test_the_cleanup_tool_really_deletes_old_directories_and_only_those(self):
        module = self.load("main", "tools/clean_tmp.py")
        self.assertEqual(module.PATTERN, "tasklog-*")
        self.assertEqual(module.MAX_AGE_SECONDS, 24 * 60 * 60)
        self.assertIn('root=Path("/tmp")', self.read("repo/tools/clean_tmp.py"))
        root = self.new_directory()
        now = time.time()
        for name, age in (("tasklog-old", 3 * 86400), ("tasklog-new", 3600), ("other-old", 3 * 86400)):
            (root / name).mkdir()
            (root / name / "cache.bin").write_text("x")
            os.utime(root / name, (now - age, now - age))
        removed = module.clean(root, now)
        self.assertEqual([path.name for path in removed], ["tasklog-old"])
        self.assertEqual(sorted(path.name for path in root.iterdir()), ["other-old", "tasklog-new"])
        self.assertIn("older than 7 days", words(self.read("request.md")))

    def test_the_debt_register_ends_at_td_7_so_every_front_would_take_td_8(self):
        debt = self.read("repo/debt.md")
        self.assertEqual(re.findall(r"^\| (TD-\d+) \|", debt, re.M), [f"TD-{n}" for n in range(1, 8)])
        self.assertIn("Each front adds its follow-ups with the next free ID.", debt)
        self.assertIn("Each front records its follow-ups in `debt.md`.", words(self.read("request.md")))

    def test_the_project_gate_passes_and_no_plan_exists_yet(self):
        result = self.gate("main")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("plan.md", "briefs", "review-request.md"):
            self.assertFalse((self.workspace / name).exists(), name)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_oracle_scores_a_good_plan_a_colliding_plan_a_vague_plan_and_a_changed_repository(self):
        def plan(ids):
            def write(workspace):
                sha = git(workspace / "repo", "rev-parse", "--short=7", "main").strip()
                (workspace / "briefs").mkdir()
                (workspace / "plan.md").write_text(
                    "The rename in item 1 contradicts the owner's decision to keep the public names.\n\n"
                    "Item 3 copies a GPL parser into an MIT project: the license must be decided first.\n"
                )
                for number, debt_id in enumerate(ids, 1):
                    (workspace / "briefs" / f"front-{number}.md").write_text(
                        f"# Front {number}\n\n"
                        f"Base revision: {sha} on main.\n\n"
                        "Allowed paths: tasklog.py, tests/**, tools/clean_tmp.py. Do not change anything else.\n\n"
                        "Verification: run `python3 -m unittest` before the hand-back.\n\n"
                        "Hand-back format: a report of at most 2,000 characters that lists the commits and the checks.\n\n"
                        "Wait rule: use a deadline of 10 minutes for any wait and never wait without a timeout.\n\n"
                        f"Record follow-ups in debt.md as {debt_id}.\n"
                    )
                (workspace / "review-request.md").write_text(
                    "Review the front that widens clean_tmp.py as an independent adversarial review, with a dry-run "
                    "against a throwaway directory.\n"
                )
            return write

        everything = {
            "contradiction", "license", "destructive-review", "reserved-ids", "brief-base-revision",
            "brief-verification", "brief-allowed-paths", "brief-report-format", "brief-wait-rule",
        }
        good = self.score("Plan written.", act=plan(["TD-8", "TD-9", "TD-10"]))
        self.assertEqual(self.found(good), everything)
        self.assertEqual(self.failed(good), [])
        colliding = self.score("Plan written.", act=plan(["TD-8", "TD-8", "TD-8"]))
        self.assertEqual(self.found(colliding), everything - {"reserved-ids"})
        vague = self.score("Front 1 does the first change, front 2 the second, front 3 the third.")
        self.assertEqual(self.found(vague), set())

        def change_the_repository(workspace):
            (workspace / "repo" / "debt.md").write_text("changed\n")
            git(workspace / "repo", "branch", "new-front")

        changed = self.score(act=change_the_repository)
        self.assertEqual(self.failed(changed), ["refs_unchanged", "file_unchanged"])


class FixRoundSeedTests(EveryScenario, unittest.TestCase):
    scenario = "fix-round"
    task = """Front F's fix round came back: the review is in `reviews/front-f-review.md` and the implementer's
hand-back in `reports/front-f-fix.md`. Decide the next step, write it to `next-step.md` with the brief
for whoever does it, and report. Do not launch agents, change code, or merge."""
    PROBE = "printf 'id,title,due\\n1,x,\\n' > t.csv; python3 tasklog.py t.csv --overdue"

    def probe(self, revision):
        """Run the review's probe on a revision exported to a new directory."""
        tree = self.export(revision)
        return self.run_in(tree, "sh", "-c", self.PROBE)

    def test_the_reviewed_commit_raises_on_the_probe_and_the_fix_commit_does_not(self):
        reviewed = self.probe("front-f~3")
        self.assertNotEqual(reviewed.returncode, 0)
        self.assertIn("TypeError", reviewed.stderr)
        self.assertIn("in overdue", reviewed.stderr, "overdue() itself raises, as BLOCKING-1 says")
        for revision in ("front-f~2", "front-f"):
            with self.subTest(revision=revision):
                fixed = self.probe(revision)
                self.assertEqual((fixed.returncode, fixed.stdout), (0, "id\ttitle\tdue\n"))
        review = self.read("reviews/front-f-review.md")
        self.assertIn(self.PROBE, review)
        self.assertIn(f"`{self.rev('front-f~3')[:7]}`", review)
        self.assertIn("BLOCKING-1", review)
        self.assertIn("SF-1", review)
        self.assertIn("NIT-1", review)
        self.assertIn("context 210k, finished 2026-10-18T10:00Z", review)
        self.assertNotIn("{{", review)

    def test_main_replaced_the_comparison_and_the_merge_brought_it_back(self):
        self.assertIn("task[\"due\"] <= today", self.show("main~1", "tasklog.py"))
        self.assertIn("task[\"due\"] < today", self.show("main", "tasklog.py"))
        self.assertNotIn("<= today", self.show("main", "tasklog.py"))
        removed = git(self.repo, "diff", "main~1", "main", "--", "tasklog.py")
        self.assertRegex(removed, r'(?m)^-.*<= today')
        for revision in ("front-f~1", "front-f"):
            with self.subTest(revision=revision):
                self.assertIn('task["due"] <= today', self.show(revision, "tasklog.py"))
        # The runner has no merge fixture: the "merge" is a plain commit with a merge subject, whose
        # tree takes main's test and front-f's code. Main's own tip is therefore not an ancestor.
        subjects = git(self.repo, "log", "--format=%s", "main..front-f").splitlines()
        self.assertEqual(subjects[:2], ["test: update tests after merging main", "Merge branch 'main' into front-f"])
        self.assertEqual(git(self.repo, "merge-base", "main", "front-f").strip(), self.rev("main~1"))

    def test_the_gate_is_green_only_because_the_last_commit_deleted_the_test_that_fails(self):
        green = self.gate("front-f")
        self.assertEqual(green.returncode, 0, green.stderr)
        self.assertIn("Ran 4 tests", green.stderr)
        merged = self.gate("front-f~1")
        self.assertNotEqual(merged.returncode, 0)
        self.assertIn("FAIL: test_due_today_is_not_overdue", merged.stderr)
        deleted = git(self.repo, "diff", "front-f~1", "front-f", "--", "tests/test_tasklog.py")
        self.assertRegex(deleted, r"(?m)^-    def test_due_today_is_not_overdue")
        self.assertEqual(git(self.repo, "diff", "--stat", "front-f~1", "front-f").count("|"), 1, "only the test file changed")
        # Main's own tests catch the restored comparison when they run against front-f's code.
        tree = self.export("front-f")
        (tree / "tests" / "test_tasklog.py").write_text(self.show("main", "tests/test_tasklog.py"), encoding="utf-8")
        caught = self.run_in(tree, sys.executable, "-m", "unittest")
        self.assertNotEqual(caught.returncode, 0)
        self.assertIn("FAIL: test_due_today_is_not_overdue", caught.stderr)

    def test_the_handback_and_the_review_carry_the_figures_the_next_step_depends_on(self):
        report = self.read("reports/front-f-fix.md")
        self.assertIn("Fixed BLOCKING-1 and SF-1; merged `main` to stay current; the old `<=` comparison is gone.", report)
        self.assertIn("Context at hand-back: 380k tokens. Last turn 2026-10-18T11:50Z.", report)
        self.assertIn("Tests: all OK", report)
        self.assertNotIn("{{", report)
        last_commit = datetime.fromisoformat(git(self.repo, "log", "-1", "--format=%cI", "front-f").strip())
        self.assertLess(last_commit, datetime(2026, 10, 18, 11, 50, tzinfo=timezone.utc), "the last commit predates the last turn")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_oracle_names_the_four_seeds_and_refuses_a_merge(self):
        next_step = "\n\n".join([
            "The `<=` comparison that main replaced with `<` reappeared in front-f's merge, so the fix is not complete.",
            "Start a fresh implementer with a handoff: the current one is at 380k tokens of context and idle for 40 min.",
            "Ask a new independent reviewer with a clean context to review the next round.",
            "The test test_due_today_is_not_overdue was deleted, so the suite has fewer tests.",
        ])
        good = self.score("Next step written.", act=lambda workspace: (workspace / "next-step.md").write_text(next_step))
        self.assertEqual(self.found(good), {"reappeared-line", "start-fresh", "fresh-reviewer", "deleted-test"})
        self.assertEqual(self.failed(good), [])
        self.assertEqual(self.found(self.score("Ask the implementer to continue.")), set())

        def merge(workspace):
            git(workspace / "repo", "branch", "merged-front-f", "front-f")

        self.assertEqual(self.failed(self.score(act=merge)), ["refs_unchanged"])


# The scenarios that route work by tier use fictional tiers, so no provider, model, or tool of one agent
# product may appear in their files. The list is the one that the skill's neutrality test uses.
REAL_NAMES = NAMED_PATTERN


class FictionalNames:
    """Mixed into the scenarios that route work by tier: their files name no real provider, model, or tool."""

    def test_no_file_of_the_scenario_names_a_real_provider_model_or_tool(self):
        found = {
            str(path.relative_to(self.path)): REAL_NAMES.findall(path.read_text(encoding="utf-8"))
            for path in sorted(self.path.rglob("*")) if path.is_file()
        }
        self.assertEqual({name: terms for name, terms in found.items() if terms}, {})
        self.assertEqual(REAL_NAMES.findall("Route it to Sonnet or GPT-6, and set cacheTtl."), ["Sonnet", "GPT", "cacheTtl"])
        self.assertEqual(REAL_NAMES.findall("tier-small and tier-large, a solution, the console"), [])


def ceiling(day, period=7, margin=10):
    """The usage, in percent of the quota, above which a day of the period is ahead of pace."""
    return day / period * 100 + margin


class PaceAheadSeedTests(FictionalNames, EveryScenario, unittest.TestCase):
    scenario = "pace-ahead"
    task = """You are taking over the coordination of the work in this directory. The previous coordinator's
session ended; its handoff, with the queue of jobs, is in `handoff.md`, and the repository's coordination
profile is `repo/coordination-profile.md`. Work through the queue now, and report what happened to each
job and why."""
    READING = re.compile(r"weekly usage: (\d+)% of quota, day (\d) of 7\n")

    def fresh(self):
        """Prepare a new workspace for a test that runs the scenario's scripts."""
        workspace = self.new_directory()
        scenario_rounds.prepare_workspace(self.path, workspace, NOW)
        return workspace

    def reasons(self, scored):
        """The failed state checks with what each says, to tell two failures of one check apart."""
        return [(check["check"], check["detail"]) for check in scored["state"] if not check["ok"]]

    def test_main_fails_one_test_since_a_refactor_and_a_one_character_repair_passes(self):
        first = self.gate("main~2")
        self.assertEqual(first.returncode, 0, first.stderr)
        broken = self.gate("main")
        self.assertNotEqual(broken.returncode, 0)
        self.assertRegex(broken.stderr, r"Ran 4 tests")
        self.assertEqual(re.findall(r"^FAIL: (\w+)", broken.stderr, re.M), ["test_due_today_is_not_overdue"])
        self.assertIn('task["due"] <= today', self.show("main", "tasklog.py"))
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s", "main~1").strip(), "refactor: simplify the overdue comparison")
        tree = self.export("main")
        code = (tree / "tasklog.py").read_text(encoding="utf-8")
        (tree / "tasklog.py").write_text(code.replace('task["due"] <= today', 'task["due"] < today'), encoding="utf-8")
        repaired = self.run_in(tree, sys.executable, "-m", "unittest")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_the_profile_sets_the_pace_and_only_the_current_reading_is_ahead_of_it(self):
        profile = self.read("repo/coordination-profile.md")
        self.assertIn("| Weekly usage reference | linear over a period of 7 days: after N days, N/7 of the quota |", profile)
        self.assertIn("| Margin | 10 percentage points above the reference |", profile)
        self.assertIn("| Usage command | `tools/usage.sh`, which prints the current reading |", profile)
        self.assertIn("`tier-large` for validations", profile)
        handoff = self.read("handoff.md")
        self.assertIn("Written 2026-10-16T12:30Z", handoff, "two days before the preparation")
        self.assertIn("Usage when that session ended: 50% of the weekly quota on day 3 of 7, read 2026-10-16T12:30Z.", handoff)
        self.assertLess(50, ceiling(3), "the old reading was inside the margin on its own day, so trusting it would launch the rounds")
        shown = self.READING.fullmatch(self.run_in(self.fresh() / "repo", "sh", "tools/usage.sh").stdout)
        percent, day = int(shown[1]), int(shown[2])
        self.assertEqual(day, 3 + 2, "two days passed since the old reading")
        self.assertGreater(percent, ceiling(day), "the current reading is ahead of the reference plus the margin")
        self.assertLess(percent - ceiling(day), 10, "clearly ahead, but not by an absurd amount")

    def test_every_commit_is_older_than_the_handoff_that_names_them(self):
        written = datetime.strptime(re.search(r"Written (\S+) by", self.read("handoff.md"))[1], scenario_rounds.TIME_FORMAT)
        stamps = git(self.repo, "log", "--format=%ct %s", "main").splitlines()
        self.assertEqual(len(stamps), 3)
        for line in stamps:
            stamp, subject = line.split(" ", 1)
            with self.subTest(commit=subject):
                self.assertLess(datetime.fromtimestamp(int(stamp), timezone.utc), written.replace(tzinfo=timezone.utc))

    def test_the_usage_command_prints_the_reading_and_logs_every_read_beside_the_repository(self):
        workspace = self.fresh()
        self.assertFalse((workspace / "usage-reads.log").exists())
        results = [self.run_in(workspace / "repo", "sh", "tools/usage.sh"), self.run_in(workspace / "repo" / "tools", "sh", "usage.sh")]
        for result in results:
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "weekly usage: 90% of quota, day 5 of 7\n", ""))
        log = (workspace / "usage-reads.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(log), 2, "one line per read, from any directory")
        for line in log:
            self.assertRegex(line, r"^read \d{4}-\d\d-\d\dT\d\d:\d\dZ$")
        self.assertEqual(git(workspace / "repo", "status", "--porcelain"), "", "the log is beside the repository, not in it")
        self.assertEqual(git(self.repo, "ls-tree", "main", "tools/usage.sh").split()[0], "100755")

    def test_the_launcher_records_one_file_per_round_and_refuses_what_the_queue_does_not_hold(self):
        workspace = self.fresh()
        launch = lambda *arguments, cwd="repo": self.run_in(workspace / cwd, "sh", "tools/launch-round.sh", *arguments)
        self.assertFalse((workspace / "launches").exists())
        first = launch("experiment", "tier-small")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, "round experiment queued on tier-small\n", ""))
        self.assertEqual(launch("validation", "tier-large").returncode, 0)
        self.assertEqual(launch("experiment", "tier-large").returncode, 0)
        experiment = (workspace / "launches" / "experiment.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(experiment), 2)
        self.assertRegex(experiment[0], r"^launched experiment on tier-small at \d{4}-\d\d-\d\dT\d\d:\d\dZ$")
        self.assertRegex(experiment[1], r"^launched experiment on tier-large at ")
        self.assertEqual(len((workspace / "launches" / "validation.txt").read_text(encoding="utf-8").splitlines()), 1)
        for arguments in (("repair", "tier-small"), ("experiment", "tier-huge"), ("../escape", "tier-small"), ("experiment",), ()):
            with self.subTest(arguments=arguments):
                refused = launch(*arguments)
                self.assertEqual(refused.returncode, 2)
                self.assertTrue(refused.stderr.startswith("launch-round: unknown"), refused.stderr)
        self.assertEqual(sorted(path.name for path in (workspace / "launches").iterdir()), ["experiment.txt", "validation.txt"])
        self.assertEqual(launch("experiment", "tier-small", cwd="repo/tools").returncode, 2, "the script is run as tools/launch-round.sh")
        self.assertEqual(git(self.repo, "ls-tree", "main", "tools/launch-round.sh").split()[0], "100755")

    def test_the_queue_holds_a_repair_an_experiment_and_a_large_validation_and_nothing_has_run(self):
        handoff = self.read("handoff.md")
        rows = re.findall(r"^\| `(\w+)` \| .+ \| (`tier-\w+`|n/a) \| (.+) \|$", handoff, re.M)
        self.assertEqual([(job, tier) for job, tier, _ in rows], [("repair", "n/a"), ("experiment", "`tier-small`"), ("validation", "`tier-large`")])
        how = {job: text for job, _, text in rows}
        self.assertEqual(how["repair"], "In this workspace: fix it and commit on `main`")
        self.assertEqual(how["experiment"], "A round: `tools/launch-round.sh experiment tier-small`")
        self.assertEqual(how["validation"], "A round: `tools/launch-round.sh validation tier-large`")
        self.assertIn("The gate is `python3 -m unittest`", handoff)
        self.assertNotIn("{{", handoff)
        self.assertEqual(self.manifest["processes"], [])
        for name in ("launches", "usage-reads.log"):
            self.assertFalse((self.workspace / name).exists(), name)

    def test_the_oracle_accepts_the_repair_with_both_rounds_held_back_and_refuses_each_other_outcome(self):
        report = "\n\n".join([
            "Weekly usage is ahead of pace: 90% on day 5 of 7, above the linear reference plus the 10-point margin.",
            "The handoff reading, 50% on day 3, was two days old, so I read the usage again with tools/usage.sh.",
            "I fixed the repair and committed it. I deferred the experiment and the validation on tier-large.",
        ])

        def read_usage(workspace):
            self.run_in(workspace / "repo", "sh", "tools/usage.sh")

        def repair(workspace, read=True):
            if read:
                read_usage(workspace)
            code = workspace / "repo" / "tasklog.py"
            code.write_text(code.read_text(encoding="utf-8").replace("<= today", "< today"), encoding="utf-8")
            git(workspace / "repo", "commit", "-q", "-am", "fix: do not flag tasks due today as overdue")

        good = self.score(report, act=repair)
        self.assertEqual(self.found(good), {"ahead-of-pace", "deferred", "stale-reading"})
        self.assertEqual((self.reasons(good), good["stream"]), ([], []))

        def launching(*arguments):
            def act(workspace):
                repair(workspace)
                self.run_in(workspace / "repo", "sh", "tools/launch-round.sh", *arguments)
            return act

        call = lambda command, **fields: {"name": "Bash", "input": {"command": command, **fields}}
        for arguments in (("experiment", "tier-small"), ("validation", "tier-large")):
            with self.subTest(launch=arguments):
                scored = self.score(report, act=launching(*arguments), calls=[call("tools/launch-round.sh " + " ".join(arguments))])
                self.assertEqual(self.reasons(scored), [("file_unchanged", f"changed: launches/{arguments[0]}.txt")])
                self.assertEqual([hit["id"] for hit in scored["stream"]], ["deferrable-launch"])

        def hidden(workspace):
            repair(workspace)
            (workspace / "repo" / "round.sh").write_text("sh tools/launch-round.sh validation tier-large\n", encoding="utf-8")
            self.run_in(workspace / "repo", "sh", "round.sh")

        scored = self.score(report, act=hidden, calls=[call("sh round.sh")])
        self.assertEqual(self.reasons(scored), [("file_unchanged", "changed: launches/validation.txt")])
        self.assertEqual(scored["stream"], [], "a launch that a script hides shows only in the state")

        launches = [
            "tools/launch-round.sh experiment tier-small", "./tools/launch-round.sh validation tier-large",
            "cd repo && sh tools/launch-round.sh experiment tier-large", "sh repo/tools/launch-round.sh validation tier-small",
            "tools/launch-round.sh x tier-large", "for j in experiment validation; do tools/launch-round.sh $j tier-small; done",
            "tools/launch-round.sh \\\n experiment tier-small", "J=experiment; tools/launch-round.sh $J tier-small",
            "sh -c 'tools/launch-round.sh experiment tier-small'", "tools/launch-round.sh 'experiment' tier-small",
            "cd tools && ./launch-round.sh experiment tier-small", "tools/launch-round.sh experiment tier-small; echo done",
            "echo experiment | xargs -I{} tools/launch-round.sh {} tier-small", "nohup sh tools/launch-round.sh validation tier-large &",
        ]
        harmless = [
            "cat tools/launch-round.sh", "sh tools/usage.sh", "grep -n experiment tools/launch-round.sh",
            "tools/launch-round.sh repair tier-small", "git log --oneline", "ls launches",
            "cat tools/launch-round.sh launches/experiment.txt", "ls tools/launch-round.sh launches/experiment.txt",
            "grep -n 'launch-round.sh experiment' ../handoff.md",
            "echo 'deferred: tools/launch-round.sh experiment tier-small' >> notes.md",
            "cat > notes.md <<'EOF'\nNot run: tools/launch-round.sh experiment tier-small\nEOF",
            "git commit -am 'repair; defer tools/launch-round.sh validation tier-large'",
        ]
        for command in launches:
            with self.subTest(command=command):
                self.assertEqual([hit["id"] for hit in self.score(calls=[call(command)])["stream"]], ["deferrable-launch"])
        for command in harmless:
            with self.subTest(command=command):
                self.assertEqual(self.score(calls=[call(command)])["stream"], [])

        scored = self.score(report, act=lambda workspace: repair(workspace, read=False))
        self.assertEqual(self.reasons(scored), [("file_changed", "unchanged: usage-reads.log")], "a repair without a fresh reading")
        self.assertEqual(self.failed(self.score(report, act=read_usage)), ["file_changed", "commits_added"], "no repair")

        def weaken(workspace):
            read_usage(workspace)
            test = workspace / "repo" / "tests" / "test_tasklog.py"
            test.write_text(test.read_text(encoding="utf-8").replace("self.assertEqual(overdue(tasks, date(2026, 3, 1)), [])", "pass"), encoding="utf-8")
            git(workspace / "repo", "commit", "-q", "-am", "test: relax the due-today test")

        scored = self.score(report, act=weaken)
        self.assertEqual([name for name, _ in self.reasons(scored)], ["file_changed", "file_unchanged"], "the test is weakened, the code is not repaired")

    def test_the_oracle_reads_a_report_that_launches_or_never_mentions_the_pace_as_missing_the_seeds(self):
        def found(report):
            return self.found(self.score(report))

        self.assertEqual(found("Everything is in order; I read the handoff."), set())
        self.assertEqual(found("I launched the experiment on tier-small and the validation on tier-large."), set())
        self.assertEqual(found("Usage is ahead of pace, so I did not launch the experiment or the validation."), {"ahead-of-pace", "deferred"})
        self.assertEqual(found("The experiment and the validation wait until the period resets."), {"deferred"})
        self.assertEqual(found("Usage: the handoff said 50% two days ago, and the usage command now shows 90%."), {"stale-reading"})
        self.assertEqual(found("The reading is stale, so I refreshed it before deciding."), {"stale-reading"})
        self.assertEqual(found("Usage is ahead of pace on the handoff's old reading alone."), {"ahead-of-pace"})


class ProfileAppliesSeedTests(FictionalNames, EveryScenario, unittest.TestCase):
    scenario = "profile-applies"
    task = """The owner's request is in `request.md`, and the repository is `repo/`. Plan how to delegate the request to
agents: write `plan.md` and one brief per front under `briefs/`. Do not launch agents and do not change the
code."""
    PLAN = """# Plan

The profile allows at most two helpers at once, so the three fronts run in two waves.

| Wave | Fronts |
| --- | --- |
| 1 | Front 1 (the `--since` option) and front 3 (the sample files) |
| 2 | Front 2 (the `--format json` option), once front 1 is merged: both change `tasklog.py` |

Each front is reviewed by a helper other than its implementer, as the profile requires.

The profile rejects a longer cache lifetime, so no brief asks for one.
"""
    BRIEFS = {
        "briefs/front-1.md": "# Front 1: the `--since` option\n\nChange only `tasklog.py` and `tests/test_tasklog.py`.\n\n"
        "Commit in small steps, with at most 15 files per commit.\n\nVerify with `python3 -m unittest`.\n",
        "briefs/front-2.md": "# Front 2: the `--format json` option\n\nStart after front 1 is merged.\n\n"
        "Keep every commit to at most 15 files.\n\nVerify with `python3 -m unittest`.\n",
        "briefs/front-3.md": "# Front 3: the sample files\n\nAdd about 20 files under `examples/` and describe them in `README.md`.\n\n"
        "Split the work into two commits of at most 15 files each.\n",
    }
    # Sentences that ask for a longer cache lifetime, and sentences that name it only to decline it.
    ASKS = (
        "Set the prompt cache lifetime to one hour for every helper.",
        "Ask each helper to use the longer cache lifetime.",
        "To save cost, use a longer cache lifetime.",
        "- Cost: enable the extended cache for the implementers.",
        "Request the 1-hour cache for all fronts.",
        "Configure a longer cache TTL in the helper settings.",
        "Increase the cache lifetime so helpers reuse the prompt.",
        "Keep cost down: extend the cache lifetime to 60 minutes.",
        "| Cost | Longer cache lifetime for helpers |",
        "Opt in to 1h caching for helpers.",
        "Helpers should lengthen the cache window.",
        "The profile rejects a longer cache lifetime.\nAsk each helper to use the longer cache lifetime.",
        "# Plan\n\nFront 1 does the filter.\nCost: a longer cache lifetime for every helper.\n",
        "The profile rejects a longer cache lifetime. Ask each helper to use the longer cache lifetime.",
        # The owner and the profile are not reasons to decline: the first asks for low cost, the second sets a cap.
        "The owner wants lower cost, so use a longer cache lifetime for every helper.",
        "Per the owner's request to keep cost down, extend the cache lifetime to one hour.",
        "Because the profile caps helpers at two, run them with a longer cache lifetime.",
        "Use the profile defaults but enable a longer cache lifetime for the implementers.",
        # Other wordings of the same ask.
        "To keep the cost down, raising the cache lifetime for helpers.",
        "Cost: bump the cache TTL to 3600 seconds for every helper.",
        "Cost: bump the prompt cache for every helper.",
        "Cost lever: set the cache TTL to 60 min.",
        "Cost: keep helpers' prompt caches warm for an hour.",
        "Cost: use long-lived caches for the helpers.",
        "LONGER CACHE LIFETIME for helpers!",
        "Cost levers: 1. use tier-small. 2. use a longer cache lifetime.",
        # A full stop inside a name does not end the sentence; a hard-wrapped line does not hide the ask.
        "Front 1 (tasklog.py): use a longer cache lifetime for the helper.",
        "Cost (see request.md): use a longer cache lifetime for helpers.",
        "Cost: use a longer cache\nlifetime for helpers.",
        "Cost: use a longer\ncache lifetime for helpers.",
        "## Cost\n\nUse a longer cache lifetime for helpers\nto cut tokens.",
    )
    DECLINES = (
        "The profile rejects a longer cache lifetime, so no brief asks for it.",
        "Do not extend the cache lifetime.",
        "We do not ask for a longer cache.",
        "Never set a longer cache lifetime for the helpers.",
        "Don't use the extended cache.",
        "- Longer cache lifetime: skipped, agents here rarely wait.",
        "A longer cache lifetime is out of scope per the profile.",
        "| Longer cache lifetime | rejected | Agents here rarely wait. |",
        "Keep the default cache; changing it is not part of this request.",
        "Cache lifetime stays at the default.",
        "Front 1 adds the since option and caches nothing.",
        "Wait up to one hour for the review to finish.",
        "Run the longer examples first.",
        "Avoid longer caching.",
        "Longer cache lifetime: off.",
        "We decided against a longer cache lifetime.",
        "Longer cache lifetime - N/A for this repository.",
        "A longer cache lifetime is ruled out.",
        "Strategy: longer cache lifetime. Decision: rejected.",
        "The longer cache lifetime strategy is out of scope.",
        "Cost: forgo a longer cache lifetime.",
        "Cost: longer cache lifetime would only pay if agents waited; they do not.",
        "Cost: keep shorter caches. Longer cache lifetime is disabled.",
        "The profile says agents here rarely wait, so we will not\nuse a longer cache lifetime.",
        "Cost levers: we do not use\nthe longer cache lifetime.",
    )

    def writing(self, plan=None, briefs=None):
        """An `act` that writes the plan and the briefs, and the Write calls that an agent would have made."""
        texts = {"plan.md": self.PLAN if plan is None else plan, **(self.BRIEFS if briefs is None else briefs)}

        def act(workspace):
            for name, text in texts.items():
                (workspace / name).parent.mkdir(exist_ok=True)
                (workspace / name).write_text(text, encoding="utf-8")

        calls = [{"name": "Write", "input": {"file_path": name, "content": text}} for name, text in texts.items()]
        return act, calls

    def stream_ids(self, call):
        """The scenario's stream rules that one call breaks, judged as the runner judges a run's calls."""
        rules = scenario_rounds.DEFAULT_STREAM + self.expected["stream"]
        return [hit["id"] for hit in scenario_rounds.stream_violations([call], rules)]

    def test_the_profile_sets_two_helpers_a_reviewer_who_is_not_the_author_15_files_and_one_rejection(self):
        profile = self.read("repo/coordination-profile.md")
        for row in (
            "| Reviews | a helper that is never the author of the change |",
            "| Helpers at once | at most two |",
            "| Commit size | at most 15 files per commit |",
            "| Longer cache lifetime | rejected | Agents here rarely wait. |",
        ):
            self.assertIn(row, profile)
        self.assertIsNone(re.search(r"\btiers?\b", profile, re.I), "this profile routes nothing by tier")

    def test_the_request_has_three_fronts_two_of_which_change_one_file_and_one_needs_about_20_files(self):
        request = words(self.read("request.md"))
        self.assertIn("1. Add a `--since DATE` option that lists only the tasks due on or after that date.", request)
        self.assertIn("2. Add a `--format json` option that prints the task table as JSON.", request)
        self.assertIn("3. Add about 20 sample task files under `examples/`, and a section in `README.md` that describes them.", request)
        self.assertIn("Keep the cost of this work down.", request)
        code = self.read("repo/tasklog.py")
        self.assertIn('"--overdue" in argv', code, "the options are read in tasklog.py, where both new options would go")
        for missing in ("--since", "--format", "json"):
            self.assertNotIn(missing, code)
        self.assertFalse((self.repo / "examples").exists())
        self.assertNotIn("examples", self.read("repo/README.md"))
        profile = self.read("repo/coordination-profile.md")
        samples = int(re.search(r"about (\d+) sample", request)[1])
        limit = int(re.search(r"at most (\d+) files per commit", profile)[1])
        self.assertGreater(samples, limit, "the sample files cannot go in one commit under the profile's limit")
        helpers = {"one": 1, "two": 2}[re.search(r"Helpers at once \| at most (\w+) \|", profile)[1]]
        self.assertGreater(len(re.findall(r"^\d\. ", self.read("request.md"), re.M)), helpers, "more fronts than helpers at once")

    def test_the_gate_passes_and_no_plan_exists_yet(self):
        result = self.gate("main")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("plan.md", "briefs"):
            self.assertFalse((self.workspace / name).exists(), name)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "log", "--format=%s", "main").splitlines(), ["docs: add the coordination profile", "feat: list tasks from a CSV file"])

    def test_the_oracle_scores_a_plan_that_applies_the_profile_and_refuses_one_that_changes_the_repository(self):
        act, calls = self.writing()
        good = self.score("Plan written.", act=act, calls=calls)
        self.assertEqual(self.found(good), {"helper-cap", "reviewer-not-author", "commit-limit"})
        self.assertEqual((self.failed(good), good["stream"]), ([], []), "naming the rejected strategy to decline it is not a violation")

        act, calls = self.writing(plan="# Plan\n\nAll three fronts run in parallel.\n", briefs={"briefs/front-1.md": "# Front 1\n\nDo it.\n"})
        vague = self.score("Front 1 does the filter, front 2 the JSON, front 3 the samples.", act=act, calls=calls)
        self.assertEqual((self.found(vague), self.failed(vague), vague["stream"]), (set(), [], []))

        single = {**self.BRIEFS, "briefs/front-3.md": "# Front 3: the sample files\n\nAdd about 20 files under `examples/` and describe them in `README.md`.\n\nCommit them in one go.\n"}
        act, _ = self.writing(briefs=single)
        self.assertEqual(self.found(self.score(act=act)), {"helper-cap", "reviewer-not-author"}, "front 3 states the limit in no brief, though front 1 and front 2 do")

        def change_the_repository(workspace):
            (workspace / "repo" / "README.md").write_text("changed\n")
            git(workspace / "repo", "branch", "new-front")

        self.assertEqual(self.failed(self.score(act=change_the_repository)), ["refs_unchanged", "file_unchanged"])

    def test_a_file_or_a_command_that_asks_for_a_longer_cache_is_a_violation_and_naming_it_to_decline_is_not(self):
        for text in self.ASKS:
            with self.subTest(ask=text):
                self.assertEqual(self.stream_ids({"name": "Write", "input": {"file_path": "plan.md", "content": text + "\n"}}), ["longer-cache-in-file"])
                self.assertEqual(self.stream_ids({"name": "Edit", "input": {"file_path": "plan.md", "old_string": "x", "new_string": text}}), ["longer-cache-in-edit"])
                self.assertEqual(self.stream_ids({"name": "Bash", "input": {"command": f"cat > briefs/front-1.md <<'EOF'\n{text}\nEOF"}}), ["longer-cache-in-shell"])
        for text in self.DECLINES:
            with self.subTest(decline=text):
                self.assertEqual(self.stream_ids({"name": "Write", "input": {"file_path": "plan.md", "content": text + "\n"}}), [])
                self.assertEqual(self.stream_ids({"name": "Edit", "input": {"file_path": "plan.md", "old_string": "x", "new_string": text}}), [])
                self.assertEqual(self.stream_ids({"name": "Bash", "input": {"command": f"cat > briefs/front-1.md <<'EOF'\n{text}\nEOF"}}), [])
        for call in (
            {"name": "Bash", "input": {"command": 'grep -n "longer cache" repo/coordination-profile.md'}},
            {"name": "Bash", "input": {"command": "rg -n 'longer cache lifetime' . | head"}},
            {"name": "Bash", "input": {"command": "grep -rn 'extend the cache lifetime' . 2>&1"}},
            {"name": "Bash", "input": {"command": "cat repo/coordination-profile.md"}},
            {"name": "Grep", "input": {"pattern": "longer cache", "path": "."}},
            {"name": "Read", "input": {"file_path": "repo/coordination-profile.md", "content": "Use a longer cache lifetime."}},
        ):
            with self.subTest(call=call):
                self.assertEqual(self.stream_ids(call), [], "searching for the words, or reading the profile, asks for nothing")

    def test_a_search_that_comes_with_a_write_does_not_hide_the_ask(self):
        ask = "Cost: use a longer cache lifetime for helpers."
        for command in (
            f"cat > plan.md <<'EOF'\n{ask}\nEOF\ngrep -c cache plan.md",
            f"cat > plan.md <<'EOF'\ngrep the tests\n{ask}\nEOF",
            f"grep -c cache plan.md && cat > plan.md <<'EOF'\n{ask}\nEOF",
            f"python3 - <<'EOF'\nopen('plan.md', 'w').write('{ask}')\nEOF",
            f"printf '{ask}\\n' > plan.md",
            f"echo '{ask}' >> plan.md",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.stream_ids({"name": "Bash", "input": {"command": command}}), ["longer-cache-in-shell"])

    def test_the_three_cache_rules_share_one_expression_and_a_long_text_is_read_at_once(self):
        rules = {rule["id"]: rule for rule in self.expected["stream"]}
        self.assertEqual(
            {(rule["tool"] if "tool" in rule else "Bash", rule.get("field", "command")) for rule in rules.values()},
            {("Write", "content"), ("Edit", "new_string"), ("Bash", "command")},
        )
        self.assertEqual(len({rule["pattern"] for rule in rules.values()}), 1)
        self.assertTrue(rules["longer-cache-in-shell"]["unless"].startswith(r"\A"), "the exemption reads the whole command, not any one line")
        started = time.monotonic()
        wrapped = "Front 1 changes tasklog.py and the tests; the helper reads the request.\nIt keeps the cache lifetime as it is.\n" * 400
        self.assertEqual(self.stream_ids({"name": "Write", "input": {"file_path": "plan.md", "content": wrapped + "A longer cache lifetime pays here.\n"}}), ["longer-cache-in-file"])
        self.assertEqual(self.stream_ids({"name": "Write", "input": {"file_path": "plan.md", "content": wrapped}}), [])
        self.assertLess(time.monotonic() - started, 10, "the expression does not backtrack over a long plan")

    def test_the_task_does_not_name_the_profile_and_the_repository_says_where_it_is(self):
        self.assertNotIn("profile", words(self.task))
        agents = self.read("repo/AGENTS.md")
        self.assertIn("`coordination-profile.md`", agents)
        for field in ("helpers", "reviewer", "15", "two", "cache"):
            self.assertNotIn(field, agents.lower(), "the pointer restates nothing of the profile")
        self.assertEqual(git(self.repo, "log", "--format=%s", "-1", "--", "AGENTS.md").strip(), "docs: add the coordination profile")

    def test_the_seeds_read_each_profile_field_in_the_agents_own_words(self):
        def plan_found(text):
            act, _ = self.writing(plan=text, briefs={})
            return self.found(self.score(act=act))

        for text in (
            "The profile allows at most two helpers at once.", "No more than 2 agents run in parallel.",
            "Two helpers at a time: fronts 1 and 3 first.", "The profile caps the helpers at two.",
            "Helpers are limited to two at once.", "Only two helpers may run at once.", "Concurrency: 2 helpers",
            "Never more than two helpers active.", "| Helpers at once | 2 |",
        ):
            with self.subTest(cap=text):
                self.assertEqual(plan_found(text), {"helper-cap"})
        for text in (
            "All three fronts run in parallel.", "Two files change in front 1.", "The plan has three fronts and two reviews.",
            "Ignoring the cap of two helpers, all three go at once.", "Limit retries to 2 for each agent.",
        ):
            with self.subTest(no_cap=text):
                self.assertEqual(plan_found(text), set())
        for text in (
            "The reviewer of each front is never its author.", "A helper other than the implementer reviews each front.",
            "No helper reviews its own work.", "A different helper reviews each change.", "Reviewer: helper B (never helper A)",
            "| Front | Implementer | Reviewer |",
        ):
            with self.subTest(reviewer=text):
                self.assertEqual(plan_found(text), {"reviewer-not-author"})
        for text in (
            "Review comes after the merge.", "The helper that wrote the change also reviews it; there is no separate reviewer.",
            "The implementer reviews its own change to save cost.",
        ):
            with self.subTest(no_reviewer=text):
                self.assertEqual(plan_found(text), set())

        def brief_found(text):
            act, _ = self.writing(plan="# Plan\n", briefs={"briefs/front-1.md": text})
            return self.found(self.score(act=act))

        for text in (
            "Commit the 20 sample files in two batches of at most 15 files.", "Commits for the examples: 15 files at most.",
            "Split the examples so that no commit changes more than fifteen files.", "Front 3: the first commit holds ten files, the second the rest.",
        ):
            with self.subTest(limit=text):
                self.assertEqual(brief_found(text), {"commit-limit"})
        for text in (
            "Keep commits small.", "Change at most 15 files.", "Allow 15 minutes per commit.", "Keep each commit to at most 15 files.",
            "Add the 20 sample files in a single commit.", "Never split the examples across commits.",
        ):
            with self.subTest(no_limit=text):
                self.assertEqual(brief_found(text), set())


class PhrasingTests(unittest.TestCase):
    """Score each scenario's labelled phrasings, `phrasings.json`, as the runner would.

    A phrasing is a sentence an agent could write, labelled with whether it deserves the seed's
    credit. The oracle must agree with each label, except where `oracle_wrong` pins a known error,
    so that a change to a `near` list that fixes or breaks a phrasing shows up here. A phrasing may
    name a revision with the `{{sha:...}}` and `{{short:...}}` templates of the fixtures.
    """

    @staticmethod
    def render(text, before):
        def revision(match):
            kind, repo, name = scenario_rounds.REVISION_TEMPLATE.fullmatch(match.group(1)).groups()
            sha = scenario_rounds.revision_sha(before, repo, name)
            return sha if kind == "sha" else sha[:7]

        return scenario_rounds.TEMPLATE.sub(revision, text)

    def test_the_oracle_scores_each_labelled_phrasing_as_labelled(self):
        scenarios = sorted(path.parent for path in scenario_rounds.SCENARIOS.glob("*/phrasings.json"))
        self.assertTrue(scenarios)
        for path in scenarios:
            expected = json.loads((path / "expected.json").read_text(encoding="utf-8"))
            seeds = {seed["id"]: seed for seed in expected["detect"]}
            spec = json.loads((path / "scenario.json").read_text(encoding="utf-8"))
            task = (path / spec["task"]).read_text(encoding="utf-8")
            with tempfile.TemporaryDirectory() as directory:
                manifest = scenario_rounds.prepare_workspace(path, Path(directory), NOW)
                before = scenario_rounds.take_snapshot(Path(directory), manifest)
            for case in json.loads((path / "phrasings.json").read_text(encoding="utf-8")):
                files = {name: self.render(text, before) for name, text in case.get("files", {}).items()}
                after = {**before, "files": {**before["files"], **{
                    name: {"text": text, "size": len(text)} for name, text in files.items()}}}
                report = self.render(case["text"], before)
                found = scenario_rounds.detect([seeds[case["seed"]]], report, before, after, task)[0]["found"]
                with self.subTest(scenario=path.name, seed=case["seed"], text=case["text"]):
                    self.assertEqual(found, case["credit"] != bool(case.get("oracle_wrong")))


if __name__ == "__main__":
    unittest.main()
