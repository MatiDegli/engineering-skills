"""Check the headless round runner against a stand-in `claude` that starts no agent."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tools import claude_rounds
from tools.validate_repo import ROOT

FAKE_CLAUDE = r'''#!{python}
"""A stand-in for the claude CLI: it answers like the real one and starts no agent."""
import json, os, sys
from pathlib import Path

arguments = sys.argv[1:]
if arguments[:2] == ["auth", "status"]:
    print(json.dumps({{"loggedIn": True}}, indent=2))
    raise SystemExit(0)
if arguments == ["--version"]:
    print("0.0.0 (Claude Code)")
    raise SystemExit(0)
model = arguments[arguments.index("--model") + 1]
if "json" == arguments[arguments.index("--output-format") + 1]:
    if model == "claude-unknown-1-0":
        print(json.dumps({{"type": "result", "is_error": True, "result": "unknown model"}}))
    else:
        print(json.dumps({{"type": "result", "is_error": False, "result": "OK", "modelUsage": {{model: {{}}}}}}))
    raise SystemExit(0)
state = Path(os.environ["FAKE_STATE"]) / (model + "-" + Path.cwd().parent.name)
if model == "claude-flaky-1-0" and not state.exists():
    state.write_text("failed once")
    print(json.dumps({{"type": "result", "result": "Failed to refresh OAuth token: another process"}}))
    raise SystemExit(1)
used = "claude-other-1-0" if model == "claude-mismatch-1-0" else model
tool = {{"type": "tool_use", "name": "Bash", "input": {{"command": "cat /home/someone/notes.txt"}}}}
print(json.dumps({{"type": "assistant", "message": {{"content": [tool]}}}}))
report = "## Findings\n| ID | Status | Priority | Evidence | Improvement |\n| --- | --- | --- | --- | --- |\n"
report += "| REPO-01 | partial | low | `README.md:1` | Say more |\n"
print(json.dumps({{"type": "result", "result": report, "duration_ms": 60000, "total_cost_usd": 0.5,
                  "modelUsage": {{used: {{}}}}}}))
'''


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
            {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_STATE": str(self.root / "state")},
        )
        self.environment.start()
        self.rounds = []

    def tearDown(self):
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
            self.assertEqual(claude_rounds.run(round_dir, jobs=2, timeout=60, pause=(0, 0)), 0)
        streams = round_dir / "streams"
        self.assertTrue((streams / "run2-case.login-failure-1.jsonl").exists())
        self.assertEqual(sorted(p.name for p in (round_dir / "reports").iterdir()), ["run1-case.md", "run2-case.md"])
        self.assertIn("0.0.0", (round_dir / "cli-version.txt").read_text())
        summary = claude_rounds.summarize(round_dir)
        self.assertIn("| case | 1 | Test 1.0 | 1 of 1 | no |", summary)
        self.assertIn("| case | 2 | Flaky 1.0 | 1 of 1 | no |", summary)
        self.assertIn("paths outside the run: /home/someone/notes.txt", summary)
        self.assertIn("| 1.0 | 0.50 |", summary)
        self.assertNotIn("prepared repository changed", summary)

    def test_a_model_other_than_the_requested_one_is_flagged(self):
        round_dir = self.plan("round", ("1", "claude-mismatch-1-0"))
        with mock.patch("builtins.print"):
            self.assertEqual(claude_rounds.run(round_dir, jobs=1, timeout=60, pause=(0, 0)), 1)
        self.assertIn("MODEL MISMATCH", (round_dir / "log.txt").read_text())

    def test_a_failed_warm_up_stops_the_round_before_any_audit(self):
        round_dir = self.plan("round", ("1", "claude-test-1-0"), ("2", "claude-unknown-1-0"))
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            claude_rounds.run(round_dir, jobs=2, timeout=60, pause=(0, 0))
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

    def test_round_directories_stay_outside_the_repository_and_clean_keeps_foreign_paths(self):
        with self.assertRaises(SystemExit):
            claude_rounds.check_round_dir(ROOT / "evals" / "round")
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

    def test_model_labels_and_audit_command(self):
        self.assertEqual(claude_rounds.model_label("claude-opus-5-5"), "Opus 5.5")
        self.assertEqual(claude_rounds.model_label("glm-5.3"), "glm-5.3")
        command = claude_rounds.claude_command("prompt", "claude-opus-5-5", Path("/skill"))
        for flags in (["--setting-sources", "user"], ["--effort", "high"], ["--strict-mcp-config"]):
            self.assertTrue(any(command[i : i + len(flags)] == flags for i in range(len(command))))
        self.assertIn('{"disableAllHooks": true}', command)


if __name__ == "__main__":
    unittest.main()
