"""Check the headless round runner against a stand-in `claude` that starts no agent."""

import fcntl
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
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
if os.environ.get("FAKE_STATE"):
    with open(Path(os.environ["FAKE_STATE"]) / "updates", "a") as record:
        record.write(os.environ.get("DISABLE_AUTOUPDATER", "on") + "\n")
if arguments[:2] == ["auth", "status"]:
    if os.environ.get("FAKE_STATE"):
        (Path(os.environ["FAKE_STATE"]) / "auth-status").write_text("asked")
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
if model == "claude-no-report-1-0":
    raise SystemExit(2)
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
if model == "claude-nonzero-1-0":
    raise SystemExit(3)
'''
FAKE_GH = r'''#!{python}
"""A stand-in for the GitHub CLI: `gh api` answers from the test's file and reaches no host."""
import json, os, sys
from pathlib import Path

state = Path(os.environ["FAKE_STATE"])
with open(state / "gh-calls", "a") as record:
    record.write(json.dumps(sys.argv[1:]) + "\n")
responses = json.loads((state / "gh-responses.json").read_text())
code, answer = responses.get(sys.argv[2].partition("?")[0], [1, "Not Found (HTTP 404)"])
if code:
    print(json.dumps({"message": answer}))
    print("gh: " + answer, file=sys.stderr)
    raise SystemExit(code)
