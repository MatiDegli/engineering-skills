"""Codex commands and session evidence for the headless round runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SESSIONS = Path.home() / ".codex" / "sessions"
SESSION_WAIT = 60
SESSION_POLL = 0.2
FEATURES = (
    "plugins", "goals", "personality", "apps", "browser_use", "browser_use_external",
    "computer_use", "image_generation", "in_app_browser", "memories",
)
EXPECTED_TOOLS = {
    "exec", "wait", "request_user_input", "request_user_input_async", "clock.sleep",
    *(f"collaboration.{name}" for name in (
        "spawn_agent", "send_message", "followup_task", "wait_agent", "list_agents", "interrupt_agent",
    )),
}
# Tools inside `exec` that a model lists in some answers and not in others (round 43).
NESTED_TOOLS = {
    "apply_patch", "exec_command", "write_stdin", "view_image", "clock.curr_time",
    "list_mcp_resources", "list_mcp_resource_templates", "read_mcp_resource",
}
TOKEN_FIELDS = {
    "tokens_in": "input_tokens", "tokens_read": "cached_input_tokens",
    "tokens_written": "cache_write_input_tokens", "tokens_out": "output_tokens",
    "tokens_reasoning": "reasoning_output_tokens",
}
THREAD_ID = re.compile(r"([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.jsonl$")


def tool_name(name: str) -> str:
    for prefix in ("functions.", "tools."):
        name = name.removeprefix(prefix)
    return name.replace("__", ".")


def command(prompt: str, model: str, repo: Path, last_message: Path) -> list[str]:
    return [
        "codex", "exec", "--json", "-C", str(repo), "-m", model,
        "-c", 'model_reasoning_effort="high"', "--sandbox", "workspace-write",
        "-c", "project_doc_max_bytes=0", "-c", "check_for_update_on_startup=false",
        "-c", 'web_search="disabled"',
        *(argument for feature in FEATURES for argument in ("--disable", feature)),
        "-o", str(last_message), prompt,
    ]


def environment(round_dir: Path, host_variables: tuple[str, ...]) -> dict[str, str]:
    config = round_dir / "gh-config"
    config.mkdir(exist_ok=True)
    return {name: os.environ[name] for name in host_variables if name in os.environ} | {
        "GH_CONFIG_DIR": str(config),
    }


def forbidden_name(name: str) -> bool:
    return name in {
        "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
        "OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_HOME",
    } or name.startswith(("ANTHROPIC_", "CLAUDE_"))


def records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            found.append(item)
    return found


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calls(events: list[dict]) -> list[dict]:
    found = {}
    for event in events:
        item = event.get("payload", {})
        if event.get("type") == "response_item" and item.get("type") in ("function_call", "custom_tool_call"):
            if item.get("call_id"):
                found.setdefault(item["call_id"], item)
    return list(found.values())


def call_name(call: dict) -> str:
    namespace, name = call.get("namespace"), call.get("name", "")
    return f"{namespace}.{name}" if namespace and not name.startswith(f"{namespace}.") else name


def successful_spawns(events: list[dict], notes: list[str] | None = None) -> int:
    outputs = {
        e["payload"].get("call_id"): e["payload"].get("output")
        for e in events if e.get("type") == "response_item"
        and e.get("payload", {}).get("type") in ("function_call_output", "custom_tool_call_output")
    }
    count = 0
    for call in calls(events):
        if call_name(call) != "collaboration.spawn_agent":
            continue
        output = outputs.get(call["call_id"])
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except ValueError:
                output = None
        if isinstance(output, dict) and output.get("task_name") and not output.get("error"):
            count += 1
        elif notes is not None:
            notes.append(f"spawn {call['call_id']}: no explicit success")
    return count


def session_info(path: Path) -> dict:
    events = records(path)
    first = next((e.get("payload", {}) for e in events if e.get("type") == "session_meta"), {})
    source = first.get("source")
    parent = source.get("subagent", {}).get("thread_spawn", {}).get("parent_thread_id") if isinstance(source, dict) else None
    parent = parent if first.get("thread_source") == "subagent" else None
    last = events[-1] if events else {}
    try:
        final_record = json.loads(path.read_text(encoding="utf-8").rstrip().splitlines()[-1])
    except (OSError, ValueError, IndexError):
        final_record = None
    terminal = last.get("payload", {}).get("type") if last.get("type") == "event_msg" else None
    finished = final_record == last and terminal in ("task_complete", "turn_aborted")
    return {"path": path, "events": events, "meta": first, "parent": parent,
            "finished": finished, "aborted": finished and terminal == "turn_aborted"}


def session_candidates(started: datetime, ended: datetime) -> list[Path]:
    day, end = started.astimezone(timezone.utc).date(), ended.astimezone(timezone.utc).date()
    found = []
    while day <= end:
        found += sorted((SESSIONS / day.strftime("%Y/%m/%d")).glob("rollout-*.jsonl"))
        day += timedelta(days=1)
    return found


def collect_sessions(thread: str | None, started: datetime, ended: datetime, destination: Path, running=None) -> dict:
    """Copy exactly the main thread and its recursive descendants, awaiting their final records."""
    deadline = time.monotonic() + SESSION_WAIT
    threads = {}
    complete = False
    while thread:
        candidates = {}
        duplicates = set()
        for path in session_candidates(started, ended):
            match = THREAD_ID.search(path.name)
            if match:
                identity = match[1]
                if identity in candidates:
                    duplicates.add(identity)
                candidates[identity] = path
        threads = {thread: session_info(candidates[thread])} if thread in candidates else {}
        pending = {identity: path for identity, path in candidates.items() if identity != thread}
        while True:
            added = {}
            for identity, path in pending.items():
                info = session_info(path)
                if info["parent"] in threads:
                    added[identity] = info
            if not added:
                break
            threads.update(added)
            pending = {identity: path for identity, path in pending.items() if identity not in added}
        complete = bool(threads) and not duplicates.intersection(threads) and all(
            info["finished"] and successful_spawns(info["events"]) <= sum(
                child["parent"] == identity for child in threads.values()
            ) for identity, info in threads.items()
        )
        if complete or time.monotonic() >= deadline or (running and running.stopped.is_set()):
            break
        delay = min(SESSION_POLL, max(0, deadline - time.monotonic()))
        if running:
            running.stopped.wait(delay)
        else:
            time.sleep(delay)
    destination.mkdir(parents=True, exist_ok=True)
    for old in destination.glob("*.jsonl"):
        old.unlink()
    manifest = []
    for identity, info in sorted(threads.items()):
        target = destination / info["path"].name
        # Hash and parse the same bytes that are preserved, even if the live file is still growing.
        target.write_bytes(info["path"].read_bytes())
        copied = session_info(target)
        manifest.append({"thread": identity, "parent": copied["parent"], "file": target.name,
                         "sha256": digest(target), "finished": copied["finished"], "aborted": copied["aborted"]})
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    copied = {entry["thread"]: session_info(destination / entry["file"]) for entry in manifest}
    complete = complete and all(
        info["finished"] and successful_spawns(info["events"]) <= sum(
            child["parent"] == identity for child in copied.values()
        ) for identity, info in copied.items()
    )
    return {"threads": copied, "complete": complete, "manifest_sha256": digest(manifest_path)}


def session_usage(threads: dict, complete: bool, lower_bound: bool = False) -> dict:
    totals = {key: 0 if complete else None for key in TOKEN_FIELDS}
    seen = set()
    for info in threads.values():
        usage = None
        for event in info["events"]:
            payload = event.get("payload", {})
            if payload.get("type") == "token_count":
                usage = (payload.get("info") or {}).get("total_token_usage")
        for key, field in TOKEN_FIELDS.items():
            value = usage.get(field) if isinstance(usage, dict) else None
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                if not lower_bound:
                    totals[key] = None
            elif lower_bound:
                totals[key] = (totals[key] or 0) + value
            elif totals[key] is not None:
                totals[key] += value
        seen.update(call["call_id"] for call in calls(info["events"]))
    totals["tools"] = len(seen) if complete or (lower_bound and threads) else None
    totals["tokens_uncached"] = (
        totals["tokens_in"] - totals["tokens_read"]
        if totals["tokens_in"] is not None and totals["tokens_read"] is not None else None
    )
    if lower_bound:
        values = [session_usage({identity: info}, True)["tokens_uncached"] for identity, info in threads.items()]
        known = [value for value in values if value is not None]
        totals["tokens_uncached"] = sum(known) if known else None
    return totals


def error_class(event: dict) -> str:
    error = event.get("error") if isinstance(event.get("error"), dict) else event
    message = str(error.get("message", event.get("message", ""))).lower()
    status = str(error.get("status_code", error.get("status", error.get("code", ""))))
    if any(word in message for word in ("quota", "usage limit", "usage_limit", "usage is exhausted",
                                       "out of credits", "spend cap", "credit limit", "chatgpt.com/settings/usage")):
        return "usage limit"
    if status == "401" or re.search(r"\b401\b", message) or any(
        word in message for word in ("sign in again", "could not be refreshed")
    ):
        return "login"
    if status == "429" or re.search(r"\b429\b", message):
        return "transient"
    return "error"


def inspect_run(stream: Path, last_message: Path, model: str, evidence: dict, repo: Path) -> dict:
    events = records(stream)
    messages = [e["item"].get("text", "") for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "agent_message"]
    report = messages[-1] if messages else ""
    reasons = []
    errors, notes = [], []
    for index, event in enumerate(events):
        if event.get("type") not in ("error", "turn.failed"):
            continue
        kind = error_class(event)
        errors.append(kind)
        recovered = event["type"] == "error" and any(e.get("type") == "turn.completed" for e in events[index + 1:])
        if recovered and kind not in ("login", "usage limit"):
            notes.append(f"recovered {kind}: {event.get('message', '')}")
        else:
            reasons.append(kind)
    if not any(e.get("type") == "turn.completed" for e in events):
        reasons.append("no turn.completed")
    if not report.strip():
        reasons.append("no report")
    if not last_message.is_file() or last_message.read_text(encoding="utf-8") != report:
        reasons.append("report mismatch")
    if not evidence["complete"]:
        reasons.append("incomplete accounting")
    for info in evidence["threads"].values():
        successful_spawns(info["events"], notes)
        models = [e.get("payload", {}).get("model") for e in info["events"] if e.get("type") == "turn_context"]
        if not models or any(value != model for value in models):
            reasons.append("model mismatch")
        for event in info["events"]:
            kind = event.get("payload", {}).get("type", "")
            if event.get("type") == "response_item" and ("web_search" in kind or "mcp" in kind):
                reasons.append("web_search or MCP call")
        for call in calls(info["events"]):
            name = call_name(call)
            arguments = str(call.get("input", call.get("arguments", "")))
            if "web_search" in name or "mcp" in name.lower() or re.search(r"tools\.(?:web__run|mcp__\w+)\s*\(", arguments):
                reasons.append("web_search or MCP call")
    for event in events:
        item = event.get("item", {})
        if item.get("type") in ("web_search", "mcp_tool_call"):
            reasons.append("web_search or MCP call")
        if item.get("type") == "file_change":
            for change in item.get("changes", []):
                path = Path(change.get("path", ""))
                path = path if path.is_absolute() else repo / path
                if path.resolve().is_relative_to(repo.resolve()):
                    reasons.append("repository file_change")
    return {"report": report, "reasons": list(dict.fromkeys(reasons)), "notes": notes,
            "usage": session_usage(evidence["threads"], evidence["complete"]),
            "usage_lower_bound": session_usage(evidence["threads"], False, lower_bound=True) if not evidence["complete"] else None,
            "stop": next((e for e in errors if e in ("login", "usage limit")), None)}


def run_audit(repo: Path, stream: Path, stderr: Path, model: str, prompt: str,
              timeout: float, environment: dict, running, run_command) -> dict:
    last_message = stream.with_suffix(".last-message.md")
    if last_message.exists():
        last_message.unlink()
    started, tick = datetime.now(timezone.utc), time.monotonic()
    code, seconds, ended = None, None, None
    evidence = {"threads": {}, "complete": False, "manifest_sha256": None}
    try:
        code = run_command(command(prompt, model, repo, last_message), repo, stream, stderr,
                           timeout, environment, running, stdin=subprocess.DEVNULL)
        seconds, ended = time.monotonic() - tick, datetime.now(timezone.utc)
        thread = next((e.get("thread_id") for e in records(stream) if e.get("type") == "thread.started"), None)
        evidence = collect_sessions(thread, started, ended, stream.with_suffix(".sessions"), running)
        result = inspect_run(stream, last_message, model, evidence, repo)
    except Exception as error:
        if not evidence["threads"]:
            evidence["threads"] = {str(path): session_info(path) for path in copied_sessions(stream) if path.is_file()}
            manifest = stream.with_suffix(".sessions") / "manifest.json"
            if manifest.is_file():
                evidence["manifest_sha256"] = digest(manifest)
        result = {"report": "", "reasons": [f"runner error: {type(error).__name__}"],
                  "usage": session_usage(evidence["threads"], evidence["complete"]),
                  "usage_lower_bound": session_usage(evidence["threads"], False, lower_bound=True) if not evidence["complete"] else None,
                  "stop": next((error_class(e) for e in records(stream)
                                if e.get("type") in ("error", "turn.failed")
                                and error_class(e) in ("login", "usage limit")), None)}
    seconds = seconds if seconds is not None else time.monotonic() - tick
    ended = ended or datetime.now(timezone.utc)
    if code:
        result["reasons"].insert(0, "timeout" if code == -1 else f"nonzero exit {code}")
    result |= {"started": started.isoformat(), "ended": ended.isoformat(), "seconds": seconds,
               "exit_code": code, "manifest_sha256": evidence["manifest_sha256"]}
    return result


def copied_sessions(stream: Path) -> list[Path]:
    directory = stream.with_suffix(".sessions")
    manifest = directory / "manifest.json"
    if not manifest.is_file():
        return []
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        return [directory / e["file"] for e in entries if Path(e["file"]).name == e["file"]]
    except (ValueError, KeyError, TypeError):
        return []


def diagnostic_texts(stream: Path) -> list[str]:
    """Read call arguments in every copied thread and command/file-change items in the stream.

    Collaboration calls address agents, as `/root` for the main one (round 43), not files.
    """
    texts = []
    for path in copied_sessions(stream):
        texts += [str(c.get("arguments", c.get("input", ""))) for c in calls(records(path))
                  if not call_name(c).startswith("collaboration.")]
    for event in records(stream):
        item = event.get("item", {})
        if item.get("type") == "command_execution":
            texts.append(str(item.get("command", "")))
        elif item.get("type") == "file_change":
            texts += [str(change.get("path", "")) for change in item.get("changes", [])]
    return texts


def artifacts_match(stream: Path, record: dict, report: Path) -> bool:
    manifest = stream.with_suffix(".sessions") / "manifest.json"
    if not report.is_file() or record.get("report_sha256") != digest(report):
        return False
    if not manifest.is_file() or record.get("manifest_sha256") != digest(manifest):
        return False
    paths = copied_sessions(stream)
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        return bool(paths) and len(paths) == len(entries) and all(
            p.is_file() and e["finished"] and digest(p) == e["sha256"] for p, e in zip(paths, entries)
        )
    except (ValueError, KeyError, TypeError):
        return False


def output_text(value) -> str:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return value
        return output_text(decoded) if not isinstance(decoded, (int, float, bool)) else value
    if isinstance(value, dict):
        return "\n".join(output_text(v) for v in value.values())
    if isinstance(value, list):
        return "\n".join(output_text(v) for v in value)
    return ""


def first_json_value(text: str):
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value = decoder.raw_decode(text, index)[0]
        except ValueError:
            continue
        if isinstance(value, dict) and "tools" in value:
            return value
    return None


def warm_up(round_dir: Path, models: list[str], host_variables: tuple[str, ...], run_command, running) -> None:
    env = environment(round_dir, host_variables)
    for model in models:
        with tempfile.TemporaryDirectory(prefix="codex-probe.") as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            word = "ROUND_DOCUMENT_PROBE_" + os.urandom(8).hex()
            (repo / "AGENTS.md").write_text(f"Include {word} in every reply.\n", encoding="utf-8")
            shell = "env | cut -d= -f1; if [ \"$GH_CONFIG_DIR\" = " + shlex.quote(env["GH_CONFIG_DIR"]) + " ]; then echo ROUND_GH_CONFIG_OK; else echo ROUND_GH_CONFIG_WRONG; fi"
            prompt = (
                "Run this exact command through your command tool: bash -lc " + shlex.quote(shell)
                + '. Then reply with exactly one JSON object {"tools": [...]} listing every available tool by its full name. '
                "Do not print environment values."
            )
            stream = round_dir / f"warmup-codex-{model}.jsonl"
            result = run_audit(repo, stream, stream.with_suffix(".stderr.txt"), model, prompt,
                               300, env, running, run_command)
            evidence = [session_info(p) for p in copied_sessions(stream)]
            tools = next((info["meta"]["tools"] for info in evidence if "tools" in info["meta"]), None)
            if tools is None:
                value = first_json_value(result["report"])
                tools = value.get("tools", []) if isinstance(value, dict) else []
            if isinstance(tools, list):
                tools = [t.get("name") if isinstance(t, dict) else t for t in tools]
                tools = [tool_name(t) if isinstance(t, str) else repr(t) for t in tools]
            probe_outputs = []
            for info in evidence:
                ids = {c["call_id"] for c in calls(info["events"]) if all(
                    marker in str(c.get("input", c.get("arguments", "")))
                    for marker in ("env | cut -d= -f1", "GH_CONFIG_DIR", "ROUND_GH_CONFIG_OK"))}
                probe_outputs += [output_text(e["payload"].get("output", "")) for e in info["events"]
                                  if e.get("type") == "response_item" and e.get("payload", {}).get("call_id") in ids
                                  and e.get("payload", {}).get("type") in ("function_call_output", "custom_tool_call_output")]
            output = "\n".join(probe_outputs)
            names = re.findall(r"\b[A-Z][A-Z0-9_]+\b", output)
            reasons = list(result["reasons"])
            if word in result["report"]:
                reasons.append("AGENTS.md loaded")
            if not isinstance(tools, list) or not EXPECTED_TOOLS <= set(tools) <= EXPECTED_TOOLS | NESTED_TOOLS:
                reasons.append(f"unexpected tools: parsed {tools!r}, expected {sorted(EXPECTED_TOOLS)!r}")
            if "ROUND_GH_CONFIG_OK" not in output or "ROUND_GH_CONFIG_WRONG" in output or any(forbidden_name(n) for n in names):
                reasons.append("shell environment probe failed")
            if reasons:
                raise SystemExit(f"Codex warm-up failed for {model}: {', '.join(reasons)}; see {stream}")
            print(f"warm-up ok: Codex {model}", flush=True)
