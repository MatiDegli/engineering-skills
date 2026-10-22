"""Check Codex rounds using synthetic stream and session records, without starting an agent."""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tests import test_claude_rounds as shared
from tools import claude_rounds as runner, codex_backend as codex

FAKE_CODEX = r'''#!{python}
import json, os, shlex, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

home = Path.home()
state = home / "fake-state"
config = json.loads((state / "config.json").read_text())
args = sys.argv[1:]
with (state / "calls.jsonl").open("a") as out:
    out.write(json.dumps({"args": args, "environment_names": sorted(os.environ), "stdin_target": os.readlink("/proc/self/fd/0")}) + "\n")
if args == ["--version"]:
    print("0.163.0 (Codex fixture)")
    raise SystemExit(0)
if args == ["login", "status"]:
    print("fixture-private-login-output")
    print("fixture-private-login-stderr", file=sys.stderr)
    raise SystemExit(config.get("login_exit", 0))
assert args[0] == "exec"
repo = Path(args[args.index("-C") + 1])
model = args[args.index("-m") + 1]
last = Path(args[args.index("-o") + 1])
prompt = args[-1]
warmup = repo.name.startswith("codex-probe.")
mode = config.get("warmup", "ok") if warmup else config.get("mode", "ok")
thread = str(uuid.uuid4())
root = home / "sessions" / datetime.now(timezone.utc).strftime("%Y/%m/%d")
root.mkdir(parents=True, exist_ok=True)
def record(kind, **payload):
    return {"type": kind, "payload": payload}
def call(name, identity, namespace=None, **extra):
    return record("response_item", type="function_call", name=name, call_id=identity, namespace=namespace, **extra)
def output(identity, value):
    return record("response_item", type="function_call_output", call_id=identity, output=value)
def session(identity, parent=None, spawns=0, finished=True, wrong=False):
    source = {"subagent": {"thread_spawn": {"parent_thread_id": parent}}} if parent else "cli"
    meta = {"id": identity, "session_id": thread, "thread_source": "subagent" if parent else "cli", "source": source, "cwd": str(repo), "cli_version": "0.163.0"}
    if warmup and "session_tools" in config:
        meta["tools"] = config["session_tools"]
    events = [{"type": "session_meta", "payload": meta}]
    if parent:
        events += [{"type": "session_meta", "payload": {"id": thread, "source": "cli"}}]
    events += [record("turn_context", model="gpt-0.0-other" if wrong else model, sandbox_policy={"type": "workspace-write"})]
    if not parent and mode != "no_slots":
        helpers = 3 if mode == "default_slots" else next((int(a.split("=", 1)[1]) for a in args
            if a.startswith("agents.max_concurrent_threads_per_session=")), 3)
        text = f"There are {helpers + 1} available concurrency slots, meaning that up to {helpers + 1} agents can be active at once, including you."
        events += [record("response_item", type="message", role="developer", content=[{"type": "input_text", "text": text}])]
    events += [call("exec", identity + "-exec", arguments="read README.md")]
    events += [call("exec", identity + "-exec", arguments="duplicate lifecycle record")]
    if parent:
        events += [call("exec", identity + "-outside", arguments="cat /root/round-fixture/notes.txt; ls " + str(state / "scratch-location"))]
        if (state / "scratch-location").is_file():
            events[-1]["payload"]["arguments"] = "cat /root/round-fixture/notes.txt; ls " + (state / "scratch-location").read_text()
        events += [call("send_message", identity + "-message", "collaboration",
                        arguments='{"target":"/root/agent-address","message":"done"}')]
    for i in range(spawns):
        key = identity + "-spawn-" + str(i)
        answer = config.get("spawn_output", "spawn failed" if mode == "failed_spawn" else '{"task_name":"helper"}')
        events += [call("spawn_agent", key, "collaboration", arguments='{"task_name":"helper"}'), output(key, answer)]
    if warmup:
        shell = shlex.split(prompt.split("Then reply")[0].split("command tool: ", 1)[1].rstrip(". "))[-1]
        # Source the fixture profile explicitly: host login profiles differ across test machines.
        profile = home / ".profile"
        shell_to_run = (". " + shlex.quote(str(profile)) + "; " if profile.exists() else "") + shell
        probe = subprocess.run(["bash", "-lc", shell_to_run], env=dict(os.environ, HOME=str(home)), capture_output=True, text=True)
        events += [call("exec", "probe", arguments=shell), output("probe", probe.stdout)]
    if not warmup and mode == "mcp":
        events += [call("read", "mcp-call", "mcp__fixture", arguments="{}")]
    if not warmup and mode == "web_search":
        events += [record("response_item", type="web_search_call", action={"type": "search", "query": "fixture"})]
    usage = {"input_tokens": 100, "cached_input_tokens": 60, "cache_write_input_tokens": 10, "output_tokens": 20, "reasoning_output_tokens": 8}
    if mode == "absent_tokens":
        usage.pop("cache_write_input_tokens")
    events += [record("event_msg", type="token_count", info={"total_token_usage": usage})]
    if finished:
        events += [record("event_msg", type="turn_aborted" if parent and mode == "aborted" else "task_complete")]
    path = root / ("rollout-2026-10-21T00-00-00-" + identity + ".jsonl")
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path
print(json.dumps({"type": "thread.started", "thread_id": thread}), flush=True)
if warmup:
    tools = config.get("answer_tools", {tools})
    text = json.dumps({"tools": tools})
    if config.get("fenced"):
        text = config.get("prose", "Tool list:") + "\n```json\n" + text + "\n```"
    if mode == "agents":
        text += (repo / "AGENTS.md").read_text().split()[1]
    session(thread, wrong=mode == "model")
    if mode == "error":
        print(json.dumps({"type": "turn.failed", "error": {"message": "fixture model refusal"}}))
else:
    with (state / "audit-times.jsonl").open("a") as out:
        out.write(json.dumps({"kind": "start", "at": time.monotonic(), "repo": str(repo)}) + "\n")
    time.sleep(config.get("audit_delay", 0))
    helpers = mode in ("helpers", "missing", "unfinished", "wrong_helper", "aborted", "unrecognized_spawn")
    session(thread, spawns=1 if helpers or mode == "failed_spawn" else 0)
    if helpers and mode != "missing":
        child = str(uuid.uuid4())
        session(child, thread, spawns=1, wrong=mode == "wrong_helper")
        session(str(uuid.uuid4()), child, finished=mode != "unfinished")
        session(str(uuid.uuid4()), wrong=True)  # same cwd and time, without lineage
    if mode in ("login", "quota", "transient", "error", "recovered", "trailing_error"):
        message = {"login": "unexpected status 401", "quota": "You've hit your usage limit. Upgrade to Plus",
                   "transient": "unexpected status 429", "error": "fixture error",
                   "recovered": "Reconnecting 1/5", "trailing_error": "late error"}[mode]
        if mode != "trailing_error":
            print(json.dumps({"type": "error", "message": message}))
        if mode in ("login", "quota", "transient", "error"):
            print(json.dumps({"type": "turn.failed", "error": {"message": message}}))
    if mode == "file_change":
        print(json.dumps({"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "README.md", "kind": "update"}]}}))
    if mode == "changed":
        (repo / "README.md").write_text("changed\n")
    text = "## Findings\n| ID | Status | Priority | Evidence | Improvement |\n| --- | --- | --- | --- | --- |\n| REPO-01 | partial | low | `README.md:1` | Say more |\n"
    with (state / "audit-times.jsonl").open("a") as out:
        out.write(json.dumps({"kind": "end", "at": time.monotonic(), "repo": str(repo)}) + "\n")
if mode != "no_report":
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "draft"}}))
if mode != "no_report":
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}}))
last.write_text("different" if mode == "report_mismatch" else text)
if mode != "no_turn":
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100}}))
if mode == "trailing_error":
    print(json.dumps({"type": "error", "message": message}))
raise SystemExit(3 if mode == "nonzero" else 0)
'''


