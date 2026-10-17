#!/usr/bin/env python3
"""Run evaluation rounds headless with Claude Code, and summarize them.

`plan` exports the skill and prepares one repository per run; `run` makes the audits, so run it
yourself; `summarize` scores the reports and checks what the runs left behind; `clean` removes the
prepared repositories and the skill export. A round directory keeps the plan, streams, reports, and
summary. Keep it outside this repository and outside /tmp, which a restart may clear.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import re
import shutil
import signal
import subprocess
import tarfile
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from tools.evals import (
    CASES,
    case_files,
    finding_rows,
    git_at,
    git_environment,
    misplaced_citations,
    prepare,
    priority_placement,
    score_report,
    verify,
)
from tools.validate_repo import ROOT

SKILL = "skills/auditing-repositories"
PROMPTS = {
    "full": (
        "Use the auditing-repositories skill at {skill}: read its SKILL.md and follow it to audit"
        " the repository in the current directory. Work only in this repository, the skill"
        " directory, and scratch directories you create; do not read any other path. Reply with"
        " only the final report, exactly in the skill's report format."
    ),
}
LOGIN_FAILURE = "Failed to refresh OAuth token"
ATTEMPTS = 3
TEMPORARY = re.compile(r"(audit|skill)\.[A-Za-z0-9_]{8}")
HOME_PATH = re.compile(r"(?<![\w.-])(?:/home/[\w.-]+|/root|/mnt/[a-z])(?:/[^\s\"'`,;)]*)?")
PROBLEMS = (
    ("unmarked_high", "unmarked high"),
    ("uncovered", "uncovered"),
    ("duplicated", "duplicated"),
    ("unknown", "unknown"),
    ("bad_citations", "bad citations"),
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def claude_command(prompt: str, model: str, skill: Path, settings: str | None = None) -> list[str]:
    """Return the audit command.

    Only user settings load, with hooks off, so the audited repository's own agent settings,
    hooks, skills, and agents never load; the effort is fixed rather than inherited. A provider's
    settings file, which `provider_settings` checks has no hooks, replaces the hooks switch.
    """
    return [
        *("claude", "-p", prompt, "--model", model, "--effort", "high", "--add-dir", str(skill)),
        *("--allowedTools", "Bash", "Read", "Grep", "Glob"),
        *("--disallowedTools", "WebFetch", "WebSearch", "Edit", "Write", "NotebookEdit"),
        *("--setting-sources", "user", "--settings", settings or '{"disableAllHooks": true}'),
        *("--output-format", "stream-json", "--verbose", "--no-session-persistence"),
        "--strict-mcp-config",
    ]


def model_label(model: str) -> str:
    """`claude-opus-5-5` becomes `Opus 5.5`; other IDs stay as they are."""
    parts = model.split("-")
    if len(parts) >= 4 and parts[0] == "claude" and parts[2].isdigit():
        return f"{parts[1].capitalize()} {parts[2]}.{parts[3]}"
    return model


def stream_results(path: Path) -> list[dict]:
    """Return the stream's result events; a run that used background helpers has several."""
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            results.append(event)
    return results


def stream_usage(path: Path, results: list[dict]) -> dict[str, int]:
    """Count tool calls in the stream and the tokens of the whole run, background helpers included.

    `modelUsage` in the last result event is cumulative across the session and its helpers, while
    each event's `usage` covers only its own turns.
    """
    tools = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (event.get("message") or {}).get("content") if event.get("type") == "assistant" else None
        tools += sum(item.get("type") == "tool_use" for item in content or [] if isinstance(item, dict))
    models = (results[-1].get("modelUsage") or {}).values() if results else []
    read = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
    return {
        "tools": tools,
        "tokens_in": sum(m.get(k) or 0 for m in models for k in read),
        "tokens_out": sum(m.get("outputTokens") or 0 for m in models),
    }


def report_text(results: list[dict]) -> str:
    """Return the run's report: the last result that holds a Findings section, else the last one.

    A run that used background helpers ends with several results, and its last one may only say
    that an earlier message holds the report.
    """
    texts = [str(r.get("result") or "") for r in results]
    reports = [text for text in texts if "## Findings" in text]
    return reports[-1] if reports else (texts[-1] if texts else "")