print(json.dumps(answer))
'''


def hosted_responses(commit):
    """Return the fake GitHub's answer to each path a snapshot reads, with fields it must drop."""
    base = "repos/owner/name"
    run = {"name": "test", "status": "completed", "conclusion": "success", "html_url": "https://x"}
    check = run | {"started_at": "t1", "completed_at": "t2"}
    workflow = run | {"event": "push", "created_at": "t0", "head_branch": "main"}
    status = {"context": "ci", "state": "error", "id": 2}
    combined = {"state": "pending", "total_count": 1, "statuses": [status]}
    rule = {"type": "deletion", "ruleset_id": 7, "ruleset_source": "owner/name", "url": "u"}
    return {
        base: [0, {"default_branch": "main", "visibility": "public", "archived": False, "id": 1}],
        f"{base}/commits/{commit}/check-runs": [0, {"total_count": 1, "check_runs": [check]}],
        f"{base}/actions/runs": [0, {"total_count": 1, "workflow_runs": [workflow]}],
        f"{base}/commits/{commit}/status": [0, combined],
        f"{base}/branches/main/protection": [1, "Branch not protected (HTTP 404)"],
        f"{base}/rules/branches/main": [0, [rule]],
    }


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


def free(path):
    """Whether a new handle takes the lock on `path` at once; it releases it again on return."""
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


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
        # Every test gets the stand-in, so no test can reach GitHub through the real CLI.
        (bin_dir / "gh").write_text(FAKE_GH.replace("{python}", sys.executable))
        (bin_dir / "gh").chmod(0o755)
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

    def providers(self, *served):
        """Return the providers of (model, URL) pairs, every model with one key file of mode 600."""
        key = self.root / "provider" / "key"
        key.parent.mkdir(exist_ok=True)
        key.write_text("fake-provider-key\n")
        key.chmod(0o600)
        urls = [f"{model}={url}" for model, url in served]
        return claude_rounds.parse_providers(urls, [f"{model}={key}" for model, _ in served])

    def source_case(self, name, **fields):
        """Make a case pinned to a one-commit source repository; return it and the commit."""
        source = self.root / f"{name}-source"
        source.mkdir()
        identity = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid"}
        identity |= {"GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

        def git(*arguments):
            return subprocess.run(
                ["git", *arguments], cwd=source, env=git_environment(**identity),
                capture_output=True, check=True, text=True,
            ).stdout

        git("init", "-q", "-b", "main")
        (source / "README.md").write_text("# Source\n")
        git("add", "-A")
        git("commit", "-q", "-m", "first")
        commit = git("rev-parse", "HEAD").strip()
        case = self.root / name
        case.mkdir()
        (case / "expected.json").write_text('{"must_find": ["REPO-01"], "must_not_flag": []}')
        source_json = {"repository": str(source), "commit": commit, **fields}
        (case / "source.json").write_text(json.dumps(source_json))
        return case, commit

    def gh_answers(self, responses):
        (self.root / "state" / "gh-responses.json").write_text(json.dumps(responses))

    def gh_calls(self):
        calls = self.root / "state" / "gh-calls"
        lines = calls.read_text().splitlines() if calls.exists() else []
        return [json.loads(line) for line in lines]

    def test_a_github_case_gets_one_snapshot_copied_beside_each_prepared_repository(self):
        case, commit = self.source_case("hosted", github="owner/name")
        self.gh_answers(hosted_responses(commit))
        round_dir = self.root / "round"
        runs = [("1", "claude-test-1-0"), ("2", "claude-test-1-0")]
        with mock.patch("builtins.print") as printed:
            data = claude_rounds.plan(round_dir, runs, [str(case)], "HEAD")
        self.rounds.append(round_dir)
        base = "repos/owner/name"
        paths = [
            base,
            f"{base}/commits/{commit}/check-runs?per_page=100",
            f"{base}/actions/runs?head_sha={commit}&per_page=100",
            f"{base}/commits/{commit}/status?per_page=100",
            f"{base}/branches/main/protection",
            f"{base}/rules/branches/main",
        ]
        self.assertEqual(self.gh_calls(), [["api", path] for path in paths])
        snapshot = round_dir / "hosted" / "hosted.json"
        state = json.loads(snapshot.read_text())
        self.assertRegex(state.pop("taken_at"), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        run = {"name": "test", "status": "completed", "conclusion": "success"}
        check = run | {"started_at": "t1", "completed_at": "t2"}
        workflow = run | {"event": "push", "created_at": "t0", "head_branch": "main"}
        statuses = [{"context": "ci", "state": "error"}]
        rule = {"type": "deletion", "ruleset_id": 7, "ruleset_source": "owner/name"}
        expected = {
            "github": "owner/name",
            "commit": commit,
            "repository": {"default_branch": "main", "visibility": "public", "archived": False},
            "check_runs": {"total_count": 1, "check_runs": [check]},
            "workflow_runs": {"total_count": 1, "workflow_runs": [workflow]},
            "commit_status": {"total_count": 1, "state": "pending", "statuses": statuses},
            "branch_protection": {"error": "gh: Branch not protected (HTTP 404)"},
            "branch_rules": [rule],
        }
        self.assertEqual(state, expected)
        self.assertIn("branch_protection", " ".join(str(c) for c in printed.call_args_list))
        copies = [Path(job["dir"]) / "hosted-state.json" for job in data["jobs"]]
        self.assertEqual([job["hosted"] for job in data["jobs"]], [str(copy) for copy in copies])
        for job, copy in zip(data["jobs"], copies):
            self.assertEqual(copy.read_bytes(), snapshot.read_bytes())
            repo = Path(job["dir"]) / job["name"]
            self.assertFalse((repo / "hosted-state.json").exists())
            self.assertTrue(claude_rounds.repository_clean(repo))
        written = [p.read_text() for p in [*round_dir.rglob("*"), *copies] if p.is_file()]
        self.assertFalse(any("fake-token" in text for text in written))

    def test_a_commit_without_statuses_gets_no_combined_state(self):
        commit = "a" * 40
        empty = {f"repos/owner/name/commits/{commit}/status": [0, {"state": "pending", "total_count": 0}]}
        self.gh_answers(hosted_responses(commit) | empty)
        state = claude_rounds.hosted_state("owner/name", commit)
        self.assertEqual(state["commit_status"], {"total_count": 0, "statuses": []})

    def test_a_failed_read_is_recorded_and_the_reads_that_need_it_are_left_out(self):
        commit = "a" * 40
        failing = {"repos/owner/name": [1, "Not Found (HTTP 404)"]}
        self.gh_answers(hosted_responses(commit) | failing)
        state = claude_rounds.hosted_state("owner/name", commit)
        self.assertEqual(state["repository"], {"error": "gh: Not Found (HTTP 404)"})
        unknown = {"error": "not read: the default branch is unknown"}
        self.assertEqual((state["branch_protection"], state["branch_rules"]), (unknown, unknown))
        self.assertEqual(state["check_runs"]["total_count"], 1)
        self.assertEqual(len(self.gh_calls()), 4)
        missing = FileNotFoundError(2, "No such file or directory", "gh")
        with mock.patch.object(claude_rounds.subprocess, "run", side_effect=missing):
            state = claude_rounds.hosted_state("owner/name", commit)
        self.assertEqual(
            [key for key, value in state.items() if isinstance(value, dict) and "error" in value],
            ["repository", "check_runs", "workflow_runs", "commit_status"]
            + ["branch_protection", "branch_rules"],
        )

    def test_a_github_name_must_be_owner_and_name(self):
        for number, name in enumerate(("owner", "owner/name/extra", "../name", "owner/..", 7)):
            with self.subTest(name=name):
                case, _ = self.source_case(f"case-{number}", github=name)
                round_dir = self.root / f"round-{number}"
                with self.assertRaises(SystemExit), mock.patch("builtins.print"):
                    claude_rounds.plan(round_dir, [("1", "claude-test-1-0")], [str(case)], "HEAD")
                self.assertFalse(round_dir.exists())
        self.assertEqual(self.gh_calls(), [])

    def test_a_case_without_github_reads_no_host_and_gets_no_snapshot(self):
        plain, _ = self.source_case("plain")
        round_dir = self.root / "round"
        cases = [str(plain), str(self.case)]
        with mock.patch("builtins.print"):
            data = claude_rounds.plan(round_dir, [("1", "claude-test-1-0")], cases, "HEAD")
        self.rounds.append(round_dir)
        self.assertFalse((round_dir / "hosted").exists())
        self.assertEqual(self.gh_calls(), [])
        for job in data["jobs"]:
            self.assertNotIn("hosted", job)
            self.assertEqual(os.listdir(job["dir"]), [job["name"]])

    def test_every_level_tells_where_the_snapshot_is_only_when_the_case_has_one(self):
        hosted, commit = self.source_case("hosted", github="owner/name")
        plain, _ = self.source_case("plain")
        self.gh_answers(hosted_responses(commit))
        levels = ["", "+catalog", "+none", "+expert"]
        specs = [f"{n}=claude-test-1-0{level}" for n, level in enumerate(levels, 1)]
        runs = claude_rounds.parse_runs(specs)
        round_dir = self.root / "round"
        with mock.patch("builtins.print"):
            data = claude_rounds.plan(round_dir, runs, [str(hosted), str(plain)], "HEAD")
            self.rounds.append(round_dir)
            code = claude_rounds.run(round_dir, jobs=4, timeout=60, budget=100, pause=(0, 0))
        self.assertEqual(code, 0)
        for job in data["jobs"]:
            recorded = self.root / "state" / f"args-{Path(job['dir']).name}"
            prompt, _ = json.loads(recorded.read_text())
            material = claude_rounds.job_material(data, job)
            level = claude_rounds.PROMPTS[job["level"]].format(path=material)
            sentence = (
                "The repository has no remote. GitHub's state for it, read when this round was"
                f" planned, is in `{job['dir']}/hosted-state.json`, which you may read: the CI runs"
                " and checks on the audited commit, and the default branch's protection and rules."
                " Use it in place of the host."
            )
            expected = f"{level}\n\n{sentence}" if job["name"] == "hosted" else level
            with self.subTest(case=job["name"], level=job["level"]):
                self.assertEqual(prompt, expected)

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

    def test_no_claude_the_runner_starts_can_update_itself(self):
        # Claude Code turns updates off for the shells it starts; the runner must not rely on that.
        os.environ.pop("DISABLE_AUTOUPDATER", None)
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 0)
        # The login check, the version, the warm-up, and the audit.
        self.assertEqual((self.root / "state" / "updates").read_text().split(), ["1"] * 4)

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

    def test_a_tag_records_the_commit_it_names(self):
        identity = {"GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

        def git(*arguments):
            return subprocess.run(
                ["git", *arguments], cwd=claude_rounds.ROOT, env=git_environment(**identity),
                capture_output=True, check=True, text=True,
            ).stdout.strip()

        git("tag", "-a", "v1", "-m", "Annotated, so the tag is an object of its own")
        round_dir = self.root / "round"
        runs = claude_rounds.parse_runs(["1=claude-test-1-0@v1"])
        with mock.patch("builtins.print"):
            data = claude_rounds.plan(round_dir, runs, [str(self.case)], "HEAD")
        self.rounds.append(round_dir)
        self.assertEqual(data["jobs"][0]["revision"], git("rev-parse", "--short", "HEAD"))
        self.assertEqual(list(data["skills"]), [git("rev-parse", "--short", "HEAD")])

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
        levels = ["", "+catalog", "+none", "+expert"]
        runs = claude_rounds.parse_runs([f"{n}=claude-test-1-0{level}" for n, level in enumerate(levels, 1)])
        round_dir = self.root / "round"
        with mock.patch("builtins.print"):
            data = claude_rounds.plan(round_dir, runs, [str(self.case)], "HEAD")
        self.rounds.append(round_dir)
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=4, timeout=60, budget=100, pause=(0, 0)), 0)
        seen = {}
        for job in data["jobs"]:
            prompt, added = json.loads((self.root / "state" / f"args-{Path(job['dir']).name}").read_text())
            seen[job["level"]] = (prompt, added)
        self.assertIn("SKILL.md", seen["full"][0])
        self.assertIn("criteria.md", seen["catalog"][0])
        self.assertEqual(seen["none"][1], [])
        # The expert level gets the frozen prompt and the same limits as every level, and nothing else.
        expert = claude_rounds.EXPERT_PROMPT.read_text(encoding="utf-8")
        self.assertTrue(seen["expert"][0].startswith(expert))
        self.assertIn("do not read any other path. Reply with only the final report.", seen["expert"][0])
        self.assertEqual(seen["expert"][1], [])
        catalog = Path(seen["catalog"][1][0])
        self.assertEqual(sorted(p.name for p in catalog.iterdir()), ["criteria-agents.md", "criteria.md"])
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| case | 3 | Test 1.0 none | by hand | by hand |", summary)
        self.assertIn("| case | 4 | Test 1.0 expert | by hand | by hand |", summary)
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
        self.assertEqual(list((round_dir / "streams").glob("*.jsonl")), [])
        records = [claude_rounds.read_record(round_dir, job) for job in json.loads((round_dir / "plan.json").read_text())["jobs"]]
        self.assertTrue(all(r["status"] == "skipped" and r["reasons"] == ["preflight failed"] for r in records))

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
                self.assertEqual([p.name for p in (round_dir / "streams").glob("*.jsonl") if "run2" in p.name], [])
                record = json.loads((round_dir / "streams/run2-case.run.json").read_text())
                self.assertEqual(record["status"], "skipped")
                self.assertEqual(record["reasons"], ["stopped"])

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

    def test_every_planned_job_has_a_status_and_an_invalid_run_fails_the_round(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "claude-nonzero-1-0"), ("3", "claude-no-report-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=3, timeout=10, budget=100), 1)
        data = json.loads((round_dir / "plan.json").read_text())
        records = [claude_rounds.read_record(round_dir, j) for j in data["jobs"]]
        self.assertEqual([r["status"] for r in records], ["valid", "invalid", "invalid"])
        self.assertIn("nonzero exit 3", records[1]["reasons"])
        self.assertIn("no report", records[2]["reasons"])
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| Status |", summary)
        self.assertIn("invalid: nonzero exit 3", summary)
        self.assertIn("| case | 3 | claude-no-report-1-0 | 0 of 1 | no |", summary)

    def test_a_job_without_a_report_stays_in_the_denominators(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=0.3), 1)
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| case | 2 | Test 1.0 | 0 of 1 | no |", summary)
        self.assertIn("| Test 1.0 | 1 of 2 | 0 of 2 |", summary)
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][1]
        (Path(job["dir"]) / job["name"] / "README.md").write_text("changed\n")
        self.assertIn("prepared repository changed", claude_rounds.summarize(round_dir))
        shutil.rmtree(Path(job["dir"]) / job["name"])
        self.assertIn("repository removed", claude_rounds.summarize(round_dir))

    def test_a_logged_out_claude_response_is_checked_without_saving_login_output(self):
        fake = self.root / "bin/claude"
        fake.write_text(fake.read_text().replace('{"loggedIn": True}', '{"loggedIn": False, "account": "fixture-private-login"}'))
        round_dir = self.plan("logged-out", ("1", "claude-test-1-0"))
        with self.assertRaisesRegex(SystemExit, "not logged in"):
            claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100)
        self.assertEqual(json.loads((round_dir / "auth-status.json").read_text()), {"exit_code": 0})
        for path in round_dir.rglob("*"):
            if path.is_file():
                self.assertNotIn("fixture-private-login", path.read_text(errors="replace"))

    def test_a_legacy_report_is_skipped_without_launches_or_a_failure(self):
        round_dir = self.plan("legacy", ("1", "claude-test-1-0"))
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        job.pop("backend")
        (round_dir / "plan.json").write_text(json.dumps(data))
        claude_rounds.record_path(round_dir, job).unlink()
        report = round_dir / "reports/run1-case.md"
        stream = round_dir / "streams/run1-case.jsonl"
        before = (report.read_bytes(), stream.read_bytes())
        self.assertIn("legacy, unverified", claude_rounds.summarize(round_dir))
        with mock.patch.object(claude_rounds, "run_command", side_effect=AssertionError("legacy job relaunched")):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        self.assertEqual((report.read_bytes(), stream.read_bytes()), before)
        self.assertEqual(claude_rounds.read_record(round_dir, job)["status"], "legacy")
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("legacy, unverified", summary)
        self.assertIn("| Test 1.0 | 1 of 1 |", summary)
        self.assertIn("| Valid runs |", summary)
        self.assertIn("| 0 of 1 |", summary)

    def test_an_old_report_survives_the_last_stop_and_budget_checks(self):
        for gate in ("stop", "budget", "codex_stop"):
            with self.subTest(gate=gate):
                round_dir = self.plan("kept-" + gate, ("1", "claude-test-1-0"))
                data = json.loads((round_dir / "plan.json").read_text())
                job = data["jobs"][0]
                if gate == "codex_stop":
                    job["backend"] = "codex"
                report = round_dir / "reports/run1-case.md"
                report.write_text("previous report")
                launch = {"running": claude_rounds.Running(), "spending": claude_rounds.Spending(1),
                          "codex_stop": threading.Event(), "codex_stop_reason": "login", "providers": {}}
                def gate_during_stagger():
                    if gate == "stop":
                        launch["running"].stopped.set()
                    elif gate == "budget":
                        launch["spending"].add(1)
                    else:
                        launch["codex_stop"].set()
                launch["starts"] = mock.Mock(wait=gate_during_stagger)
                with mock.patch.object(claude_rounds, "run_command", side_effect=AssertionError("launched")):
                    line = claude_rounds.audit_ready(round_dir, data, job, launch, 0)
                self.assertIn("skipped", line)
                self.assertEqual(report.read_text(), "previous report")

    def test_invalid_reports_keep_denominators_but_credit_no_findings(self):
        round_dir = self.plan("invalid", ("1", "claude-test-1-0"), ("2", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][1]
        record = claude_rounds.read_record(round_dir, job)
        claude_rounds.write_record(round_dir, data, job, ["MODEL MISMATCH"], usage=record["usage"])
        summary = claude_rounds.summarize(round_dir)
        model = next(line for line in summary.splitlines() if line.startswith("| Test 1.0 |"))
        self.assertTrue(model.startswith("| Test 1.0 | 1 of 2 | 0 of 2 |"))
        self.assertTrue(model.endswith("| 1 of 2 |"))
        self.assertIn("| case | 2 | Test 1.0 | 0 of 1 | no |", summary)
        self.assertIn("invalid: MODEL MISMATCH", summary)
        self.assertIn("Available usage", summary)
        self.assertIn("200 output", summary)

    def test_replacing_a_run_record_archives_every_previous_record(self):
        round_dir = self.plan("records", ("1", "claude-test-1-0"))
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        first = claude_rounds.write_record(round_dir, data, job, ["first failure"], usage={"tokens_in": 123})
        second = claude_rounds.write_record(round_dir, data, job, ["second failure"], usage={"tokens_in": 456})
        claude_rounds.write_record(round_dir, data, job, [], usage={"tokens_in": 789})
        claude_rounds.skipped_job(round_dir, data, job, "preflight failed")
        self.assertEqual(json.loads((round_dir / "streams/run1-case.run.1.json").read_text()), first)
        self.assertEqual(json.loads((round_dir / "streams/run1-case.run.2.json").read_text()), second)

    def test_clean_preserves_recorded_status_and_a_later_run_does_not_crash(self):
        round_dir = self.plan("cleaned", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        before = {p.name: p.read_bytes() for p in (round_dir / "streams").glob("*.run*.json")}
        claude_rounds.clean(round_dir)
        self.assertFalse(claude_rounds.repository_clean(Path(job["dir"]) / job["name"]))
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("repository removed", summary)
        self.assertIn("| valid |", summary)
        self.assertNotIn("invalid: changed repository", summary)
        with mock.patch("builtins.print"), mock.patch.object(claude_rounds, "run_command") as command:
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        command.assert_not_called()
        self.assertEqual(claude_rounds.read_record(round_dir, job)["status"], "valid")
        self.assertEqual(before, {p.name: p.read_bytes() for p in (round_dir / "streams").glob("*.run*.json")})
        self.assertEqual((round_dir / "log.txt").read_text().count("prepared repository removed; record unchanged"), 1)

    def test_summary_uses_recorded_status_even_when_the_repository_later_changes(self):
        round_dir = self.plan("changed-after-run", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        job = json.loads((round_dir / "plan.json").read_text())["jobs"][0]
        (Path(job["dir"]) / job["name"] / "README.md").write_text("changed after completion")
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| valid |", summary)
        self.assertIn("prepared repository changed", summary)
        self.assertNotIn("invalid: changed repository", summary)

    def test_a_failed_record_write_keeps_the_previous_record_in_place(self):
        round_dir = self.plan("atomic", ("1", "claude-test-1-0"))
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        original = claude_rounds.write_record(round_dir, data, job, [], usage={"tokens_out": 123})
        path = claude_rounds.record_path(round_dir, job)
        before = path.read_bytes()
        with self.assertRaises(TypeError):
            claude_rounds.write_record(round_dir, data, job, [], unserializable=object())
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(path.parent.glob("*.run.*.json")))
        temporary = path.parent / ".failed-write.tmp"
        temporary.touch()
        output = mock.MagicMock(name=str(temporary))
        output.name = str(temporary)
        output.__enter__.return_value = output
        output.write.side_effect = OSError("fixture write failure")
        with mock.patch.object(claude_rounds.tempfile, "NamedTemporaryFile", return_value=output), self.assertRaises(OSError):
            claude_rounds.write_record(round_dir, data, job, ["replacement"])
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(temporary.exists())
        self.assertFalse(list(path.parent.glob("*.run.*.json")))
        def failed_replace(source, destination):
            self.assertEqual(Path(source).parent, path.parent)
            self.assertEqual(destination, path)
            self.assertEqual(json.loads(Path(source).read_text())["reasons"], ["replacement"])
            self.assertEqual(json.loads(path.read_text()), original)
            raise OSError("fixture replace failure")
        with mock.patch.object(claude_rounds.os, "replace", side_effect=failed_replace), self.assertRaises(OSError):
            claude_rounds.write_record(round_dir, data, job, ["replacement"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads((path.parent / "run1-case.run.1.json").read_text()), original)
        self.assertFalse(list(path.parent.glob("*.tmp")))
        with mock.patch.object(claude_rounds.shutil, "copyfile", side_effect=OSError("fixture archive failure")), self.assertRaises(OSError):
            claude_rounds.write_record(round_dir, data, job, ["replacement"])
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_placeholders_never_replace_or_archive_an_existing_record(self):
        round_dir = self.plan("placeholders", ("1", "claude-test-1-0"))
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        claude_rounds.write_record(round_dir, data, job, ["real failure"], usage={"tokens_out": 123})
        path = claude_rounds.record_path(round_dir, job)
        before = path.read_bytes()
        for reason in ("not launched", "preflight failed", "stopped", "budget reached", "login", "usage limit"):
            with self.subTest(reason=reason):
                self.assertIn(reason, claude_rounds.skipped_job(round_dir, data, job, reason))
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse(list(path.parent.glob("*.run.*.json")))

    def test_a_new_claude_job_with_its_record_removed_is_never_legacy(self):
        round_dir = self.plan("new-plan", ("1", "claude-mismatch-1-0"))
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        self.assertEqual(job["backend"], "claude")
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 1)
            claude_rounds.record_path(round_dir, job).unlink()
            self.assertFalse(claude_rounds.legacy_job(round_dir, job))
            self.assertIn("unverified: no run record", claude_rounds.summarize(round_dir))
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 1)
        record = claude_rounds.read_record(round_dir, job)
        self.assertEqual(record["status"], "invalid")
        self.assertIn("MODEL MISMATCH", record["reasons"])

    def test_an_old_round_without_records_stays_unverified_after_clean(self):
        round_dir = self.plan("old-cleaned", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 0)
        data = json.loads((round_dir / "plan.json").read_text())
        job = data["jobs"][0]
        job.pop("backend")
        (round_dir / "plan.json").write_text(json.dumps(data))
        claude_rounds.record_path(round_dir, job).unlink()
        claude_rounds.clean(round_dir)
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("unverified: no run record", summary)
        self.assertIn("uncredited report", summary)
        self.assertIn("| Test 1.0 | 0 of 1 |", summary)

    def test_a_claude_runner_error_after_launch_keeps_times_and_usage(self):
        round_dir = self.plan("runner-error", ("1", "claude-test-1-0"))
        with mock.patch.object(claude_rounds, "report_text", side_effect=KeyError("fixture")), mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=10, budget=100), 1)
        job = json.loads((round_dir / "plan.json").read_text())["jobs"][0]
        record = claude_rounds.read_record(round_dir, job)
        self.assertEqual(record["status"], "invalid")
        self.assertEqual(record["reasons"], ["runner error: KeyError"])
        self.assertIsNotNone(record["started"])
        self.assertIsNotNone(record["ended"])
        self.assertGreater(record["seconds"], 0)
        self.assertEqual(record["usage"]["tokens_out"], 200)

    def test_a_stop_ends_the_stagger_wait_early(self):
        round_dir = self.plan("stagger-stop", ("1", "claude-stuck-1-0"),
                              ("2", "claude-test-1-0"), ("3", "claude-test-1-0"))
        first_spaced, all_waiting = threading.Event(), threading.Event()
        lock, count = threading.Lock(), 0
        original_wait = claude_rounds.StartSpacer.wait
        original_ready, original_command = claude_rounds.audit_ready, claude_rounds.run_command
        def observed_wait(spacer):
            nonlocal count
            with lock:
                count += 1
                if count == 3:
                    all_waiting.set()
            original_wait(spacer)
            first_spaced.set()
        def ordered_ready(directory, data, job, launch, queued):
            if job["run"] != "1":
                self.assertTrue(first_spaced.wait(2))
            return original_ready(directory, data, job, launch, queued)
        def observed_command(command, *args, **kwargs):
            if "stream-json" in command:
                self.assertTrue(all_waiting.wait(2))
            return original_command(command, *args, **kwargs)
        started = time.monotonic()
        with mock.patch("builtins.print"), mock.patch.object(claude_rounds, "GRACE", 0.1), \
             mock.patch.object(claude_rounds.StartSpacer, "wait", observed_wait), \
             mock.patch.object(claude_rounds, "audit_ready", side_effect=ordered_ready), \
             mock.patch.object(claude_rounds, "run_command", side_effect=observed_command):
            code = claude_rounds.run(round_dir, jobs=3, timeout=10, budget=100, stagger=3)
        elapsed = time.monotonic() - started
        pids = [int(pid) for pid in (self.root / "state/pids-claude-stuck-1-0").read_text().split()]
        for pid in pids:
            self.addCleanup(lambda pid=pid: alive(pid) and os.kill(pid, signal.SIGKILL))
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertLess(elapsed, 2.5, "stagger waiting did not wake on stop")
        self.assertEqual(len(list((self.root / "state").glob("args-*"))), 1)

    def group_with_stubborn_child(self, normal_exit):
        marker = self.root / "child-ready"
        child_code = "import os, signal, time; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); Path(" + repr(str(marker)) + ").write_text(str(os.getpid())); time.sleep(60)"
        leader_code = "import subprocess, sys, time; from pathlib import Path; subprocess.Popen([sys.executable, '-c', " + repr(child_code) + "]); p=Path(" + repr(str(marker)) + ");\nwhile not p.exists(): time.sleep(0.01)\n" + ("" if normal_exit else "time.sleep(60)")
        process = subprocess.Popen([sys.executable, "-c", leader_code], start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: claude_rounds.stop_groups([process], 0))
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists())
        child = int(marker.read_text())
        self.addCleanup(lambda: alive(child) and os.kill(child, signal.SIGKILL))
        return process, child

    def test_a_child_that_ignores_sigterm_is_killed_after_its_leader_exits(self):
        process, child = self.group_with_stubborn_child(False)
        with mock.patch.object(claude_rounds, "GRACE", 0.05):
            claude_rounds.stop_groups([process])
        self.assertIsNotNone(process.poll())
        self.assertTrue(gone(child))

    def test_a_child_that_outlives_its_leader_is_killed_after_a_normal_exit(self):
        marker = self.root / "normal-child"
        child_code = "import os, signal, time; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); Path(" + repr(str(marker)) + ").write_text(str(os.getpid())); time.sleep(60)"
        leader_code = "import subprocess, sys, time; from pathlib import Path; subprocess.Popen([sys.executable, '-c', " + repr(child_code) + "]); p=Path(" + repr(str(marker)) + ");\nwhile not p.exists(): time.sleep(0.01)"
        with mock.patch.object(claude_rounds, "EXIT_GRACE", 0.05):
            self.assertEqual(claude_rounds.run_command([sys.executable, "-c", leader_code], self.root,
                self.root / "out", self.root / "err", 3), 0)
        child = int(marker.read_text())
        self.addCleanup(lambda: alive(child) and os.kill(child, signal.SIGKILL))
        self.assertTrue(gone(child))

    def test_running_stop_signals_registered_groups_even_after_the_leader_exits(self):
        process, child = self.group_with_stubborn_child(True)
        process.wait(timeout=3)
        running = claude_rounds.Running()
        running.processes.add(process)
        with mock.patch.object(claude_rounds, "GRACE", 0.05):
            self.assertEqual(running.stop(), 1)
        self.assertTrue(gone(child))

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
        start = command.index("--tools") + 1
        self.assertEqual(command[start : start + 6], ["Bash", "Read", "Grep", "Glob", "Agent", "--allowedTools"])


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

    def test_rounds_on_different_resources_run_at_once_and_on_one_exclude_each_other(self):
        glm = claude_rounds.ROUND_LOCK.with_name("rounds-api.z.ai.lock")
        self.assertEqual(claude_rounds.lock_path("anthropic"), claude_rounds.ROUND_LOCK)
        self.assertEqual(claude_rounds.lock_path("api.z.ai"), glm)
        with claude_rounds.round_lock("claude round"):
            with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
                self.assertTrue(glm.is_file())
                self.assertEqual(glm.parent, self.root / "lock")
                self.assertIn("claude round", claude_rounds.ROUND_LOCK.read_text())
                self.assertIn("glm round", glm.read_text())
                with self.assertRaises(SystemExit) as refusal:
                    with claude_rounds.round_lock("second glm round", resources=("api.z.ai",)):
                        self.fail("one resource was locked twice")
                self.assertIn("glm round", str(refusal.exception))
                self.assertIn("rounds-api.z.ai.lock", str(refusal.exception))
            with self.assertRaises(SystemExit):
                with claude_rounds.round_lock("second claude round"):
                    self.fail("one resource was locked twice")

    def test_free_locks_are_taken_at_once(self):
        resources = ("api.z.ai", "anthropic")
        with claude_rounds.round_lock("both", wait=0, resources=resources):
            for path in map(claude_rounds.lock_path, resources):
                self.assertIn("both, pid", path.read_text())
                self.assertIn("for anthropic, api.z.ai", path.read_text())
                self.assertFalse(free(path))

    def test_duplicate_resources_do_not_refuse_themselves(self):
        with claude_rounds.round_lock("twice", resources=("api.z.ai", "anthropic", "api.z.ai", "anthropic")):
            self.assertFalse(free(claude_rounds.lock_path("api.z.ai")))

    def test_a_refused_set_names_the_holder_and_leaves_every_file_as_it_was(self):
        with claude_rounds.round_lock("finished round"):
            pass
        before = claude_rounds.ROUND_LOCK.read_text()
        with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
            with self.assertRaises(SystemExit) as refusal:
                with claude_rounds.round_lock("mixed round", resources=("anthropic", "api.z.ai")):
                    self.fail("a held lock was taken")
            self.assertIn("rounds-api.z.ai.lock: glm round", str(refusal.exception))
            self.assertEqual(claude_rounds.ROUND_LOCK.read_text(), before)
            with claude_rounds.round_lock("probe", wait=0):
                self.assertIn("probe", claude_rounds.ROUND_LOCK.read_text())

    def test_an_interrupted_wait_leaves_the_first_lock_free(self):
        with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
            with mock.patch("time.sleep", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
                with claude_rounds.round_lock("mixed round", wait=60, resources=("anthropic", "api.z.ai")):
                    self.fail("a held lock was taken")
            self.assertTrue(free(claude_rounds.ROUND_LOCK))

    def test_a_waiting_set_holds_none_of_its_locks(self):
        probes, real_sleep = [], time.sleep

        def sleep(seconds):
            # Another round's attempt that waits for nothing, made while the set waits.
            with claude_rounds.round_lock("probe", wait=0):
                probes.append(seconds)
            real_sleep(seconds)

        with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
            with mock.patch.object(claude_rounds, "LOCK_POLL", 0.01), mock.patch("time.sleep", sleep):
                with self.assertRaises(SystemExit) as refusal:
                    with claude_rounds.round_lock("mixed round", wait=0.05, resources=("anthropic", "api.z.ai")):
                        self.fail("a held lock was taken")
        self.assertIn("rounds-api.z.ai.lock: glm round", str(refusal.exception))
        self.assertTrue(probes)

    def test_a_set_waits_until_one_deadline(self):
        started, real_sleep = time.monotonic(), time.sleep

        def sleep(seconds):
            if time.monotonic() - started > 1:
                raise AssertionError("the wait outlived its deadline")
            real_sleep(seconds)

        with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
            with mock.patch.object(claude_rounds, "LOCK_POLL", 0.01), mock.patch("time.sleep", sleep):
                with self.assertRaises(SystemExit) as refusal:
                    with claude_rounds.round_lock("mixed round", wait=0.05, resources=("anthropic", "api.z.ai")):
                        self.fail("a held lock was taken")
        self.assertLess(time.monotonic() - started, 1)
        self.assertIn("rounds-api.z.ai.lock: glm round", str(refusal.exception))

    def test_a_round_needs_one_resource_per_provider(self):
        providers = {
            "glm-5.3": {"url": "https://api.z.ai/api/anthropic"},
            "glm-4.6": {"url": "https://API.Z.ai:443/api/anthropic"},
            "proxy-1": {"url": "http://localhost:4000"},
            "proxy-2": {"url": "http://localhost:80/v1"},
            "unused-1": {"url": "https://unused.example"},
        }
        resources = claude_rounds.round_resources
        self.assertEqual(resources(["claude-test-1-0", "claude-other-1-0"], providers), ("anthropic",))
        self.assertEqual(resources(["glm-5.3", "claude-test-1-0"], providers), ("anthropic", "api.z.ai"))
        self.assertEqual(resources(["glm-5.3", "glm-4.6"], providers), ("api.z.ai",))
        self.assertEqual(resources(["proxy-1", "proxy-2"], providers), ("localhost", "localhost_4000"))
        self.assertEqual(resources([], providers), ())
        with self.assertRaises(SystemExit) as refusal:
            resources(["glm-5.3"], {"glm-5.3": {"url": "http://h:abc"}})
        self.assertIn("invalid port", str(refusal.exception))

    def test_a_provider_host_is_a_plain_name_other_than_anthropic(self):
        for host in ("..", "api.z.ai/v1", "api.z.ai\n", "anthropic", ""):
            with self.subTest(host=host), self.assertRaises(SystemExit):
                claude_rounds.check_host(host)
        for url in ("https://../v1", "https://anthropic", "http://anthropic:4000", "api.z.ai"):
            with self.subTest(url=url), self.assertRaises(SystemExit):
                claude_rounds.round_resources(["glm-5.3"], {"glm-5.3": {"url": url}})
        for resource in ("../rounds", "api.z.ai/v1", "api.z.ai\n", "api.z.ai_", "anthropic_4000"):
            with self.subTest(resource=resource), self.assertRaises(SystemExit):
                with claude_rounds.round_lock("bad name", resources=(resource,)):
                    self.fail("a lock with a bad name was taken")
        self.assertFalse(claude_rounds.ROUND_LOCK.parent.exists())

    def test_a_provider_round_runs_beside_a_claude_round_without_the_claude_login(self):
        providers = self.providers(("glm-5.3", "https://api.z.ai/api/anthropic"))
        round_dir = self.plan("round", ("1", "glm-5.3"))
        with claude_rounds.round_lock("claude round"), mock.patch("builtins.print"):
            code = claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0), providers=providers)
        self.assertEqual(code, 0)
        self.assertFalse((self.root / "state" / "auth-status").exists())
        self.assertIn(f"claude_rounds run {round_dir.resolve()}", claude_rounds.lock_path("api.z.ai").read_text())
        self.assertIn("claude round", claude_rounds.ROUND_LOCK.read_text())
        log = (round_dir / "log.txt").read_text()
        self.assertIn("others start rounds.lock held=yes changed=no holder=claude round", log)
        summary = claude_rounds.summarize(round_dir).splitlines()
        self.assertEqual(summary[2], "Overlapped with another round: its minutes are not comparable.")

    def test_a_mixed_round_is_refused_while_one_provider_is_busy_and_holds_nothing(self):
        providers = self.providers(("glm-5.3", "https://api.z.ai/api/anthropic"))
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "glm-5.3"))
        with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
            with self.assertRaises(SystemExit) as refusal, mock.patch("builtins.print"):
                claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0), providers=providers)
            self.assertIn("rounds-api.z.ai.lock: glm round", str(refusal.exception))
            self.assertTrue(free(claude_rounds.ROUND_LOCK))
        self.assertFalse((round_dir / "cli-version.txt").exists())

    def other_lock(self, text="glm round, pid 7, since 2026-10-18T08:00:00Z, for api.z.ai\n"):
        """Leave the lock file of a provider round that is not running; return its path."""
        path = claude_rounds.ROUND_LOCK.with_name("rounds-api.z.ai.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def probe(self, start=None):
        """Return the probe's lines for a round on the Claude login, and what they read."""
        return claude_rounds.lock_overlaps(("anthropic",), start)

    def test_the_probe_sees_a_lock_held_elsewhere_then_free_and_changed(self):
        glm = self.other_lock("")
        with claude_rounds.round_lock("this round"):
            lines, start = self.probe()
            self.assertEqual(
                lines, ["others start: 1 files", "others start rounds-api.z.ai.lock held=no changed=no holder="]
            )
            with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
                lines, _ = self.probe(start)
                self.assertRegex(lines[1], r"^others end rounds-api.z.ai.lock held=yes changed=yes holder=glm round")
            lines, _ = self.probe(start)
            self.assertRegex(lines[1], r"^others end rounds-api.z.ai.lock held=no changed=yes holder=glm round")
        self.assertIn("glm round", glm.read_text())

    def test_the_probe_counts_a_file_created_mid_round_as_changed_once_written(self):
        with claude_rounds.round_lock("this round"):
            lines, start = self.probe()
            self.assertEqual(lines, ["others start: 0 files"])
            with claude_rounds.round_lock("glm round", resources=("api.z.ai",)):
                pass
            # A refused round creates its file and writes nothing.
            claude_rounds.ROUND_LOCK.with_name("rounds-refused.example.lock").touch()
            lines, _ = self.probe(start)
        self.assertEqual(lines[0], "others end: 2 files")
        self.assertRegex(lines[1], r"^others end rounds-api.z.ai.lock held=no changed=yes holder=glm round")
        self.assertEqual(lines[2], "others end rounds-refused.example.lock held=no changed=no holder=")

    def test_the_probe_reports_a_lock_never_taken_as_free_and_unchanged(self):
        self.other_lock()
        with claude_rounds.round_lock("this round"):
            _, start = self.probe()
            lines, _ = self.probe(start)
        self.assertEqual(lines[1], "others end rounds-api.z.ai.lock held=no changed=no holder=glm round, pid 7,"
                         " since 2026-10-18T08:00:00Z, for api.z.ai")

    def test_the_probe_counts_a_file_deleted_and_recreated_as_changed(self):
        glm = self.other_lock()
        with claude_rounds.round_lock("this round"):
            _, start = self.probe()
            # The new file exists before the old one goes, so it cannot reuse the old inode.
            new = glm.with_name("recreated")
            new.write_text(glm.read_text())
            os.replace(new, glm)
            lines, _ = self.probe(start)
        self.assertRegex(lines[1], r"^others end rounds-api.z.ai.lock held=no changed=yes holder=glm round")

    def test_the_probe_says_unknown_without_proc_locks(self):
        self.other_lock()
        with claude_rounds.round_lock("this round"):
            with mock.patch.object(claude_rounds, "PROC_LOCKS", self.root / "missing"):
                lines, _ = self.probe()
        self.assertRegex(lines[1], r"^others start rounds-api.z.ai.lock held=unknown changed=no ")

    def test_the_probe_reads_device_numbers_in_hex_and_skips_waiters(self):
        glm = self.other_lock("glm round\n")
        with claude_rounds.round_lock("this round"):
            own, other = (path.stat().st_ino for path in (claude_rounds.ROUND_LOCK, glm))
            mine = f"1: FLOCK  ADVISORY  WRITE {os.getpid()} 08:30:{own} 0 EOF"

            def identity(status):
                """Put every file on device 8:48, which /proc/locks prints as 08:30."""
                return 8, 48, status.st_ino

            holder = f"2: FLOCK  ADVISORY  WRITE 7 08:30:{other} 0 EOF"
            fakes = {
                "the other inode on another device": ([mine, holder.replace("08:30", "08:31")], "no"),
                "a waiter on the other file": ([mine, holder.replace("2: ", "2: -> ")], "no"),
                "a holder of the other file": ([mine, holder], "yes"),
                "no lock of this round": ([holder], "unknown"),
            }
            for name, (lines, held) in fakes.items():
                fake = self.root / "locks"
                fake.write_text("".join(f"{line}\n" for line in lines))
                fields = f"held={held} changed=no holder=glm round"
                with self.subTest(name), mock.patch.multiple(claude_rounds, PROC_LOCKS=fake, lock_identity=identity):
                    self.assertEqual(self.probe()[0][1], f"others start rounds-api.z.ai.lock {fields}")

    def test_a_round_logs_the_other_locks_before_it_starts_and_after_it_ends(self):
        self.other_lock()
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 0)
        log = (round_dir / "log.txt").read_text()
        for phase in ("start", "end"):
            lines = f"others {phase}: 1 files\nothers {phase} rounds-api.z.ai.lock held=no changed=no"
            self.assertIn(f"{lines} holder=glm round", log)
        self.assertLess(log.index("others start:"), log.index("\nstart "))
        self.assertLess(log.index("\nend "), log.index("others end:"))
        self.assertNotIn("Overlap", claude_rounds.summarize(round_dir))

    def test_a_round_alone_still_marks_its_start_and_end(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 0)
        log = (round_dir / "log.txt").read_text()
        self.assertTrue(log.startswith("others start: 0 files\nstart "), log)
        self.assertTrue(log.endswith("\nothers end: 0 files\n"), log)
        self.assertNotIn("Overlap", claude_rounds.summarize(round_dir))

    def test_a_round_that_stops_early_still_logs_the_end_of_its_overlaps(self):
        self.other_lock()
        code, round_dir, _ = self.stopped_round("claude-stuck-1-0", signal.SIGTERM)
        self.assertEqual(code, 128 + signal.SIGTERM)
        end = "others end: 1 files\nothers end rounds-api.z.ai.lock held=no changed=no holder=glm round, pid 7,"
        self.assertIn(end, (round_dir / "log.txt").read_text())
        # A failed warm-up exits the round.
        round_dir = self.plan("failed", ("1", "claude-unknown-1-0"))
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0))
        self.assertIn(end, (round_dir / "log.txt").read_text())

    def test_the_summary_marks_a_round_that_overlapped_another_or_may_have(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, budget=100, pause=(0, 0)), 0)
        audits = "start 2026-10-18T09:00:00Z 0.0.0, budget USD 100\nrun1-case: exit 0\nend 2026-10-18T09:01:00Z\n"

        def lines(phase, held="no", changed="no"):
            marker = f"others {phase}: 1 files\n"
            return marker + f"others {phase} rounds-api.z.ai.lock held={held} changed={changed} holder=glm round\n"

        overlapped, unknown = "Overlapped with another round: its minutes are not comparable.", "Overlap unknown."
        logs = {
            "clean": (lines("start") + audits + lines("end"), None),
            "an older runner": (audits, None),
            "held at the start": (lines("start", held="yes") + audits + lines("end"), overlapped),
            "held at the end": (lines("start") + audits + lines("end", held="yes"), overlapped),
            "changed": (lines("start") + audits + lines("end", changed="yes"), overlapped),
            "changed, held unknown": (lines("start") + audits + lines("end", "unknown", "yes"), overlapped),
            "unknown": (lines("start", held="unknown") + audits + lines("end", held="unknown"), unknown),
            "no end": (lines("start") + audits, unknown),
            "no end, then resumed": (lines("start") + audits + lines("start") + audits + lines("end"), unknown),
        }
        for name, (text, note) in logs.items():
            with self.subTest(name):
                (round_dir / "log.txt").write_text(text)
                summary = claude_rounds.summarize(round_dir)
                if note:
                    self.assertEqual(summary.splitlines()[1:4], ["", note, ""])
                else:
                    self.assertNotIn("Overlap", summary)


class SummaryActivityTests(unittest.TestCase):
    """Small streams and summary tables, without an agent or a Git repository."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.stream = self.root / "stream.jsonl"

    @staticmethod
    def assistant(*names, parent=None):
        return {"type": "assistant", "parent_tool_use_id": parent, "message": {"content": [
            {"type": "tool_use", "name": name, "input": {}} for name in names
        ]}}

    def write_stream(self, *events):
        self.stream.write_text("".join(json.dumps(event) + "\n" for event in events))

    def test_helpers_started_counts_agent_and_task_calls(self):
        self.write_stream(self.assistant("Agent", "Read", "Task", "Agent"))
        self.assertEqual(claude_rounds.stream_activity(self.stream), (3, ["Task"]))

    def test_readable_run_without_helper_starts_is_zero(self):
        self.write_stream(self.assistant("Read", "Bash"), {"type": "result"})
        self.assertEqual(claude_rounds.stream_activity(self.stream), (0, []))

    def test_nested_helpers_are_not_starts_by_the_lead(self):
        self.write_stream(self.assistant("Agent"), self.assistant("Agent", "Task", parent="lead-call"))
        self.assertEqual(claude_rounds.stream_activity(self.stream), (1, ["Task"]))

    def test_only_assistant_tool_use_blocks_count(self):
        event = self.assistant("Agent", "Monitor") | {"type": "user"}
        self.write_stream(event, {"type": "assistant", "message": {"content": [
            {"type": "text", "name": "Agent", "text": "Agent Monitor"}
        ]}})
        self.assertEqual(claude_rounds.stream_activity(self.stream), (0, []))

    def test_unreadable_stream_counts_are_unknown(self):
        self.assertEqual(claude_rounds.stream_activity(self.stream), (None, []))
        for content in (b"", b"bad json\n", b"[]\n", b"null\n", b"\xff"):
            with self.subTest(content=content):
                self.stream.write_bytes(content)
                self.assertEqual(claude_rounds.stream_activity(self.stream), (None, []))
        with mock.patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertEqual(claude_rounds.stream_activity(self.stream), (None, []))

    def test_partial_stream_keeps_unexpected_tools_but_not_a_count(self):
        self.write_stream(self.assistant("Agent", "Monitor"))
        with self.stream.open("a") as output:
            output.write("broken\n")
        self.assertEqual(claude_rounds.stream_activity(self.stream), (None, ["Monitor"]))

    def test_malformed_assistant_or_tool_cannot_establish_zero(self):
        for message in ({}, {"content": "text"}, {"content": [{"type": "tool_use"}]}):
            with self.subTest(message=message):
                self.write_stream({"type": "assistant", "message": message})
                self.assertIsNone(claude_rounds.stream_activity(self.stream)[0])

    def test_unexpected_tools_include_lead_and_helpers_once_in_name_order(self):
        self.write_stream(self.assistant("Monitor", "Read"), self.assistant("Zebra", "Monitor", parent="helper"))
        self.assertEqual(claude_rounds.stream_activity(self.stream), (0, ["Monitor", "Zebra"]))

    def test_tool_check_reads_the_commands_allowed_list(self):
        self.write_stream(self.assistant("Monitor", "Read"))
        with mock.patch.object(claude_rounds, "AUDIT_TOOLS", ("Monitor",)):
            command = claude_rounds.claude_command("prompt", "model", [])
            self.assertEqual(command[command.index("--tools") + 1:command.index("--allowedTools")], ["Monitor"])
            self.assertEqual(claude_rounds.stream_activity(self.stream), (0, ["Read"]))

    @staticmethod
    def tables(summary):
        tables, current = [], []
        for line in summary.splitlines():
            if line.startswith("| ---"):
                continue
            if line.startswith("| "):
                current.append([cell.strip() for cell in line.strip("|").split("|")])
            elif current:
                tables.append([dict(zip(current[0], row)) for row in current[1:]])
                current = []
        return tables

    def summary_fixture(self, entries, backend="claude"):
        case = self.root / "case"
        (case / "repo").mkdir(parents=True)
        (case / "expected.json").write_text('{"must_find": [], "must_not_flag": []}')
        for folder in ("streams", "reports"):
            (self.root / folder).mkdir()
        (self.root / "tmp-before.txt").write_text("")
        jobs = []
        for number, (events, status) in enumerate(entries, 1):
            job = {"run": number, "name": "case", "case": str(case), "dir": str(case.parent),
                   "backend": backend, "model": "claude-test-1-0"}
            jobs.append(job)
            stream = self.root / "streams" / f"run{number}-case.jsonl"
            if events is not None:
                stream.write_text("".join(json.dumps(e) + "\n" for e in events))
            report = self.root / "reports" / f"run{number}-case.md"
            report.write_text("## Findings\n")
            record = {"status": status, "report_sha256": claude_rounds.sha256(report)}
            (stream.with_suffix(".run.json")).write_text(json.dumps(record))
        data = {"created": "2026-10-23T00:00:00Z", "skill_commit": "fixture", "level": "none", "jobs": jobs}
        (self.root / "plan.json").write_text(json.dumps(data))
        return jobs

    def summarize(self):
        with mock.patch.object(claude_rounds, "repository_problems", return_value=[]):
            return self.tables(claude_rounds.summarize(self.root))

    def test_summary_counts_unknowns_and_only_valid_zero_runs(self):
        self.summary_fixture([
            ([self.assistant("Agent", "Agent")], "valid"),
            ([self.assistant("Read")], "valid"),
            (None, "valid"),
            ([self.assistant("Read")], "invalid"),
            ([self.assistant("Read")], "legacy"),
        ])
        runs, models = self.summarize()
        self.assertEqual([row["Helpers started"] for row in runs], ["2", "0", "—", "0", "0"])
        self.assertEqual(models[0]["Mean helpers started"], "0.50 (4 of 5)")
        self.assertEqual(models[0]["Valid runs with no helpers"], "1 of 2 (2 of 3 readable)")

    def test_summary_problems_include_unexpected_tools_even_for_invalid_runs(self):
        self.summary_fixture([
            ([self.assistant("Monitor")], "valid"),
            ([self.assistant("Read"), self.assistant("Monitor", parent="helper")], "invalid"),
        ])
        runs, models = self.summarize()
        self.assertEqual(runs[0]["Problems"], "tools outside the list: Monitor")
        self.assertEqual(runs[1]["Problems"], "uncredited report; tools outside the list: Monitor")
        self.assertEqual(models[0]["Mean helpers started"], "0.00")
        self.assertEqual(models[0]["Valid runs with no helpers"], "1 of 1")

    def test_summary_with_no_readable_count_shows_no_zero(self):
        self.summary_fixture([(None, "valid")])
        runs, models = self.summarize()
        self.assertEqual(runs[0]["Helpers started"], "—")
        self.assertEqual(models[0]["Mean helpers started"], "—")
        self.assertEqual(models[0]["Valid runs with no helpers"], "— (0 of 1 readable)")

    def test_summary_survives_a_stream_read_error(self):
        self.summary_fixture([([self.assistant("Read")], "valid")])
        original = Path.read_text
        def unreadable(path, *args, **kwargs):
            if path.suffix == ".jsonl":
                raise PermissionError("fixture stream")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "read_text", unreadable):
            runs, _ = self.summarize()
        self.assertEqual(runs[0]["Helpers started"], "—")

    def test_changed_artifacts_do_not_count_as_valid_zero_helper_runs(self):
        self.summary_fixture([([self.assistant("Read")], "valid")])
        (self.root / "reports/run1-case.md").write_text("changed report\n")
        runs, models = self.summarize()
        self.assertEqual(runs[0]["Helpers started"], "0")
        self.assertEqual(runs[0]["Status"], "invalid: artifacts changed after the run")
        self.assertEqual(models[0]["Valid runs with no helpers"], "—")

    def test_codex_summary_uses_session_thread_count(self):
        self.summary_fixture([([], "invalid")], backend="codex")
        with mock.patch.object(claude_rounds.codex_backend, "helpers_started", return_value=4) as count:
            runs, models = self.summarize()
        count.assert_called_once_with(self.root / "streams/run1-case.jsonl")
        self.assertEqual(runs[0]["Helpers started"], "4")
        self.assertEqual(models[0]["Mean helpers started"], "4.00 (1 of 1)")


if __name__ == "__main__":
    unittest.main()
