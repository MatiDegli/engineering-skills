"""Check the headless round runner against a stand-in `claude` that starts no agent."""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from tools import claude_rounds
from tools.evals import git_environment

FAKE_CLAUDE = r'''#!{python}
"""A stand-in for the claude CLI: it answers like the real one and starts no agent."""
import json, os, signal, subprocess, sys, time
from pathlib import Path

arguments = sys.argv[1:]
if arguments[:2] == ["auth", "status"]:
    print(json.dumps({{"loggedIn": True}}, indent=2))
    raise SystemExit(0)
if arguments == ["--version"]:
    print("0.0.0 (Claude Code)")
    raise SystemExit(0)
model = arguments[arguments.index("--model") + 1]
source = "none"
if os.environ.get("ANTHROPIC_BASE_URL"):
    settings = json.load(open(arguments[arguments.index("--settings") + 1]))
    inherited = [name for name in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY") if name in os.environ]
    aliases = {{os.environ.get("ANTHROPIC_DEFAULT_" + a + "_MODEL") for a in ("OPUS", "SONNET", "HAIKU", "FABLE")}}
    if inherited or not os.environ.get("CLAUDE_CONFIG_DIR") or aliases != {{model}} or "apiKeyHelper" not in settings:
        raise SystemExit("the provider launch is not isolated")
    source = "apiKeyHelper"
if "json" == arguments[arguments.index("--output-format") + 1]:
    if model == "claude-unknown-1-0":
        print(json.dumps({{"type": "result", "is_error": True, "result": "unknown model"}}))
    else:
        print(json.dumps({{"type": "result", "is_error": False, "result": "OK", "modelUsage": {{model: {{}}}}}}))
    raise SystemExit(0)
if os.environ.get("GH_TOKEN") or not os.environ.get("GH_CONFIG_DIR", "").endswith("gh-config"):
    raise SystemExit("the audit could reach a GitHub CLI login")
state = Path(os.environ.get("FAKE_STATE", "/nonexistent")) / (model + "-" + Path.cwd().parent.name)
if os.environ.get("FAKE_STATE"):
    added = [arguments[i + 1] for i, a in enumerate(arguments) if a == "--add-dir"]
    prompt = arguments[arguments.index("-p") + 1]
    (Path(os.environ["FAKE_STATE"]) / ("args-" + Path.cwd().parent.name)).write_text(json.dumps([prompt, added]))
if model in ("claude-stuck-1-0", "claude-stubborn-1-0"):
    # Start a grandchild, record both processes, signal the runner, and stay alive until stopped.
    if model == "claude-stubborn-1-0":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    grandchild = subprocess.Popen(["sleep", "120"])
    pids = " ".join(str(pid) for pid in (os.getpid(), grandchild.pid))
    (Path(os.environ["FAKE_STATE"]) / ("pids-" + model)).write_text(pids)
    os.kill(os.getppid(), getattr(signal, os.environ.get("FAKE_SIGNAL", "SIGTERM")))
    time.sleep(30)  # a bound so that a runner that does not stop this process cannot hang the suite
    (Path(os.environ["FAKE_STATE"]) / "expired").write_text(model)
    raise SystemExit(1)
if model == "claude-flaky-1-0" and not state.exists():
    state.write_text("failed once")
    print(json.dumps({{"type": "result", "result": "Failed to refresh OAuth token: another process"}}))
    raise SystemExit(1)
used = "claude-other-1-0" if model == "claude-mismatch-1-0" else model
command = "cat /home/someone/notes.txt; grep -E '/home/|/Users/' x; cat /home/u/.claude/projects/-tmp-audit-x/out.txt"
tool = {{"type": "tool_use", "name": "Bash", "input": {{"command": command}}}}
print(json.dumps({{"type": "system", "subtype": "init", "apiKeySource": source}}))
print(json.dumps({{"type": "assistant", "message": {{"content": [tool]}}}}))
print(json.dumps({{"type": "system", "subtype": "notice", "message": "a plain text message"}}))
report = "## Findings\n| ID | Status | Priority | Evidence | Improvement |\n| --- | --- | --- | --- | --- |\n"
report += "| REPO-01 | partial | low | `README.md:1` | Say more |\n"
usage = {{"inputTokens": 10, "cacheReadInputTokens": 1000, "outputTokens": 200}}
print(json.dumps({{"type": "result", "result": report, "duration_ms": 60000, "total_cost_usd": 0.5,
                  "modelUsage": {{used: usage}}}}))
'''