def ran_model(results: list[dict], model: str) -> bool:
    return any(name.split("[")[0] == model for r in results for name in r.get("modelUsage") or {})


def login_failed(results: list[dict]) -> bool:
    return bool(results) and str(results[-1].get("result", "")).startswith(LOGIN_FAILURE)


def case_path(case: str) -> Path:
    return Path(case).expanduser().resolve() if "/" in case else CASES / case


def round_paths(round_dir: Path) -> dict[str, Path]:
    names = ("plan.json", "streams", "reports", "log.txt", "summary.md", "tmp-before.txt")
    return {name: round_dir / name for name in names}


def check_round_dir(round_dir: Path) -> None:
    resolved = round_dir.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise SystemExit("Keep the round directory outside this repository")
    if Path(tempfile.gettempdir()).resolve() in resolved.parents:
        print(f"warning: {round_dir} is under the temporary directory, which a restart may clear")


def repository_git(*arguments: str) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        env=git_environment(),
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout


def export_skill(revision: str) -> Path:
    """Extract the skill at a revision into a new temporary directory, away from the reports."""
    archive = repository_git("archive", "--format=tar", f"{revision}:{SKILL}")
    skill = Path(tempfile.mkdtemp(prefix="skill.")) / "auditing-repositories"
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(skill, filter="data")
    return skill


def job_skill(data: dict, job: dict) -> str:
    """Return the skill a job audits with; plans before per-run revisions kept one skill."""
    return job.get("skill") or data["skill"]


def job_revision(data: dict, job: dict) -> str:
    return job.get("revision") or data["skill_commit"]


def skill_exports(data: dict) -> list[Path]:
    return [Path(path).parent for path in (data.get("skills") or {"": data.get("skill")}).values()]


def plan(round_dir: Path, runs: list[tuple], cases: list[str], revision: str) -> dict:
    """Export each skill revision and prepare a fresh repository for every run of every case.

    A run may name its own revision, so a control and a candidate share one round. Jobs are listed
    case by case with every run of a case together, so the arms run side by side in time instead
    of hours apart, when the service may have changed.
    """
    check_round_dir(round_dir)
    paths = round_paths(round_dir)
    if paths["plan.json"].exists():
        raise SystemExit(f"{round_dir} already has a plan")
    for case in cases:
        if not (case_path(case) / "expected.json").is_file():
            raise SystemExit(f"unknown case: {case}")
    specs = []
    for number, model, *rest in runs:
        wanted = rest[0] if rest and rest[0] else revision
        specs.append((number, model, repository_git("rev-parse", "--short", wanted).decode().strip()))
    for name in ("streams", "reports"):
        paths[name].mkdir(parents=True, exist_ok=True)
    listing = sorted(os.listdir(tempfile.gettempdir()))
    paths["tmp-before.txt"].write_text("\n".join(listing) + "\n", encoding="utf-8")
    skills = {commit: str(export_skill(commit)) for commit in dict.fromkeys(s[2] for s in specs)}
    jobs = []
    for case in cases:
        for run, model, commit in specs:
            directory = Path(tempfile.mkdtemp(prefix="audit."))
            name = case_path(case).name
            prepare(case_path(case), directory / name)
            job = {"run": run, "model": model, "case": case, "name": name, "dir": str(directory)}
            jobs.append(job | {"revision": commit, "skill": skills[commit]})
    data = {"created": now(), "skill_commit": ", ".join(skills), "skills": skills, "level": "full"}
    data["jobs"] = jobs
    paths["plan.json"].write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


HOSTING_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


def audit_environment(round_dir: Path) -> dict[str, str]:
    """Return the audit's environment, with no GitHub CLI login.

    A prepared repository is not the hosted one: a rewritten history has no hosted runs, and live
    hosting state changes between rounds. With an empty `gh` configuration and no tokens, an audit
    reports remote settings as unverified, the same way in every round.
    """
    config = round_dir / "gh-config"
    config.mkdir(exist_ok=True)
    clean = {name: value for name, value in os.environ.items() if name not in HOSTING_TOKENS}
    return clean | {"GH_CONFIG_DIR": str(config)}