class CodexTests(unittest.TestCase):
    skill_history = shared.RoundTests.skill_history
    plan = shared.RoundTests.plan
    tearDown = shared.RoundTests.tearDown

    def setUp(self):
        shared.RoundTests.setUp(self)
        self.home = self.root / "home"
        self.home.mkdir()
        self.state = self.home / "fake-state"
        self.state.mkdir()
        self.configure()
        fake = self.root / "bin" / "codex"
        fake.write_text(FAKE_CODEX.replace("{python}", sys.executable).replace("{tools}", repr(sorted(codex.EXPECTED_TOOLS))))
        fake.chmod(0o755)
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.sessions = mock.patch.object(codex, "SESSIONS", self.home / "sessions")
        self.sessions.start()
        self.addCleanup(self.sessions.stop)
        self.wait = mock.patch.object(codex, "SESSION_WAIT", 0.15)
        self.wait.start()
        self.addCleanup(self.wait.stop)

    def configure(self, **config):
        (self.state / "config.json").write_text(json.dumps(config))

    def codex_plan(self, *numbers):
        return self.plan("round" + str(len(self.rounds)), *[(str(n), "codex:gpt-6.1-sol") for n in numbers or (1,)])

    def run_round(self, round_dir, jobs=4, budget=100):
        with mock.patch("builtins.print"):
            return runner.run(round_dir, jobs, timeout=10, budget=budget, pause=(0, 0))

    def data(self, round_dir):
        return json.loads((round_dir / "plan.json").read_text())

    def record(self, round_dir, number=1):
        return runner.read_record(round_dir, self.data(round_dir)["jobs"][number - 1])

    def audit_calls(self):
        path = self.state / "audit-times.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_a_codex_job_runs_with_stdin_closed_and_the_fixed_flags(self):
        self.env.stop()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "OPENAI_API_KEY": "fake",
            "CODEX_HOME": "fake", "CODEX_API_KEY": "fake", "ANTHROPIC_AUTH_TOKEN": "fake"})
        self.env.start()
        round_dir = self.codex_plan()
        saved = os.dup(0)
        read_fd, write_fd = os.pipe()
        try:
            os.dup2(read_fd, 0)
            self.assertEqual(self.run_round(round_dir), 0)
        finally:
            os.dup2(saved, 0)
            for fd in (saved, read_fd, write_fd):
                os.close(fd)
        events = codex.records(self.state / "calls.jsonl")
        self.assertEqual([e["args"][:2] for e in events[:2]], [["login", "status"], ["--version"]])
        for e in events:
            self.assertEqual(e["stdin_target"], "/dev/null")
            self.assertFalse(any(codex.forbidden_name(n) for n in e["environment_names"]))
        args = events[-1]["args"]
        for feature in codex.FEATURES:
            self.assertIn(["--disable", feature], [args[i:i+2] for i in range(len(args))])
        for value in ('model_reasoning_effort="high"', "project_doc_max_bytes=0", "check_for_update_on_startup=false",
                      'web_search="disabled"', "agents.max_concurrent_threads_per_session=8", "workspace-write"):
            self.assertIn(value, args)
        self.assertNotIn("--ephemeral", args)
        self.assertEqual(args[args.index("-m") + 1], "gpt-6.1-sol")
        self.assertEqual(self.record(round_dir)["status"], "valid")

    def test_codex_audits_run_one_at_a_time_whatever_the_jobs(self):
        self.configure(audit_delay=0.12)
        round_dir = self.codex_plan(1, 2, 3)
        self.assertEqual(self.run_round(round_dir, jobs=8), 0)
        events = self.audit_calls()
        self.assertEqual([e["kind"] for e in events], ["start", "end"] * 3)

    def test_a_waiting_codex_job_rechecks_the_stop_and_the_budget(self):
        for gate in ("stop", "budget", "codex_stop"):
            with self.subTest(gate=gate):
                round_dir = self.codex_plan(1, 2)
                data = self.data(round_dir)
                entered = threading.Event()
                class WaitingSemaphore(threading.Semaphore):
                    def acquire(self, *args, **kwargs):
                        entered.set()
                        return super().acquire(*args, **kwargs)
                    __enter__ = acquire
                launch = {"codex_turn": WaitingSemaphore(1), "running": runner.Running(),
                    "spending": runner.Spending(1), "codex_stop": threading.Event(), "codex_stop_reason": "login",
                    "providers": {}, "starts": runner.StartSpacer(0), "timeout": 3}
                launch["codex_turn"].acquire()
                entered.clear()
                with ThreadPoolExecutor(1) as pool:
                    waiting = pool.submit(runner.audit, round_dir, data, data["jobs"][1], launch)
                    self.assertTrue(entered.wait(2))
                    if gate == "stop":
                        launch["running"].stopped.set()
                    elif gate == "budget":
                        launch["spending"].add(1)
                    else:
                        launch["codex_stop"].set()
                    launch["codex_turn"].release()
                    line = waiting.result(timeout=3)
                self.assertIn("skipped", line)
                self.assertEqual(self.record(round_dir, 2)["status"], "skipped")
                self.assertEqual(self.audit_calls(), [])

    def check_stop_class(self, mode, reason):
        self.configure(mode=mode)
        round_dir = self.codex_plan(1, 2, 3)
        self.assertEqual(self.run_round(round_dir), 1)
        self.assertEqual(len(self.audit_calls()), 2)
        statuses = [runner.read_record(round_dir, j) for j in self.data(round_dir)["jobs"]]
        self.assertEqual(sum(r["status"] == "invalid" for r in statuses), 1)
        self.assertEqual(sum(r["status"] == "skipped" for r in statuses), 2)
        self.assertTrue(all(reason in r["reasons"] for r in statuses))

    def test_a_login_error_stops_further_codex_launches_without_retrying(self):
        self.check_stop_class("login", "login")

    def test_a_usage_limit_error_stops_further_codex_launches_without_retrying(self):
        self.check_stop_class("quota", "usage limit")

    def test_usage_limit_words_do_not_require_a_status(self):
        for text in ("quota exceeded", "You've hit your usage limit. Upgrade to Plus",
                     "Visit https://chatgpt.com/settings/usage", "usage_limit exhausted"):
            for status in (None, 400, 401, 429, 500):
                with self.subTest(text=text, status=status):
                    self.assertEqual(codex.error_class({"type": "error", "message": text, "status_code": status}), "usage limit")

    def test_usage_exhaustion_does_not_match_retry_or_resource_exhaustion(self):
        self.assertEqual(codex.error_class({"message": "Your usage is exhausted"}), "usage limit")
        for text in ("request_retry_exhausted", "realtime sideband websocket retry loop exhausted",
                     "Some resource has been exhausted"):
            with self.subTest(text=text):
                self.assertEqual(codex.error_class({"message": text}), "error")

    def test_out_of_credits_is_a_usage_limit(self):
        self.assertEqual(codex.error_class({"message": "Your workspace is out of credits. Add credits to continue."}), "usage limit")

    def test_spend_cap_is_a_usage_limit(self):
        self.assertEqual(codex.error_class({"message": "You hit your spend cap set in your workspace."}), "usage limit")

    def test_credit_limit_is_a_usage_limit(self):
        self.assertEqual(codex.error_class({"message": "Your workspace reached its credit limit."}), "usage limit")

    def test_sign_in_again_is_a_login_error(self):
        self.assertEqual(codex.error_class({"message": "Please sign in again."}), "login")

    def test_a_token_that_could_not_be_refreshed_is_a_login_error(self):
        self.assertEqual(codex.error_class({"message": "Your authentication session could not be refreshed automatically."}), "login")

    def test_a_transient_429_invalidates_only_its_run(self):
        self.configure(mode="transient")
        round_dir = self.codex_plan(1, 2)
        self.assertEqual(self.run_round(round_dir), 1)
        self.assertEqual(len(self.audit_calls()), 4)
        self.assertTrue(all(runner.read_record(round_dir, j)["reasons"] == ["transient"] for j in self.data(round_dir)["jobs"]))

    def test_the_warm_up_stops_the_round_when_agents_md_loads(self):
        self.configure(warmup="agents")
        round_dir = self.codex_plan()
        with self.assertRaisesRegex(SystemExit, "AGENTS.md loaded"):
            self.run_round(round_dir)
        self.assertEqual(self.audit_calls(), [])
        self.assertEqual(self.record(round_dir)["reasons"], ["preflight failed"])

    def test_the_warm_up_reads_the_tool_list_from_the_session_file_else_the_answer_and_stops_on_a_difference(self):
        for config, passes in (({"session_tools": sorted(codex.EXPECTED_TOOLS), "answer_tools": []}, True),
                               ({"session_tools": []}, False), ({"answer_tools": ["exec"]}, False), ({}, True)):
            with self.subTest(config=config):
                self.configure(**config)
                round_dir = self.codex_plan()
                if passes:
                    self.assertEqual(self.run_round(round_dir), 0)
                else:
                    with self.assertRaisesRegex(SystemExit, "unexpected tools"):
                        self.run_round(round_dir)

    def test_the_warm_up_stops_the_round_unless_the_instructions_state_the_helper_slots(self):
        for mode, stated in (("default_slots", r"\[4\]"), ("no_slots", r"\[\]")):
            with self.subTest(mode=mode):
                self.configure(warmup=mode)
                round_dir = self.codex_plan()
                with self.assertRaisesRegex(SystemExit, rf"helper slots: instructions state {stated}, expected \[9\]"):
                    self.run_round(round_dir)
                self.assertEqual(self.audit_calls(), [])

    def test_the_warm_up_stops_the_round_when_a_profile_restores_a_token(self):
        (self.home / ".profile").write_text("export OPENAI_API_KEY=fake-profile-token\n")
        round_dir = self.codex_plan()
        with self.assertRaisesRegex(SystemExit, "shell environment probe failed"):
            self.run_round(round_dir)
        self.assertEqual(self.audit_calls(), [])
        self.assertNotIn("fake-profile-token", (round_dir / "warmup-codex-gpt-6.1-sol.jsonl").read_text())

    def test_helpers_are_found_by_recursive_lineage_and_unrelated_sessions_ignored(self):
        self.configure(mode="helpers")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 0)
        record = self.record(round_dir)
        manifest = json.loads((round_dir / "streams/run1-case.sessions/manifest.json").read_text())
        self.assertEqual(len(manifest), 3)
        self.assertEqual(sum(e["parent"] is None for e in manifest), 1)
        self.assertEqual(record["usage"]["tokens_in"], 300)
        self.assertEqual(record["usage"]["tokens_out"], 60)
        self.assertEqual(record["usage"]["tokens_uncached"], 120)
        self.assertEqual(record["usage"]["tokens_reasoning"], 24)
        self.assertEqual(record["usage"]["tools"], 9)

    def test_a_missing_or_unfinished_helper_leaves_accounting_incomplete_not_zero(self):
        for mode in ("missing", "unfinished"):
            with self.subTest(mode=mode):
                self.configure(mode=mode)
                round_dir = self.codex_plan()
                self.assertEqual(self.run_round(round_dir), 1)
                record = self.record(round_dir)
                self.assertIn("incomplete accounting", record["reasons"])
                self.assertIsNone(record["usage"]["tokens_in"])
                self.assertIsNone(record["usage"]["tools"])
                self.assertGreaterEqual(record["usage_lower_bound"]["tokens_in"], 100)
                self.assertGreaterEqual(record["usage_lower_bound"]["tools"], 2)
                summary = runner.summarize(round_dir)
                self.assertIn("lower bound:", summary)
                self.assertIn("input", summary)
                self.assertIn("Mean uncached input", summary)

    def test_a_helper_with_another_model_is_flagged(self):
        self.configure(mode="wrong_helper")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 1)
        self.assertIn("model mismatch", self.record(round_dir)["reasons"])

    def test_late_helper_files_are_awaited_and_the_manifest_hashes_the_copies(self):
        self.configure(mode="helpers")
        round_dir = self.codex_plan()
        original = codex.session_candidates
        hidden = set()
        first = True
        def delayed(started, ended):
            nonlocal first
            paths = original(started, ended)
            if len(paths) > 1 and first:
                first = False
                hidden.update(p.name for p in paths if codex.session_info(p)["parent"])
                return [p for p in paths if p.name not in hidden]
            return paths
        with mock.patch.object(codex, "session_candidates", side_effect=delayed), mock.patch.object(codex, "SESSION_POLL", 0.01):
            self.assertEqual(self.run_round(round_dir), 0)
        self.assertTrue(hidden)
        directory = round_dir / "streams/run1-case.sessions"
        self.assertEqual(self.record(round_dir)["manifest_sha256"], codex.digest(directory / "manifest.json"))
        for item in json.loads((directory / "manifest.json").read_text()):
            self.assertEqual(item["sha256"], codex.digest(directory / item["file"]))
            self.assertTrue(item["finished"])

    def test_tool_calls_count_once_per_call_id_across_threads(self):
        events = [{"type": "response_item", "payload": {"type": "function_call", "name": "exec", "call_id": "one"}}] * 2
        threads = {"main": {"events": events}, "helper": {"events": events}}
        self.assertEqual(codex.session_usage(threads, True)["tools"], 1)

    def test_absent_token_fields_are_unavailable_not_zero(self):
        self.configure(mode="absent_tokens")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertIsNone(self.record(round_dir)["usage"]["tokens_written"])
        summary = runner.summarize(round_dir)
        self.assertIn("Mean uncached input", summary)
        self.assertIn("Mean reasoning tokens", summary)
        self.assertIn("| — | 60 (1 of 1) | 20 (1 of 1) |", summary)
        self.assertIn("| — | 1 (1 of 1) |", summary)  # no USD

    def test_unknown_metric_means_show_how_many_runs_supply_the_field(self):
        round_dir = self.codex_plan(1, 2)
        original = codex.run_audit
        def change_after_first(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[1].name == "run1-case.jsonl":
                self.configure(mode="absent_tokens")
            return result
        with mock.patch.object(codex, "run_audit", side_effect=change_after_first):
            self.assertEqual(self.run_round(round_dir, jobs=1), 0)
        summary = runner.summarize(round_dir)
        self.assertIn("| 10 (1 of 2) | 60 (2 of 2) | 20 (2 of 2) |", summary)

    def test_duration_excludes_the_wait_for_the_codex_turn(self):
        self.configure(audit_delay=0.18)
        round_dir = self.codex_plan(1, 2, 3)
        self.assertEqual(self.run_round(round_dir), 0)
        records = [runner.read_record(round_dir, j) for j in self.data(round_dir)["jobs"]]
        queued = max(records, key=lambda r: r["queue_seconds"])
        self.assertGreater(queued["queue_seconds"], 0.3)
        self.assertGreater(queued["seconds"], 0.15)
        self.assertLess(queued["seconds"], queued["queue_seconds"])

    def test_the_report_is_the_main_threads_last_message_and_a_different_o_file_invalidates_it(self):
        self.configure(mode="report_mismatch")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 1)
        self.assertIn("report mismatch", self.record(round_dir)["reasons"])
        self.assertTrue((round_dir / "reports/run1-case.md").read_text().startswith("## Findings"))

    def test_a_codex_job_is_skipped_on_resume_only_when_its_record_matches_and_is_valid(self):
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertEqual(len(self.audit_calls()), 2)
        job = self.data(round_dir)["jobs"][0]
        path = runner.record_path(round_dir, job)
        for key, value in (("backend", "claude"), ("model", "gpt-0.0-other"), ("revision", "other"),
                           ("case", "other"), ("prompt_sha256", "wrong"), ("status", "invalid")):
            with self.subTest(field=key):
                baseline = self.record(round_dir)
                path.write_text(json.dumps(baseline | {key: value}))
                before = len(self.audit_calls())
                self.assertEqual(self.run_round(round_dir), 0)
                self.assertEqual(len(self.audit_calls()) - before, 2)
        path.unlink()
        before = len(self.audit_calls())
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertEqual(len(self.audit_calls()) - before, 2)
        self.assertEqual(self.record(round_dir)["status"], "valid")
        self.assertFalse(runner.legacy_job(round_dir, job))

    def test_a_changed_plan_invalidates_valid_records_before_launch_gates(self):
        round_dir = self.plan("changed-plan", ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
        self.assertEqual(self.run_round(round_dir), 0)
        jobs = self.data(round_dir)["jobs"]
        originals = [runner.read_record(round_dir, job) for job in jobs]
        for field in ("backend", "model", "revision", "case", "prompt_sha256"):
            with self.subTest(field=field):
                for job, record in zip(jobs, originals):
                    runner.record_path(round_dir, job).write_text(json.dumps(record | {field: "changed"}))
                self.assertEqual(self.run_round(round_dir, budget=0), 1)
                for job, original in zip(jobs, originals):
                    record = runner.read_record(round_dir, job)
                    self.assertEqual(record["status"], "invalid")
                    self.assertEqual(record["reasons"], ["plan changed after the run"])
                    for key in ("started", "ended", "seconds", "usage", "report_sha256", "manifest_sha256"):
                        self.assertEqual(record.get(key), original.get(key))
                summary = runner.summarize(round_dir)
                self.assertEqual(summary.count("invalid: plan changed after the run"), 2)
                self.assertIn("| Test 1.0 | 0 of 1 |", summary)
                self.assertIn("| Codex gpt-6.1-sol | 0 of 1 |", summary)

    def test_a_relaunch_records_its_start_before_deleting_the_old_report(self):
        class Crash(BaseException):
            pass
        for backend in ("claude-test-1-0", "codex:gpt-6.1-sol"):
            for stale in ("identity", "status"):
                with self.subTest(backend=backend, stale=stale):
                    round_dir = self.plan("crash-" + backend + stale, ("1", backend))
                    self.assertEqual(self.run_round(round_dir), 0)
                    job = self.data(round_dir)["jobs"][0]
                    record = runner.read_record(round_dir, job)
                    change = {"prompt_sha256": "changed"} if stale == "identity" else {"status": "invalid"}
                    runner.record_path(round_dir, job).write_text(json.dumps(record | change))
                    report = round_dir / "reports/run1-case.md"
                    original_command, original_unlink = runner.run_command, Path.unlink
                    deleted = []
                    def unlink(path, *args, **kwargs):
                        if path == report:
                            current = runner.read_record(round_dir, job)
                            self.assertEqual(current["status"], "invalid")
                            self.assertEqual(current["reasons"], ["relaunch started"])
                            deleted.append(path)
                        return original_unlink(path, *args, **kwargs)
                    def crash(command, cwd, *args, **kwargs):
                        if cwd == Path(job["dir"]) / job["name"]:
                            raise Crash()
                        return original_command(command, cwd, *args, **kwargs)
                    with mock.patch.object(runner, "run_command", side_effect=crash), mock.patch.object(Path, "unlink", unlink):
                        with self.assertRaises(Crash):
                            self.run_round(round_dir)
                    self.assertEqual(deleted, [report])
                    self.assertFalse(report.exists())
                    current = runner.read_record(round_dir, job)
                    self.assertEqual(current["reasons"], ["relaunch started"])
                    self.assertEqual(current["usage"], record["usage"])
                    self.assertEqual(self.run_round(round_dir), 0)
                    self.assertEqual(self.record(round_dir)["status"], "valid")

    def test_a_signal_in_future_result_stops_the_round_without_a_runner_error(self):
        for number in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=number):
                round_dir = self.plan("future-signal-" + str(number), ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
                original_result, original_stop = Future.result, runner.Running.stop
                fired, stopped = [], []
                def result(future, *args, **kwargs):
                    value = original_result(future, *args, **kwargs)
                    if not fired:
                        fired.append(number)
                        signal.raise_signal(number)
                    return value
                def stop(running):
                    stopped.append(running)
                    return original_stop(running)
                previous = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
                with mock.patch.object(Future, "result", result), mock.patch.object(runner.Running, "stop", stop):
                    self.assertEqual(self.run_round(round_dir), 128 + number)
                self.assertEqual(fired, [number])
                self.assertTrue(stopped)
                self.assertEqual({n: signal.getsignal(n) for n in previous}, previous)
                for job in self.data(round_dir)["jobs"]:
                    self.assertNotIn("runner error: Interrupted", runner.read_record(round_dir, job)["reasons"])
                self.assertIn("by " + signal.Signals(number).name, (round_dir / "log.txt").read_text())

    def test_a_signal_during_codex_warm_up_is_not_a_runner_error(self):
        round_dir = self.codex_plan()
        original = runner.run_command
        interrupted = []
        def command(args, cwd, *positional, **kwargs):
            if args[:1] == ["codex"] and "exec" in args:
                interrupted.append(True)
                signal.raise_signal(signal.SIGTERM)
            return original(args, cwd, *positional, **kwargs)
        with mock.patch.object(runner, "run_command", side_effect=command):
            self.assertEqual(self.run_round(round_dir), 128 + signal.SIGTERM)
        self.assertTrue(interrupted)
        self.assertEqual(self.record(round_dir)["reasons"], ["stopped"])
        self.assertEqual(self.audit_calls(), [])

    def test_an_outer_future_error_is_invalid_for_both_backends(self):
        round_dir = self.plan("future-error", ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
        with mock.patch.object(runner, "audit_ready", side_effect=KeyError("fixture")):
            self.assertEqual(self.run_round(round_dir), 1)
        for job in self.data(round_dir)["jobs"]:
            record = runner.read_record(round_dir, job)
            self.assertEqual(record["status"], "invalid")
            self.assertEqual(record["reasons"], ["runner error: KeyError"])
        self.assertEqual(runner.summarize(round_dir).count("invalid: runner error: KeyError"), 2)

    def test_an_idle_run_adds_no_start_or_end_to_the_log(self):
        round_dir = self.plan("idle", ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
        self.assertEqual(self.run_round(round_dir), 0)
        path = round_dir / "log.txt"
        before = path.read_text().splitlines()
        with mock.patch.object(runner, "run_command") as command:
            self.assertEqual(self.run_round(round_dir), 0)
        command.assert_not_called()
        after = path.read_text().splitlines()
        for prefix in ("start ", "end "):
            self.assertEqual([line for line in after if line.startswith(prefix)],
                             [line for line in before if line.startswith(prefix)])

    def test_an_unknown_backend_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "unknown backend"):
            runner.parse_runs(["1=other:gpt-6.1-sol"])
        with self.assertRaisesRegex(SystemExit, "unknown backend"):
            self.plan("bad", ("1", "other:gpt-6.1-sol"))
        for alias in ("codex", "gpt", "gpt-6", "../model"):
            with self.subTest(alias=alias), self.assertRaisesRegex(SystemExit, "full model ID"):
                runner.parse_runs(["1=codex:" + alias])
        self.assertEqual(runner.parse_runs(["300=codex:gpt-6.1-sol@HEAD+catalog"]),
                         [("300", "gpt-6.1-sol", "HEAD", "catalog", "codex")])

    def test_model_ids_with_colons_remain_refused(self):
        for spec in ("1=claude:model:tag", "1=codex:gpt-6.1-sol:tag", "1=private:model"):
            with self.subTest(spec=spec), self.assertRaises(SystemExit):
                runner.parse_runs([spec])

    def test_invalid_codex_reports_credit_no_model_findings(self):
        self.configure(mode="wrong_helper")
        round_dir = self.codex_plan(1, 2)
        self.assertEqual(self.run_round(round_dir), 1)
        summary = runner.summarize(round_dir)
        row = next(line for line in summary.splitlines() if line.startswith("| Codex gpt-6.1-sol |"))
        self.assertTrue(row.startswith("| Codex gpt-6.1-sol | 0 of 2 | 0 of 2 |"))
        self.assertTrue(row.endswith("| 0 of 2 |"))

    def test_a_codex_only_round_runs_no_claude_command(self):
        (self.root / "bin/claude").write_text("#!/bin/sh\nexit 99\n")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertFalse((round_dir / "cli-version.txt").exists())
        self.assertIn("0.163.0", (round_dir / "codex-cli-version.txt").read_text())

    def test_a_mixed_round_needs_the_claude_and_codex_locks(self):
        round_dir = self.plan("mixed", ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
        self.assertEqual(runner.round_resources(self.data(round_dir)["jobs"], {}), ("anthropic", "codex"))
        with runner.round_lock("busy", resources=("codex",)), self.assertRaisesRegex(SystemExit, "another round"):
            self.run_round(round_dir)
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertTrue(shared.free(runner.lock_path("codex")))
        summary = runner.summarize(round_dir)
        self.assertIn("Codex gpt-6.1-sol", summary)
        self.assertIn("| Test 1.0 |", summary)

    def test_runs_without_a_backend_stay_claude(self):
        round_dir = self.plan("legacy", ("1", "claude-test-1-0"))
        data = self.data(round_dir)
        data["jobs"][0].pop("backend")
        (round_dir / "plan.json").write_text(json.dumps(data))
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertEqual(self.record(round_dir)["backend"], "claude")
        self.assertFalse((self.state / "calls.jsonl").exists())

    def test_outside_paths_and_leftovers_read_every_threads_session_file(self):
        self.configure(mode="helpers")
        round_dir = self.codex_plan()
        scratch = Path(tempfile.mkdtemp(prefix="codex-scratch."))
        self.addCleanup(lambda: scratch.rmdir())
        (self.state / "scratch-location").write_text(str(scratch))
        self.assertEqual(self.run_round(round_dir), 0)
        stream = round_dir / "streams/run1-case.jsonl"
        self.assertIn("/root/round-fixture/notes.txt", runner.outside_paths(stream, []))
        self.assertFalse(any("agent-address" in path for path in runner.outside_paths(stream, [])))
        summary = runner.summarize(round_dir)
        self.assertIn("left in the temporary directory: " + scratch.name, summary)
        self.assertIn("/root/round-fixture/notes.txt", summary)

    def test_codex_stream_errors_and_changes_are_invalid(self):
        for mode, reason in (("nonzero", "nonzero exit 3"), ("no_report", "no report"), ("no_turn", "no turn.completed"),
                             ("file_change", "repository file_change"), ("changed", "changed repository"),
                             ("mcp", "web_search or MCP call"), ("web_search", "web_search or MCP call"), ("error", "error")):
            with self.subTest(mode=mode):
                self.configure(mode=mode)
                round_dir = self.codex_plan()
                self.assertEqual(self.run_round(round_dir), 1)
                self.assertIn(reason, self.record(round_dir)["reasons"])

    def test_failed_codex_preflights_leave_statuses_without_launching_audits(self):
        for mode, message in (("model", "model mismatch"), ("no_turn", "no turn.completed"),
                              ("no_report", "no report"), ("error", "error")):
            with self.subTest(mode=mode):
                self.configure(warmup=mode)
                round_dir = self.codex_plan(1, 2)
                with self.assertRaisesRegex(SystemExit, message):
                    self.run_round(round_dir)
                self.assertEqual(self.audit_calls(), [])
                self.assertTrue(all(runner.read_record(round_dir, j)["status"] == "skipped"
                                    for j in self.data(round_dir)["jobs"]))
        self.configure(login_exit=1)
        with self.assertRaisesRegex(SystemExit, "not logged in"):
            self.run_round(self.codex_plan())
        self.assertEqual(self.audit_calls(), [])

    def test_a_partial_final_session_record_leaves_accounting_incomplete(self):
        identity = str(uuid.uuid4())
        path = self.root / f"rollout-{identity}.jsonl"
        path.write_text(json.dumps({"type": "event_msg", "payload": {"type": "task_complete"}}) + "\n{partial")
        self.assertFalse(codex.session_info(path)["finished"])

    def test_a_codex_timeout_keeps_an_invalid_status_and_missing_accounting(self):
        self.configure(audit_delay=1)
        round_dir = self.codex_plan()
        with mock.patch("builtins.print"):
            self.assertEqual(runner.run(round_dir, 1, timeout=0.15, budget=100), 1)
        record = self.record(round_dir)
        self.assertIn("timeout", record["reasons"])
        self.assertIn("incomplete accounting", record["reasons"])
        self.assertIsNone(record["usage"]["tokens_in"])

    def test_wrapped_probe_output_still_exposes_forbidden_names(self):
        wrapped = json.dumps({"content": [{"type": "text", "text": "OPENAI_API_KEY\nROUND_GH_CONFIG_OK\n"}]})
        self.assertIn("OPENAI_API_KEY", codex.output_text(wrapped).splitlines())

    def test_duplicate_artifact_labels_are_refused(self):
        with self.assertRaisesRegex(SystemExit, "duplicate"):
            self.plan("duplicate", ("1", "codex:gpt-6.1-sol"), ("1", "claude-test-1-0"))

    def test_session_search_includes_each_utc_date(self):
        started = datetime(2026, 10, 21, 23, 59, tzinfo=timezone.utc)
        for day in ("2026/10/21", "2026/10/22"):
            directory = codex.SESSIONS / day
            directory.mkdir(parents=True)
            (directory / "rollout-fixture.jsonl").write_text("")
        self.assertEqual(len(codex.session_candidates(started, started + timedelta(minutes=2))), 2)

    def test_a_fenced_warm_up_tool_list_is_accepted(self):
        self.configure(fenced=True)
        self.assertEqual(self.run_round(self.codex_plan()), 0)

    def test_a_bracketed_count_before_the_warm_up_tools_object_is_ignored(self):
        self.configure(fenced=True, prose="Here are the [12] tools:")
        self.assertEqual(self.run_round(self.codex_plan()), 0)
        tools = sorted(codex.EXPECTED_TOOLS)
        self.assertEqual(codex.first_json_value('A count [12], {"note": "ignore"}, then ' + json.dumps({"tools": tools})), {"tools": tools})
        warmup = next(e["args"][-1] for e in codex.records(self.state / "calls.jsonl") if e["args"][0] == "exec")
        self.assertIn('exactly one JSON object {"tools": [...]}', warmup)

    def test_run_after_clean_keeps_every_record_and_launches_no_backend(self):
        round_dir = self.plan("cleaned-mixed", ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
        self.assertEqual(self.run_round(round_dir), 0)
        streams = round_dir / "streams"
        before = {p.name: p.read_bytes() for p in streams.glob("*.run*.json")}
        runner.clean(round_dir)
        with mock.patch.object(runner, "run_command") as command:
            self.assertEqual(self.run_round(round_dir), 0)
            for job in self.data(round_dir)["jobs"]:
                self.assertIn("prepared repository removed", runner.audit(round_dir, self.data(round_dir), job, {}))
        command.assert_not_called()
        self.assertEqual(before, {p.name: p.read_bytes() for p in streams.glob("*.run*.json")})
        self.assertEqual((round_dir / "log.txt").read_text().count("prepared repository removed; record unchanged"), 2)
        summary = runner.summarize(round_dir)
        self.assertIn("| Codex gpt-6.1-sol | 1 of 1 |", summary)
        self.assertIn("| Test 1.0 | 1 of 1 |", summary)

    def test_preflight_and_budget_skips_preserve_real_attempts_and_their_usage(self):
        self.configure(mode="error")
        round_dir = self.codex_plan(1, 2)
        self.assertEqual(self.run_round(round_dir), 1)
        streams = round_dir / "streams"
        self.assertEqual(list(streams.glob("*.run.*.json")), [])
        self.assertEqual(self.run_round(round_dir), 1)
        # Each relaunch archives the failed attempt and its "relaunch started" record.
        self.assertEqual(len(list(streams.glob("*.run.*.json"))), 4)
        before = {p.name: p.read_bytes() for p in streams.glob("*.run*.json")}
        self.configure(login_exit=1)
        with self.assertRaisesRegex(SystemExit, "not logged in"):
            self.run_round(round_dir)
        self.assertEqual(before, {p.name: p.read_bytes() for p in streams.glob("*.run*.json")})
        self.configure()
        self.assertEqual(self.run_round(round_dir, budget=0), 1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in streams.glob("*.run*.json")})
        self.assertIn("100 input", runner.summarize(round_dir))

    def test_a_missing_repository_is_excluded_while_other_jobs_are_pending(self):
        round_dir = self.plan("one-missing", ("1", "codex:gpt-6.1-sol"), ("2", "claude-test-1-0"))
        data = self.data(round_dir)
        missing, pending = data["jobs"]
        runner.write_record(round_dir, data, missing, ["original failure"], usage={"tokens_in": 100})
        path = runner.record_path(round_dir, missing)
        before = path.read_bytes()
        shutil.rmtree(Path(missing["dir"]) / missing["name"])
        self.assertEqual(self.run_round(round_dir), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(path.parent.glob("run1-case.run.*.json")))
        self.assertFalse((self.state / "calls.jsonl").exists())
        self.assertEqual(runner.read_record(round_dir, pending)["status"], "valid")

    def test_a_codex_runner_error_after_launch_keeps_times_and_usage(self):
        round_dir = self.codex_plan()
        original = codex.inspect_run
        def broken(stream, last_message, model, evidence, repo):
            if repo.name.startswith("codex-probe."):
                return original(stream, last_message, model, evidence, repo)
            raise KeyError("fixture")
        with mock.patch.object(codex, "inspect_run", side_effect=broken):
            self.assertEqual(self.run_round(round_dir), 1)
        record = self.record(round_dir)
        self.assertEqual(record["status"], "invalid")
        self.assertEqual(record["reasons"], ["runner error: KeyError"])
        self.assertIsNotNone(record["started"])
        self.assertIsNotNone(record["ended"])
        self.assertGreater(record["seconds"], 0)
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["usage"]["tokens_in"], 100)
        self.assertIn("100 input", runner.summarize(round_dir))

    def test_a_session_collection_error_keeps_copied_usage_as_a_lower_bound(self):
        round_dir = self.codex_plan()
        original = codex.collect_sessions
        def broken(thread, started, ended, destination, running):
            evidence = original(thread, started, ended, destination, running)
            if destination.name == "run1-case.sessions":
                raise ValueError("fixture")
            return evidence
        with mock.patch.object(codex, "collect_sessions", side_effect=broken):
            self.assertEqual(self.run_round(round_dir), 1)
        record = self.record(round_dir)
        self.assertEqual(record["status"], "invalid")
        self.assertEqual(record["reasons"], ["runner error: ValueError"])
        self.assertIsNotNone(record["started"])
        self.assertGreater(record["seconds"], 0)
        self.assertIsNone(record["usage"]["tokens_in"])
        self.assertEqual(record["usage_lower_bound"]["tokens_in"], 100)

    def test_changed_artifacts_are_invalid_and_block_relaunch_until_the_record_is_deleted(self):
        for kind in ("claude-report", "codex-report", "session", "manifest", "missing-report", "missing-session"):
            with self.subTest(kind=kind):
                backend = "claude-test-1-0" if kind == "claude-report" else "codex:gpt-6.1-sol"
                round_dir = self.plan("edited-" + kind, ("1", backend))
                self.assertEqual(self.run_round(round_dir), 0)
                job = self.data(round_dir)["jobs"][0]
                baseline = self.record(round_dir)
                directory = round_dir / "streams/run1-case.sessions"
                artifact = (next(directory.glob("*.jsonl")) if kind in ("session", "missing-session")
                            else directory / "manifest.json" if kind == "manifest"
                            else round_dir / "reports/run1-case.md")
                if kind.startswith("missing-"):
                    artifact.unlink()
                else:
                    artifact.write_text(artifact.read_text() + "\nMaintainer note.\n")
                edited = artifact.read_bytes() if artifact.exists() else None
                records = {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                           for p in (round_dir / "streams").glob("*.run*.json")}
                summary = runner.summarize(round_dir)
                self.assertIn("invalid: artifacts changed after the run", summary)
                self.assertIn("| " + runner.arm_label(self.data(round_dir), job) + " | 0 of 1 |", summary)
                self.assertEqual(records, {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                                          for p in (round_dir / "streams").glob("*.run*.json")})
                with mock.patch.object(runner, "run_command") as command:
                    self.assertEqual(self.run_round(round_dir), 1)
                    self.assertEqual(self.run_round(round_dir), 1)
                    self.assertIn("artifacts changed after the run", runner.audit(round_dir, self.data(round_dir), job, {}))
                command.assert_not_called()
                record = self.record(round_dir)
                self.assertEqual(record["status"], "invalid")
                self.assertEqual(record["reasons"], ["artifacts changed after the run"])
                for key in ("started", "seconds", "usage", "report_sha256", "manifest_sha256"):
                    self.assertEqual(record.get(key), baseline.get(key))
                self.assertEqual(artifact.read_bytes() if artifact.exists() else None, edited)
                self.assertEqual(len(list((round_dir / "streams").glob("*.run.*.json"))), 1)
                self.assertIn(f"delete {runner.record_path(round_dir, job)} to run it again", (round_dir / "log.txt").read_text())
                runner.record_path(round_dir, job).unlink()
                self.assertEqual(self.run_round(round_dir), 0)
                self.assertEqual(self.record(round_dir)["status"], "valid")

    def test_preflight_runs_only_for_pending_models_and_backends(self):
        round_dir = self.plan("pending-mixed", ("1", "claude-test-1-0"),
                              ("2", "claude-other-1-0"), ("3", "codex:gpt-6.1-sol"))
        self.assertEqual(self.run_round(round_dir), 0)
        original = runner.run_command
        for index in (0, 2):
            with self.subTest(pending=index):
                job = self.data(round_dir)["jobs"][index]
                path = runner.record_path(round_dir, job)
                record = runner.read_record(round_dir, job)
                path.write_text(json.dumps(record | {"status": "invalid"}))
                commands = []
                def observed(command, *args, **kwargs):
                    commands.append(command)
                    return original(command, *args, **kwargs)
                with mock.patch.object(runner, "run_command", side_effect=observed):
                    self.assertEqual(self.run_round(round_dir), 0)
                self.assertTrue(commands)
                backend = job["backend"]
                self.assertTrue(all(c[0] == backend for c in commands))
                if backend == "claude":
                    self.assertIn(["claude", "auth", "status"], commands)
                    models = [c[c.index("--model") + 1] for c in commands if "--model" in c]
                    self.assertEqual(models, [job["model"], job["model"]])
                else:
                    self.assertIn(["codex", "login", "status"], commands)
        with mock.patch.object(runner, "run_command") as command:
            self.assertEqual(self.run_round(round_dir), 0)
        command.assert_not_called()

    def test_a_prefixed_warm_up_tool_list_is_accepted_as_a_set(self):
        tools = ["functions." + name for name in reversed(sorted(codex.EXPECTED_TOOLS))]
        self.configure(answer_tools=tools + tools[:1])
        self.assertEqual(self.run_round(self.codex_plan()), 0)

    def test_the_warm_up_accepts_nested_tools_and_refuses_web_search(self):
        listed = ["functions." + name for name in sorted(codex.EXPECTED_TOOLS)]
        for extra, passes in ((["tools.apply_patch", "tools.clock__curr_time", "functions.exec_command"], True),
                              (["web.run"], False), (["tools.browser_open"], False)):
            with self.subTest(extra=extra):
                self.configure(answer_tools=listed + extra)
                round_dir = self.codex_plan()
                if passes:
                    self.assertEqual(self.run_round(round_dir), 0)
                else:
                    with self.assertRaisesRegex(SystemExit, "unexpected tools"):
                        self.run_round(round_dir)

    def test_tool_list_errors_show_parsed_and_expected_lists(self):
        self.configure(answer_tools=["functions.exec"])
        with self.assertRaisesRegex(SystemExit, r"parsed \['exec'\], expected \["):
            self.run_round(self.codex_plan())

    def test_queued_codex_jobs_leave_the_claude_pool_available(self):
        round_dir = self.plan("mixed", ("1", "codex:gpt-6.1-sol"), ("2", "codex:gpt-6.1-sol"),
                              ("3", "codex:gpt-6.1-sol"), ("4", "claude-test-1-0"))
        codex_started, claude_started = threading.Event(), threading.Event()
        original_audit, original_command = codex.run_audit, runner.run_command
        def held_audit(repo, *args, **kwargs):
            if not repo.name.startswith("codex-probe."):
                codex_started.set()
                self.assertTrue(claude_started.wait(3), "Claude was blocked behind queued Codex jobs")
            return original_audit(repo, *args, **kwargs)
        def observed_command(command, *args, **kwargs):
            if command[0] == "claude" and "stream-json" in command:
                self.assertTrue(codex_started.wait(3))
                claude_started.set()
            return original_command(command, *args, **kwargs)
        with mock.patch.object(codex, "run_audit", side_effect=held_audit), mock.patch.object(runner, "run_command", side_effect=observed_command):
            self.assertEqual(self.run_round(round_dir, jobs=2), 0)
        self.assertTrue(claude_started.is_set())

    def test_a_stop_ends_the_session_wait_early(self):
        running = runner.Running()
        entered = threading.Event()
        original = codex.session_candidates
        def scan(*args):
            entered.set()
            return original(*args)
        with mock.patch.object(codex, "SESSION_WAIT", 4), mock.patch.object(codex, "SESSION_POLL", 4), mock.patch.object(codex, "session_candidates", side_effect=scan), ThreadPoolExecutor(1) as pool:
            future = pool.submit(codex.collect_sessions, str(uuid.uuid4()), datetime.now(timezone.utc),
                                 datetime.now(timezone.utc), self.root / "stopped-sessions", running)
            self.assertTrue(entered.wait(2))
            running.stopped.set()
            result = future.result(timeout=2)
        self.assertFalse(result["complete"])

    def test_an_aborted_helper_has_final_accounting_and_an_aborted_manifest_entry(self):
        self.configure(mode="aborted")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertEqual(self.record(round_dir)["usage"]["tokens_in"], 300)
        manifest = json.loads((round_dir / "streams/run1-case.sessions/manifest.json").read_text())
        self.assertEqual(sum(item["aborted"] for item in manifest), 2)

    def test_failed_spawns_are_notes_and_do_not_require_children(self):
        for answer in ("spawn failed", '{"error":"refused"}', '{"status":"unknown"}'):
            with self.subTest(answer=answer):
                self.configure(mode="failed_spawn", spawn_output=answer)
                round_dir = self.codex_plan()
                self.assertEqual(self.run_round(round_dir), 0)
                self.assertTrue(self.record(round_dir)["notes"])
                self.assertEqual(self.record(round_dir)["usage"]["tokens_in"], 100)

    def test_lineage_finds_children_even_without_a_recognized_spawn_output(self):
        self.configure(mode="unrecognized_spawn", spawn_output="unrecognized")
        round_dir = self.codex_plan()
        self.assertEqual(self.run_round(round_dir), 0)
        self.assertEqual(self.record(round_dir)["usage"]["tokens_in"], 300)
        self.assertTrue(self.record(round_dir)["notes"])

    def test_a_recovered_error_is_a_note_but_a_trailing_error_is_invalid(self):
        for mode, status in (("recovered", "valid"), ("trailing_error", "invalid")):
            with self.subTest(mode=mode):
                self.configure(mode=mode)
                round_dir = self.codex_plan()
                self.assertEqual(self.run_round(round_dir), int(status == "invalid"))
                self.assertEqual(self.record(round_dir)["status"], status)
                if mode == "recovered":
                    self.assertTrue(self.record(round_dir)["notes"])
                else:
                    self.assertIn("error", self.record(round_dir)["reasons"])

    def test_codex_path_scans_ignore_output_and_read_commands_and_changed_paths(self):
        stream = self.root / "paths.jsonl"
        items = [{"type": "command_execution", "command": "cat README.md", "aggregated_output": "/root/fixture-output/notes.txt"},
                 {"type": "command_execution", "command": "cat /root/fixture-command/notes.txt"},
                 {"type": "file_change", "changes": [{"path": "/root/fixture-change/notes.txt"}], "output": "/root/fixture-noise/notes.txt"}]
        stream.write_text("".join(json.dumps({"type": "item.completed", "item": item}) + "\n" for item in items))
        self.assertEqual(runner.outside_paths(stream, []), ["/root/fixture-change/notes.txt", "/root/fixture-command/notes.txt"])

    def test_login_output_is_discarded_and_only_exit_status_is_saved(self):
        round_dir = self.plan("mixed", ("1", "claude-test-1-0"), ("2", "codex:gpt-6.1-sol"))
        self.assertEqual(self.run_round(round_dir), 0)
        for backend in ("auth-status", "codex-login"):
            self.assertEqual(json.loads((round_dir / (backend + ".json")).read_text()), {"exit_code": 0})
            self.assertFalse((round_dir / (backend + ".txt")).exists())
            self.assertFalse((round_dir / (backend + ".stderr.txt")).exists())
        for path in round_dir.rglob("*"):
            if path.is_file():
                self.assertNotIn("fixture-private-login", path.read_text(errors="replace"))

    def test_incomplete_usage_means_state_their_complete_run_coverage(self):
        round_dir = self.codex_plan(1, 2)
        original = codex.run_audit
        def change_after_first(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[1].name == "run1-case.jsonl":
                self.configure(mode="missing")
            return result
        with mock.patch.object(codex, "run_audit", side_effect=change_after_first):
            self.assertEqual(self.run_round(round_dir), 1)
        summary = runner.summarize(round_dir)
        self.assertIn("40 (1 of 2)", summary)
        self.assertIn("lower bound:", summary)


if __name__ == "__main__":
    unittest.main()