def alive(pid):
    """Whether a process runs; a zombie that nothing has reaped yet counts as gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0] != "Z"
    except OSError:
        return True


def gone(pid):
    """Wait, for a bounded time, until a process that was signaled has ended."""
    for _ in range(100):
        if not alive(pid):
            return True
        time.sleep(0.1)
    return False


class RoundTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.case = self.root / "case"
        (self.case / "repo").mkdir(parents=True)
        (self.case / "repo" / "README.md").write_text("# Fixture\n")
        (self.case / "expected.json").write_text('{"must_find": ["REPO-01"], "must_not_flag": []}')
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(FAKE_CLAUDE.format(python=sys.executable))
        (bin_dir / "claude").chmod(0o755)
        (self.root / "state").mkdir()
        self.environment = mock.patch.dict(
            os.environ,
            {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "FAKE_STATE": str(self.root / "state"),
                "GH_TOKEN": "fake-token",
            },
        )
        self.environment.start()
        # The tests run inside other agents' sessions; their provider variables must not leak in.
        for name in [n for n in os.environ if n.startswith(("ANTHROPIC_", "CLAUDE_"))]:
            del os.environ[name]
        self.repository = mock.patch.object(claude_rounds, "ROOT", self.skill_history())
        self.repository.start()
        self.lock = mock.patch.object(claude_rounds, "ROUND_LOCK", self.root / "lock" / "rounds.lock")
        self.lock.start()
        self.rounds = []

    def skill_history(self):
        """Build a repository with two skill revisions, so tests need no history of this one."""
        repository = self.root / "repository"
        skill = repository / claude_rounds.SKILL
        (skill / "references").mkdir(parents=True)
        for name in ("criteria.md", "criteria-agents.md", "standard.md"):
            (skill / "references" / name).write_text(f"# {name}\n")
        identity = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid"}
        identity |= {"GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

        def git(*arguments):
            subprocess.run(
                ["git", *arguments], cwd=repository, env=git_environment(**identity),
                capture_output=True, check=True,
            )

        git("init", "-q", "-b", "main")
        for version in ("first", "second"):
            (skill / "SKILL.md").write_text(f"# Skill, {version} revision\n")
            git("add", "-A")
            git("commit", "-q", "-m", version)
        return repository

    def tearDown(self):
        self.lock.stop()
        self.repository.stop()
        self.environment.stop()
        for round_dir in self.rounds:
            claude_rounds.clean(round_dir)
        self.directory.cleanup()

    def plan(self, name, *runs):
        round_dir = self.root / name
        with mock.patch("builtins.print"):
            claude_rounds.plan(round_dir, list(runs), [str(self.case)], "HEAD")
        self.rounds.append(round_dir)
        return round_dir

    def test_a_round_retries_a_failed_login_and_summarizes_every_run(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "claude-flaky-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=2, timeout=60, budget=100, pause=(0, 0)), 0)
        streams = round_dir / "streams"
        self.assertTrue((streams / "run2-case.login-failure-1.jsonl").exists())
        self.assertEqual(sorted(p.name for p in (round_dir / "reports").iterdir()), ["run1-case.md", "run2-case.md"])
        self.assertIn("0.0.0", (round_dir / "cli-version.txt").read_text())
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| case | 1 | Test 1.0 | 1 of 1 | no |", summary)
        self.assertIn("| case | 2 | Flaky 1.0 | 1 of 1 | no |", summary)
        self.assertIn("paths outside the run: /home/someone/notes.txt\n", summary)
        self.assertIn("| 1.0 | 0.50 | 1 | 0 | 1,000 | 200 |", summary)
        self.assertNotIn("prepared repository changed", summary)

    def test_a_control_and_a_candidate_share_a_round_side_by_side(self):
        second = self.root / "second"
        (second / "repo").mkdir(parents=True)
        (second / "repo" / "README.md").write_text("# Second\n")
        (second / "expected.json").write_text('{"must_find": ["REPO-01"], "must_not_flag": []}')
        round_dir = self.root / "round"
        runs = claude_rounds.parse_runs(["1=claude-test-1-0@HEAD~1", "2=claude-test-1-0"])
        with mock.patch("builtins.print"):
            data = claude_rounds.plan(round_dir, runs, [str(self.case), str(second)], "HEAD")
        self.rounds.append(round_dir)
        self.assertEqual([(j["name"], j["run"]) for j in data["jobs"]],
                         [("case", "1"), ("case", "2"), ("second", "1"), ("second", "2")])
        self.assertEqual(len(data["skills"]), 2)
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=2, timeout=60, budget=100, pause=(0, 0)), 0)
        summary = claude_rounds.summarize(round_dir)
        for revision in data["skills"]:
            self.assertIn(f"| Test 1.0 @ {revision} | 2 of 2 |", summary)
        exports = [Path(path).parent for path in data["skills"].values()]
        with mock.patch("builtins.print"):
            claude_rounds.clean(round_dir)
        self.rounds.remove(round_dir)
        self.assertFalse(any(path.exists() for path in exports))

    def test_a_round_stops_launching_audits_at_its_budget(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=0.3, pause=(0, 0)), 1)
        log = (round_dir / "log.txt").read_text()
        self.assertEqual(log.count(": exit 0"), 1)
        self.assertIn("skipped, budget reached", log)

    def test_a_provider_model_runs_isolated_with_its_key_through_a_helper(self):
        key = self.root / "provider" / "key"
        key.parent.mkdir()
        key.write_text("fake-provider-key\n")
        key.chmod(0o644)
        flags = (["glm-5.3=https://provider.example"], [f"glm-5.3={key}"])
        with self.assertRaises(SystemExit):
            claude_rounds.parse_providers(*flags)
        key.chmod(0o600)
        with self.assertRaises(SystemExit):
            claude_rounds.parse_providers(flags[0], [])
        providers = claude_rounds.parse_providers(*flags)
        round_dir = self.plan("round", ("1", "glm-5.3"))
        parent = {"ANTHROPIC_AUTH_TOKEN": "parent-token", "ANTHROPIC_API_KEY": "parent-key"}
        with mock.patch.dict(os.environ, parent), mock.patch("builtins.print"):
            self.assertEqual(
                claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0), providers=providers), 0
            )
        log = (round_dir / "log.txt").read_text()
        self.assertIn("models glm-5.3\n", log)
        self.assertNotIn("KEY SOURCE", log)
        settings = next(round_dir.glob("providers/run1-case/run-settings.json"))
        self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
        self.assertIn("apiKeyHelper", settings.read_text())
        # A single leading slash would anchor the rules at the settings file's directory.
        deny = json.loads(settings.read_text())["permissions"]["deny"]
        self.assertTrue(deny)
        self.assertTrue(all(rule.startswith("Read(//") for rule in deny), deny)
        written = "".join(p.read_text() for p in round_dir.rglob("*") if p.is_file())
        for secret in ("fake-provider-key", "parent-token", "parent-key"):
            self.assertNotIn(secret, written)

    def test_levels_give_the_skill_the_catalog_or_nothing(self):
        runs = claude_rounds.parse_runs(["1=claude-test-1-0", "2=claude-test-1-0+catalog", "3=claude-test-1-0+none"])
        round_dir = self.root / "round"
        with mock.patch("builtins.print"):
            data = claude_rounds.plan(round_dir, runs, [str(self.case)], "HEAD")
        self.rounds.append(round_dir)
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=3, timeout=60, budget=100, pause=(0, 0)), 0)
        seen = {}
        for job in data["jobs"]:
            prompt, added = json.loads((self.root / "state" / f"args-{Path(job['dir']).name}").read_text())
            seen[job["level"]] = (prompt, added)
        self.assertIn("SKILL.md", seen["full"][0])
        self.assertIn("criteria.md", seen["catalog"][0])
        self.assertEqual(seen["none"][1], [])
        catalog = Path(seen["catalog"][1][0])
        self.assertEqual(sorted(p.name for p in catalog.iterdir()), ["criteria-agents.md", "criteria.md"])
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| case | 3 | Test 1.0 none | by hand | by hand |", summary)
        self.assertIn("| case | 2 | Test 1.0 catalog | 1 of 1 |", summary)

    def test_the_summary_adds_defects_at_location_only_when_a_case_counts_one(self):
        second = self.root / "second"
        (second / "repo").mkdir(parents=True)
        (second / "repo" / "README.md").write_text("# Second\n")
        (second / "expected.json").write_text('{"must_find": ["REPO-01"], "must_not_flag": []}')
        defect = {
            "description": "The README says too little",
            "ids": ["REPO-01"],
            "at": "README.md:1",
            "terms": ["more"],
            "since": "2026-10-18",
        }
        missed = defect | {"description": "The README names no owner", "terms": ["owner"]}
        round_dir = self.root / "round"
        with mock.patch("builtins.print"):
            claude_rounds.plan(round_dir, [("1", "claude-test-1-0")], [str(self.case), str(second)], "HEAD")
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 0)
        self.rounds.append(round_dir)

        def summary(started, *defects):
            log = round_dir / "log.txt"
            log.write_text(re.sub(r"^start \S+", f"start {started}", log.read_text(), flags=re.M))
            (self.case / "expected.json").write_text(
                json.dumps({"must_find": ["REPO-01"], "must_not_flag": [], "defects": list(defects)})
            )
            return claude_rounds.summarize(round_dir)

        for text in (summary("2026-10-18T09:00:00Z"), summary("2026-10-17T23:59:59Z", defect)):
            self.assertNotIn("Defects at location", text)
            self.assertIn("| case | 1 | Test 1.0 | 1 of 1 | no |", text)
            self.assertIn("| Test 1.0 | 2 of 2 | 0 of 2 |", text)
        text = summary("2026-10-18T00:00:00Z", defect, missed)
        self.assertIn("| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer |", text)
        self.assertIn("| case | 1 | Test 1.0 | 1 of 1 | 1 of 2 | no |", text)
        self.assertIn("| second | 1 | Test 1.0 | 1 of 1 | — | no |", text)
        self.assertIn("| Model | Seeded gaps found | Defects at location | Reports that pass the scorer |", text)
        self.assertIn("| Test 1.0 | 2 of 2 | 1 of 2 | 0 of 2 |", text)

    def test_a_report_without_the_skill_leaves_its_defects_to_be_scored_by_hand(self):
        defect = {"description": "The README says too little", "ids": ["REPO-01"], "at": "README.md:1"}
        (self.case / "expected.json").write_text(
            json.dumps({"must_find": ["REPO-01"], "must_not_flag": [], "defects": [defect]})
        )
        runs = claude_rounds.parse_runs(["1=claude-test-1-0", "2=claude-test-1-0+none"])
        round_dir = self.root / "round"
        with mock.patch("builtins.print"):
            claude_rounds.plan(round_dir, runs, [str(self.case)], "HEAD")
            self.assertEqual(claude_rounds.run(round_dir, jobs=2, timeout=60, budget=100, pause=(0, 0)), 0)
        self.rounds.append(round_dir)
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| case | 1 | Test 1.0 full | 1 of 1 | 1 of 1 | no |", summary)
        self.assertIn("| case | 2 | Test 1.0 none | by hand | by hand | by hand |", summary)
        self.assertIn("| Test 1.0 full | 1 of 1 | 1 of 1 | 0 of 1 |", summary)
        self.assertIn("| Test 1.0 none | 0 of 0 | 0 of 0 | 0 of 1 |", summary)

    def test_a_round_counts_defects_as_of_its_first_start_or_else_its_plan(self):
        log = self.root / "log.txt"
        data = {"created": "2026-10-16T08:00:00Z"}
        self.assertEqual(claude_rounds.round_date({"log.txt": log}, data), date(2026, 10, 16))
        log.write_text(
            "warm-up 2026-10-15T08:00:00Z ok\nstart 2026-10-17T09:00:00Z 0.0.0, budget USD 5\n"
            "stopped 2026-10-18T10:00:00Z by SIGINT\nstart 2026-10-19T09:00:00Z 0.0.0, budget USD 5\n"
        )
        self.assertEqual(claude_rounds.round_date({"log.txt": log}, data), date(2026, 10, 17))

    def test_a_model_other_than_the_requested_one_is_flagged(self):
        round_dir = self.plan("round", ("1", "claude-mismatch-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 1)
        self.assertIn("MODEL MISMATCH", (round_dir / "log.txt").read_text())

    def test_a_failed_warm_up_stops_the_round_before_any_audit(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "claude-unknown-1-0"))
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            claude_rounds.run(round_dir, jobs=2, timeout=60, budget=100, pause=(0, 0))
        self.assertEqual(list((round_dir / "streams").iterdir()), [])

    def test_a_timeout_stops_the_whole_process_group(self):
        pid_file = self.root / "child.pid"
        command = ["sh", "-c", f"sleep 30 & echo $! > {pid_file}; wait"]
        start = time.monotonic()
        code = claude_rounds.run_command(command, self.root, self.root / "out", self.root / "err", 1)
        self.assertEqual(code, -1)
        self.assertLess(time.monotonic() - start, 20)
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid_file.read_text()), 0)
        self.assertIn("stopped after", (self.root / "err").read_text())

    def stopped_round(self, model, sent):
        """Run a round whose first audit starts a grandchild and then sends `sent` to the runner.

        Stand-in handlers receive the signal if the runner has not installed its own, so a missing
        handler fails the test instead of ending it. Return the exit code, the round directory,
        and the processes the audit started; they are killed at the end if the runner left them.
        """
        round_dir = self.plan(f"round-{sent.name}", ("1", model), ("2", "claude-test-1-0"))
        received = []

        def stand_in(number, frame):
            received.append(number)

        before = {number: signal.signal(number, stand_in) for number in (signal.SIGTERM, signal.SIGINT)}
        with mock.patch.dict(os.environ, {"FAKE_SIGNAL": sent.name}), mock.patch("builtins.print"):
            try:
                code = claude_rounds.run(round_dir, jobs=1, timeout=300, budget=100, pause=(0, 0))
            finally:
                restored = {number: signal.signal(number, before[number]) for number in before}
        pids = [int(pid) for pid in (self.root / "state" / f"pids-{model}").read_text().split()]
        for pid in pids:
            self.addCleanup(lambda pid=pid: alive(pid) and os.kill(pid, signal.SIGKILL))
        self.assertEqual(received, [])
        self.assertEqual(restored, {number: stand_in for number in before})
        self.assertFalse((self.root / "state" / "expired").exists(), "the audit ended on its own")
        return code, round_dir, pids

    def test_a_stop_signal_ends_every_audit_group_and_starts_no_other(self):
        for sent in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(sent=sent.name):
                code, round_dir, pids = self.stopped_round("claude-stuck-1-0", sent)
                self.assertEqual(code, 128 + sent)
                self.assertEqual(len(pids), 2)
                self.assertEqual([gone(pid) for pid in pids], [True, True])
                self.assertIn(f"by {sent.name}: 1 running audits ended", (round_dir / "log.txt").read_text())
                self.assertEqual(list((round_dir / "reports").iterdir()), [])
                self.assertEqual([p.name for p in (round_dir / "streams").iterdir() if "run2" in p.name], [])

    def test_a_stop_signal_kills_an_audit_that_ignores_sigterm(self):
        with mock.patch.object(claude_rounds, "GRACE", 1):
            code, round_dir, pids = self.stopped_round("claude-stubborn-1-0", signal.SIGTERM)
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertEqual([gone(pid) for pid in pids], [True, True])

    def test_no_command_starts_after_the_runner_stopped(self):
        running = claude_rounds.Running()
        self.assertEqual(running.stop(), 0)
        marker = self.root / "started"
        command = ["sh", "-c", f"touch {marker}"]
        code = claude_rounds.run_command(command, self.root, self.root / "out", self.root / "err", 60, running=running)
        self.assertEqual(code, -signal.SIGTERM)
        self.assertFalse(marker.exists())

    def test_round_directories_stay_outside_the_repository_and_clean_keeps_foreign_paths(self):
        with self.assertRaises(SystemExit):
            claude_rounds.check_round_dir(claude_rounds.ROOT / "evals" / "round")
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        plan_file = round_dir / "plan.json"
        data = json.loads(plan_file.read_text())
        foreign = self.root / "audit.keepme12"
        foreign.mkdir()
        planned = Path(data["jobs"][0]["dir"])
        data["jobs"].append({**data["jobs"][0], "dir": str(foreign)})
        plan_file.write_text(json.dumps(data))
        with mock.patch("builtins.print"):
            removed = claude_rounds.clean(round_dir)
        self.assertIn(str(planned.resolve()), removed)
        self.assertFalse(planned.exists())
        self.assertTrue(foreign.exists())
        self.rounds.remove(round_dir)

    def test_audits_run_without_a_github_cli_login(self):
        hosted = {"GH_TOKEN": "fake-token", "GITHUB_TOKEN": "fake-token", "GH_CONFIG_DIR": "/elsewhere"}
        with mock.patch.dict(os.environ, hosted):
            environment = claude_rounds.audit_environment(self.root)
        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertEqual(environment["GH_CONFIG_DIR"], str(self.root / "gh-config"))
        self.assertEqual(list((self.root / "gh-config").iterdir()), [])
        self.assertEqual(environment["PATH"], os.environ["PATH"])

    def test_the_report_is_the_last_result_with_findings(self):
        results = [{"result": "## Context\n## Findings\n| A |"}, {"result": "Helpers done; see above."}]
        self.assertEqual(claude_rounds.report_text(results), "## Context\n## Findings\n| A |")
        self.assertEqual(claude_rounds.report_text([{"result": "no report"}]), "no report")
        self.assertEqual(claude_rounds.report_text([]), "")

    def test_launches_are_spaced_by_the_interval(self):
        now, slept = [100.0], []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds

        spacer = claude_rounds.StartSpacer(5, clock=lambda: now[0], sleep=sleep)
        for _ in range(3):
            spacer.wait()
        now[0] += 20
        spacer.wait()
        self.assertEqual(slept, [5, 5])

    def test_model_labels_and_audit_command(self):
        self.assertEqual(claude_rounds.model_label("claude-opus-5-5"), "Opus 5.5")
        self.assertEqual(claude_rounds.model_label("glm-5.3"), "glm-5.3")
        command = claude_rounds.claude_command("prompt", "claude-opus-5-5", [Path("/skill")])
        self.assertIn(["--add-dir", "/skill"], [command[i : i + 2] for i in range(len(command))])
        for flags in (["--setting-sources", "user"], ["--effort", "high"], ["--strict-mcp-config"]):
            self.assertTrue(any(command[i : i + len(flags)] == flags for i in range(len(command))))
        self.assertIn('{"disableAllHooks": true}', command)


    def test_a_held_round_lock_stops_a_second_round_before_any_audit(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        with claude_rounds.round_lock("scenario line, round seven"):
            with self.assertRaises(SystemExit) as refusal, mock.patch("builtins.print"):
                claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0))
        self.assertIn("scenario line, round seven", str(refusal.exception))
        self.assertFalse((round_dir / "cli-version.txt").exists())
        self.assertFalse(any((round_dir / "streams").glob("*.jsonl")))

    def test_a_round_names_itself_in_the_lock_and_releases_it(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 0)
        holder = claude_rounds.ROUND_LOCK.read_text()
        self.assertIn(f"claude_rounds run {round_dir.resolve()}, pid {os.getpid()}", holder)
        with claude_rounds.round_lock("next round"):
            self.assertIn("next round", claude_rounds.ROUND_LOCK.read_text())

    def test_a_bounded_wait_for_the_lock_ends_with_the_holder(self):
        with claude_rounds.round_lock("first"), mock.patch.object(claude_rounds, "LOCK_POLL", 0.01):
            with self.assertRaises(SystemExit) as refusal:
                with claude_rounds.round_lock("second", wait=0.05):
                    self.fail("the lock was taken twice")
        self.assertIn("first", str(refusal.exception))

if __name__ == "__main__":
    unittest.main()