def run_command(
    command: list[str],
    cwd: Path,
    stdout: Path,
    stderr: Path,
    timeout: float,
    environment: dict[str, str] | None = None,
) -> int:
    """Run in a new session and stop the whole process group on timeout, grandchildren included."""
    with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
        process = subprocess.Popen(
            command, cwd=cwd, env=environment, stdout=out, stderr=err, start_new_session=True
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            err.write(f"\nstopped after {timeout:.0f} seconds\n")
            return -1


def provider_settings(path: Path) -> dict:
    """Check a Claude Code settings file that routes a provider, and return how to use it.

    The CLI reads the file itself, so its token never passes through the runner; the runner reads
    only the model aliases. A file with hooks is refused, since it replaces the hooks switch.
    """
    settings = json.loads(path.read_text(encoding="utf-8"))
    if settings.get("hooks"):
        raise SystemExit(f"Provider settings must not define hooks: {path}")
    env = settings.get("env") or {}
    aliases = {name: str(value) for name, value in env.items() if name.startswith("ANTHROPIC_DEFAULT_")}
    return {"path": str(path.resolve()), "aliases": aliases}


def cli_model(model: str, provider: dict | None) -> str:
    """Return what to pass to `--model`: the model itself, or the alias its provider maps to it."""
    if not provider:
        return model
    for alias in ("sonnet", "opus", "haiku"):
        if provider["aliases"].get(f"ANTHROPIC_DEFAULT_{alias.upper()}_MODEL", "").split("[")[0] == model:
            return alias
    raise SystemExit(f"No alias in the provider settings maps to {model}")


class Spending:
    """Stop launching audits once the finished ones have used the round's budget.

    The CLI reports an API-equivalent cost; on a subscription it measures quota, not money.
    Audits already running finish, so a round can end somewhat above its budget.
    """

    def __init__(self, limit: float) -> None:
        self.limit, self.spent, self.lock = limit, 0.0, threading.Lock()

    def allows(self) -> bool:
        with self.lock:
            return self.spent < self.limit

    def add(self, cost: float) -> None:
        with self.lock:
            self.spent += cost


def warm_up(round_dir: Path, models: list[str], providers: dict[str, dict]) -> None:
    """Make one short call per model, one at a time, before any parallel run.

    Parallel runs that find an expired login race to refresh it, and most fail before their first
    tool call; a serial call refreshes it first. It also stops the round when the CLI does not
    serve a requested model, before any audit spends anything.
    """
    for model in models:
        output = round_dir / f"warmup-{model}.json"
        provider = providers.get(model)
        command = ["claude", "-p", "Reply with the single word OK.", "--model", cli_model(model, provider)]
        command += ["--setting-sources", "user", "--strict-mcp-config", "--no-session-persistence"]
        command += ["--settings", provider["path"]] if provider else []
        with output.open("w", encoding="utf-8") as out:
            subprocess.run(
                [*command, "--output-format", "json"],
                cwd=tempfile.gettempdir(),
                stdout=out,
                stderr=subprocess.DEVNULL,
                timeout=300,
            )
        try:
            event = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            event = {"is_error": True}
        if event.get("is_error") or not ran_model([event], model):
            raise SystemExit(f"warm-up failed for {model}; see {output}")
        print(f"warm-up ok: {model}", flush=True)


def repository_clean(repo: Path) -> bool:
    try:
        status = git_at(repo / ".git", "status", "--porcelain", "--ignored", work_tree=repo)
    except subprocess.CalledProcessError:
        return False
    return not status


def audit(round_dir: Path, data: dict, job: dict, launch: dict) -> str:
    """Run one audit, retrying a launch whose login refresh failed, and save its report."""
    paths = round_paths(round_dir)
    label = f"run{job['run']}-{job['name']}"
    repo = Path(job["dir"]) / job["name"]
    report = paths["reports"] / f"{label}.md"
    if report.exists():
        return f"{label}: skipped, report exists"
    if not repository_clean(repo):
        return f"{label}: skipped, the prepared repository is missing or changed"
    if not launch["spending"].allows():
        return f"{label}: skipped, budget reached"
    provider = launch["providers"].get(job["model"])
    stream, stderr = paths["streams"] / f"{label}.jsonl", paths["streams"] / f"{label}.stderr.txt"
    prompt = PROMPTS[data["level"]].format(skill=job_skill(data, job))
    skill = Path(job_skill(data, job))
    settings = provider["path"] if provider else None
    command = claude_command(prompt, cli_model(job["model"], provider), skill, settings)
    for attempt in range(1, ATTEMPTS + 1):
        environment = audit_environment(round_dir)
        code = run_command(command, repo, stream, stderr, launch["timeout"], environment)
        results = stream_results(stream)
        if not login_failed(results) or attempt == ATTEMPTS:
            break
        stream.rename(paths["streams"] / f"{label}.login-failure-{attempt}.jsonl")
        time.sleep(random.uniform(*launch["pause"]))
    launch["spending"].add(max((r.get("total_cost_usd") or 0 for r in results), default=0))
    if results:
        report.write_text(report_text(results), encoding="utf-8")
    used = sorted({name for r in results for name in r.get("modelUsage") or {}})
    flag = "" if ran_model(results, job["model"]) else " MODEL MISMATCH"
    return f"{label}: exit {code}, models {','.join(used) or 'none'}{flag}"


def run(
    round_dir: Path,
    jobs: int,
    timeout: float,
    budget: float,
    pause: tuple[int, int] = (20, 60),
    providers: dict[str, dict] | None = None,
) -> int:
    """Run every planned audit; return 1 when a model differs or an audit was skipped.

    `providers` maps a model to the checked settings file that routes it to its provider.
    """
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    status = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=60)
    if '"loggedIn": true' not in status.stdout:
        raise SystemExit("claude is not logged in here: run 'claude auth login' first")
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=60)
    (round_dir / "cli-version.txt").write_text(version.stdout, encoding="utf-8")
    providers = providers or {}
    warm_up(round_dir, sorted({job["model"] for job in data["jobs"]}), providers)
    launch = {"timeout": timeout, "pause": pause, "providers": providers, "spending": Spending(budget)}
    lines = []
    with paths["log.txt"].open("a", encoding="utf-8") as log:
        log.write(f"start {now()} {version.stdout.strip()}, budget USD {budget:g}\n")
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [
                pool.submit(audit, round_dir, data, job, launch) for job in data["jobs"]
            ]
            for future in as_completed(futures):
                lines.append(future.result())
                log.write(lines[-1] + "\n")
                log.flush()
                print(lines[-1], flush=True)
        log.write(f"end {now()}\n")
    return int(any(mark in line for line in lines for mark in ("MODEL MISMATCH", "skipped, the", "skipped, budget")))


def outside_paths(stream: Path, allowed: list[Path]) -> list[str]:
    """List home or Windows paths in the run's tool calls outside its repository and the skill.

    Executables, such as an interpreter the run started, are left out, and so are search patterns
    that only look like paths and the files where the CLI keeps a long tool output for the run.
    """
    found = set()
    for line in stream.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for item in content if isinstance(content, list) else []:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            for match in HOME_PATH.findall(json.dumps(item.get("input"))):
                path = Path(match)
                if any(match == str(a) or match.startswith(f"{a}/") for a in allowed):
                    continue
                if any(mark in match for mark in "|\\*") or "/.claude/projects/-tmp-audit" in match:
                    continue
                if not (path.is_file() and os.access(path, os.X_OK)):
                    found.add(match)
    return sorted(found)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_job(job: dict, data: dict, paths: dict[str, Path], repo: Path, totals: Counter) -> dict:
    """Score one run's report and check its stream and prepared repository."""
    label, case = f"run{job['run']}-{job['name']}", case_path(job["case"])
    report, stream = paths["reports"] / f"{label}.md", paths["streams"] / f"{label}.jsonl"
    expected, result = score_report(report, case, repo)
    text = report.read_text(encoding="utf-8")
    problems = [f"{name} {len(result[key])}" for key, name in PROBLEMS if result.get(key)]
    if result["false_flags"]:
        problems.append(f"false flag {', '.join(result['false_flags'])}")
    if result["leaked"]:
        problems.append("secret copied")
    gaps = f"{len(result['found'])} of {len(expected['must_find'])}"
    if result["missed"]:
        gaps += f" (missed {', '.join(result['missed'])})"
    top = re.search(r"(\d+) of (\d+) in the first five", priority_placement(text, expected) or "")
    passed = not any(values for key, values in result.items() if key != "found")
    results = stream_results(stream) if stream.exists() else []
    totals.update(
        found=len(result["found"]),
        seeded=len(expected["must_find"]),
        passed=int(passed),
        reports=1,
        top=int(top[1]) if top else 0,
        top_of=int(top[2]) if top else 0,
        bad=len(result["bad_citations"]),
        misplaced=len(misplaced_citations(text, repo)),
        high=sum(row["priority"] == "high" for row in finding_rows(text).values()),
        seconds=sum(r.get("duration_ms") or 0 for r in results) / 1000,
        cents=100 * max((r.get("total_cost_usd") or 0 for r in results), default=0),
        **(stream_usage(stream, results) if stream.exists() else {}),
    )
    notes = []
    if not ran_model(results, job["model"]):
        notes.append(f"{label}: the stream does not show {job['model']}")
    changed = verify(case, Path(job["dir"]) / job["name"])
    if changed:
        notes.append(f"{label}: the prepared repository changed: {'; '.join(changed[:5])}")
    if result["leaked"]:
        notes.append(f"{label}: copied {', '.join(result['leaked'])}")
    allowed = [Path(job["dir"]), Path(job_skill(data, job)).parent]
    outside = outside_paths(stream, allowed) if results else []
    if outside:
        notes.append(f"{label}: tool calls name paths outside the run: {', '.join(outside[:8])}")
    row = (
        f"| {job['name']} | {job['run']} | {arm_label(data, job)} | {gaps} "
        f"| {'yes' if passed else 'no'} | {f'{top[1]} of {top[2]}' if top else '—'} "
        f"| {', '.join(problems) or '—'} |"
    )
    return {"row": row, "hash": f"- {job['name']} run {job['run']}: `{sha256(report)}`", "notes": notes}


def leftovers(paths: dict[str, Path], data: dict) -> list[str]:
    """Name new entries of the temporary directory that a run's stream mentions."""
    before = set(paths["tmp-before.txt"].read_text(encoding="utf-8").split())
    planned = {Path(job["dir"]).name for job in data["jobs"]} | {p.name for p in skill_exports(data)}
    streams = {p.stem: p.read_text(encoding="utf-8") for p in sorted(paths["streams"].glob("*.jsonl"))}
    notes = []
    for entry in sorted(set(os.listdir(tempfile.gettempdir())) - before - planned):
        location = str(Path(tempfile.gettempdir()) / entry)
        named = [stem for stem, text in streams.items() if location in text]
        if named:
            notes.append(f"left in the temporary directory: {entry}, named by {', '.join(named)}")
    return notes


def arm_label(data: dict, job: dict) -> str:
    """Name a job's model, and its revision when the round compares several."""
    label = model_label(job["model"])
    return f"{label} @ {job_revision(data, job)}" if len(data.get("skills") or {}) > 1 else label


def summarize(round_dir: Path) -> str:
    """Score every report, check the prepared repositories, and write summary.md."""
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    rows, hashes, notes = [], [], []
    totals: dict[str, Counter] = defaultdict(Counter)
    with ExitStack() as stack:
        repos: dict[str, Path] = {}
        for job in data["jobs"]:
            label = f"run{job['run']}-{job['name']}"
            if not (paths["reports"] / f"{label}.md").exists():
                notes.append(f"{label}: no report")
                continue
            if job["case"] not in repos:
                repos[job["case"]] = stack.enter_context(case_files(case_path(job["case"])))
            scored = score_job(job, data, paths, repos[job["case"]], totals[arm_label(data, job)])
            rows.append(scored["row"])
            hashes.append(scored["hash"])
            notes += scored["notes"]
    notes += leftovers(paths, data)
    lines = [
        f"# Round summary ({now()})",
        "",
        f"Skill `{data['skill_commit']}`, level {data['level']}, planned {data['created']}.",
        "",
        "| Case | Run | Model | Seeded gaps found | Passes the scorer"
        " | Top priorities in first five | Problems |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        "| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five"
        " | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD"
        " | Mean tool calls | Mean input tokens | Mean output tokens |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model, t in totals.items():
        n = t["reports"] or 1
        lines.append(
            f"| {model} | {t['found']} of {t['seeded']} | {t['passed']} of {t['reports']} "
            f"| {t['top']} of {t['top_of']} | {t['bad']} | {t['misplaced']} | {t['high']} "
            f"| {t['seconds'] / 60 / n:.1f} | {t['cents'] / 100 / n:.2f} | {t['tools'] / n:.0f} "
            f"| {t['tokens_in'] / n:,.0f} | {t['tokens_out'] / n:,.0f} |"
        )
    lines += ["", "Report SHA-256 hashes:", "", *hashes, "", "Notes:", ""]
    lines += [f"- {note}" for note in notes] or ["- none"]
    summary = "\n".join(lines) + "\n"
    paths["summary.md"].write_text(summary, encoding="utf-8")
    return summary


def clean(round_dir: Path) -> list[str]:
    """Remove the prepared repositories and the skill export that this round's plan created.

    Only paths recorded in the plan that are direct children of the temporary directory, with the
    names that `plan` creates, are removed; anything else is reported and kept.
    """
    data = json.loads(round_paths(round_dir)["plan.json"].read_text(encoding="utf-8"))
    temporary = Path(tempfile.gettempdir()).resolve()
    removed = []
    for path in [Path(job["dir"]) for job in data["jobs"]] + skill_exports(data):
        resolved = path.resolve()
        created = resolved.parent == temporary and TEMPORARY.fullmatch(resolved.name)
        if not created or path.is_symlink():
            print(f"kept {path}: not a directory this round created")
            continue
        if resolved.is_dir():
            shutil.rmtree(resolved)
            removed.append(str(resolved))
    return removed


def parse_runs(values: list[str]) -> list[tuple[str, str, str | None]]:
    runs = []
    for value in values:
        number, _, rest = value.partition("=")
        model, _, revision = rest.partition("@")
        if not number.isdigit() or not model:
            raise SystemExit(f"--run takes NUMBER=MODEL or NUMBER=MODEL@REVISION, not {value!r}")
        runs.append((number, model, revision or None))
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="export the skill and prepare every run")
    plan_parser.add_argument("round_dir", type=Path)
    plan_parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="NUMBER=MODEL",
        help="a run number, a full model ID, and optionally a skill revision, such as"
        " 51=claude-opus-5-5 or 52=claude-opus-5-5@8b2a2c6; repeat for each run",
    )
    plan_parser.add_argument(
        "--case",
        action="append",
        metavar="NAME_OR_PATH",
        help="a case name or a case directory path; repeat; default: every case in evals/cases",
    )
    plan_parser.add_argument(
        "--revision", default="HEAD", help="skill revision for runs that do not name one"
    )
    run_parser = commands.add_parser("run", help="run every planned audit (starts agents)")
    run_parser.add_argument("round_dir", type=Path)
    run_parser.add_argument("--jobs", type=int, default=6)
    run_parser.add_argument("--timeout-minutes", type=float, default=90)
    run_parser.add_argument(
        "--budget-usd",
        type=float,
        required=True,
        help="stop launching audits once finished ones reach this API-equivalent cost",
    )
    run_parser.add_argument(
        "--model-settings",
        action="append",
        default=[],
        metavar="MODEL=SETTINGS",
        help="run MODEL through a Claude Code settings file that routes its provider, such as glm-5.3",
    )
    for name, text in (
        ("summarize", "score the reports and check what the runs left behind"),
        ("clean", "remove the prepared repositories and the skill export"),
    ):
        commands.add_parser(name, help=text).add_argument("round_dir", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "plan":
        cases = arguments.case or sorted(p.parent.name for p in CASES.glob("*/expected.json"))
        data = plan(arguments.round_dir, parse_runs(arguments.run), cases, arguments.revision)
        print(f"planned {len(data['jobs'])} runs of skill {data['skill_commit']}")
        return 0
    if arguments.command == "run":
        providers = {}
        for value in arguments.model_settings:
            model, _, path = value.partition("=")
            if not model or not path:
                parser.error(f"--model-settings takes MODEL=SETTINGS, not {value!r}")
            providers[model] = provider_settings(Path(path).expanduser())
        timeout = arguments.timeout_minutes * 60
        return run(arguments.round_dir, arguments.jobs, timeout, arguments.budget_usd, providers=providers)
    if arguments.command == "summarize":
        print(summarize(arguments.round_dir), end="")
        return 0
    for path in clean(arguments.round_dir):
        print(f"removed {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
