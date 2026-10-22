#!/usr/bin/env python3
"""Run evaluation rounds headless with Claude Code or Codex, and summarize them.

`plan` exports the skill and prepares one repository per run, with a snapshot of GitHub's state
beside it when the case names its GitHub repository; `run` makes the audits, so run it yourself;
`summarize` scores the reports and checks what the runs left behind; `clean` removes the prepared
repositories and the skill export. A round directory keeps the plan, hosted-state snapshots,
streams, reports, and summary. Keep it outside this repository and outside /tmp, which a restart
may clear.
"""

from __future__ import annotations

import argparse
import hashlib
import fcntl
import io
import json
import os
import random
import re
import shlex
import shutil
import signal
import subprocess
import tarfile
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from tools import codex_backend
from tools.evals import (
    CASES,
    case_files,
    counted_defects,
    check_text,
    finding_rows,
    git_at,
    git_environment,
    has_problems,
    misplaced_citations,
    prepare,
    priority_placement,
    score_report,
    verify,
)
from tools.validate_repo import ROOT

SKILL = "skills/auditing-repositories"
# The levels of evals/README.md: the skill, its catalog with the report format, a bare request, or
# the prompt an experienced engineer would write, which a model wrote without tools or context.
EXPERT_PROMPT = ROOT / "evals" / "prompts" / "expert.md"
PROMPTS = {
    "full": (
        "Use the auditing-repositories skill at {path}: read its SKILL.md and follow it to audit"
        " the repository in the current directory. Work only in this repository, the skill"
        " directory, and scratch directories you create; do not read any other path. Reply with"
        " only the final report, exactly in the skill's report format."
    ),
    "catalog": (
        "Audit the repository in the current directory against the criteria in {path}/criteria.md"
        " and the area files it lists. Do not modify the repository or install dependencies. Work"
        " only in this repository, that directory, and scratch directories you create; do not read"
        " any other path. Reply with only the final report, in this format:\n\n"
        "## Findings\n| ID | Status | Priority | Evidence | Improvement |\n| --- | --- | --- | --- | --- |\n\n"
        "One row per criterion that is not met, with status partial, pending-implementation, or"
        " pending-verification, and priority high, medium, or low.\n\n"
        "## Priority actions\nUp to five actions, most important first, each naming the IDs of the"
        " findings it closes, with scope, an acceptance check, and timing: now, before release, or"
        " when the need arises.\n\n"
        "## Coverage\n- meets: IDs\n- not-applicable: ID (reason), ID (reason)\n"
        "- not-applicable areas: AREA-* (reason)\n\n"
        "Every ID of the core catalog and of each area that applies appears exactly once, in"
        " Findings or in Coverage; an area that does not apply appears once on the not-applicable"
        " areas line."
    ),
    "none": (
        "Audit the repository in the current directory and list its problems, with evidence for"
        " each, then give up to five priority actions, most important first. Do not modify the"
        " repository or install dependencies. Work only in this repository and scratch directories"
        " you create; do not read any other path. Reply with only the final report."
    ),
    "expert": EXPERT_PROMPT.read_text(encoding="utf-8").replace("{", "{{").replace("}", "}}")
    + "\nWork only in this repository and scratch directories you create; do not read any other"
    " path. Reply with only the final report.",
}
# Levels that give the agent neither the skill nor the catalog: their reports have no criterion IDs.
WITHOUT_CATALOG = ("none", "expert")
# Added to every level's prompt for a job whose case has a snapshot of its hosted state. Every
# level says not to read other paths, so the sentence allows that file by name.
HOSTED_PROMPT = (
    "The repository has no remote. GitHub's state for it, read when this round was planned, is in"
    " `{path}`, which you may read: the CI runs and checks on the audited commit, and the default"
    " branch's protection and rules. Use it in place of the host."
)
GITHUB_NAME = re.compile(r"[A-Za-z0-9-]+/(?!\.\.?$)[A-Za-z0-9._-]+")
# The fields of each listed run that a snapshot keeps; the API's other fields stay out.
CHECK_RUN_FIELDS = ("name", "status", "conclusion", "started_at", "completed_at")
WORKFLOW_RUN_FIELDS = ("name", "event", "status", "conclusion", "created_at", "head_branch")
LOGIN_FAILURE = "Failed to refresh OAuth token"
ATTEMPTS = 3
TEMPORARY = re.compile(r"(audit|skill|catalog)\.[A-Za-z0-9_]{8}")
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


# One headless round at a time per provider on this machine, for every runner that takes these
# locks: rounds of one provider share its login or key and its limits. The Claude login's lock,
# `anthropic`, keeps the file older runners take, so they still exclude each other; another
# provider's lock is a file beside it. Rounds of different providers run at once on one host, so
# each logs the others' locks (`lock_overlaps`).
ROUND_LOCK = Path.home() / ".cache" / "engineering-skills" / "rounds.lock"
LOCK_POLL = 5
ANTHROPIC = "anthropic"
HOST = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*")
DEFAULT_PORTS = {"https": 443, "http": 80}


def check_host(host: str) -> str:
    """Return a provider's host, or exit unless it is a lowercase DNS name other than `anthropic`.

    The whole host must match, so `..`, a slash, or a trailing newline never reaches a lock's file
    name; `anthropic` names the Claude login.
    """
    if not HOST.fullmatch(host) or host == ANTHROPIC:
        raise SystemExit(f"a provider host must be a lowercase DNS name other than {ANTHROPIC}, not {host!r}")
    return host


def provider_resource(url: str) -> str:
    """Return the resource of a provider's base URL: its host, plus `_<port>` for a port other than
    the scheme's default, so `https://api.z.ai` and `https://api.z.ai:443` share one lock."""
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError as error:
        raise SystemExit(f"the provider URL {url!r} has an invalid port: {error}") from None
    host = check_host(parts.hostname or "")
    return host if port in (None, DEFAULT_PORTS.get(parts.scheme)) else f"{host}_{port}"


def round_resources(models: list[str | dict], providers: dict[str, dict]) -> tuple[str, ...]:
    """Return the resources a round's models need, sorted and without repeats.

    A model served by the Claude login needs `anthropic`, and one served by `--provider-url` its
    provider's resource; a provider of a model the round does not run adds nothing.
    """
    needed = set()
    for item in models:
        model = item["model"] if isinstance(item, dict) else item
        backend = item.get("backend", "claude") if isinstance(item, dict) else "claude"
        needed.add("codex" if backend == "codex" else provider_resource(providers[model]["url"]) if model in providers else ANTHROPIC)
    return tuple(sorted(needed))


def lock_path(resource: str) -> Path:
    """Return a resource's lock file: `ROUND_LOCK` for `anthropic`, `rounds-<resource>.lock` beside
    it for any other.

    The path comes from `ROUND_LOCK` at every call, so a test that points it elsewhere never
    touches the live directory.
    """
    if resource == ANTHROPIC:
        return ROUND_LOCK
    host, _, port = resource.partition("_")
    if resource != check_host(host) and not re.fullmatch(r"[0-9]+", port):
        raise SystemExit(f"a round resource is a host, with or without _<port>, not {resource!r}")
    return ROUND_LOCK.with_name(f"rounds-{resource}.lock")


def take_locks(handles: list) -> int | None:
    """Take every lock without blocking, or none: return the index of one held elsewhere."""
    for number, handle in enumerate(handles):
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            for taken in handles[:number]:
                fcntl.flock(taken, fcntl.LOCK_UN)
            return number
    return None


@contextmanager
def round_lock(holder: str, wait: float = 0.0, resources: tuple[str, ...] = (ANTHROPIC,)):
    """Hold the round lock of every resource while the block runs, or exit naming who holds one.

    The kernel releases a `flock` when its holder exits, so a lock is never stale; a file's text
    only says who took it last. Each attempt takes every lock without blocking, in sorted order, or
    releases the ones it took and tries again after `LOCK_POLL`, until one deadline `wait` seconds
    after the first attempt. A round never holds one lock while it waits for another, and writes
    its text only once it holds them all, so a refused round leaves every file as it was.

    Two costs are accepted. A refused attempt holds a lock for microseconds, and an older runner's
    attempt or a probe that lands then finds it held and names the previous holder's text. A round
    that needs two resources can keep losing to rounds that need one of them; waits are bounded
    and rounds are few.
    """
    resources = sorted(set(resources))
    paths = [lock_path(resource) for resource in resources]
    ROUND_LOCK.parent.mkdir(parents=True, exist_ok=True)
    # Closing a file releases its lock, so every exit frees them all, an interrupted attempt too.
    with ExitStack() as stack:
        handles = [stack.enter_context(path.open("a+", encoding="utf-8")) for path in paths]
        deadline = time.monotonic() + wait
        while (blocked := take_locks(handles)) is not None:
            left = deadline - time.monotonic()
            if left <= 0:
                handles[blocked].seek(0)
                text = handles[blocked].read().strip()
                raise SystemExit(f"another round holds {paths[blocked]}: {text or 'holder unknown'}")
            time.sleep(min(LOCK_POLL, left))
        for handle in handles:
            handle.seek(0)
            handle.truncate()
            handle.write(f"{holder}, pid {os.getpid()}, since {now()}, for {', '.join(resources)}\n")
            handle.flush()
        yield


# The kernel's table of file locks; a test points it at a fake.
PROC_LOCKS = Path("/proc/locks")
LOCKED_FILE = re.compile(r"([0-9a-f]+):([0-9a-f]+):([0-9]+)")


def lock_identity(status: os.stat_result) -> tuple[int, int, int]:
    """Name a file as /proc/locks does: its device's major and minor numbers, then its inode."""
    return os.major(status.st_dev), os.minor(status.st_dev), status.st_ino


def held_files() -> set[tuple[int, int, int]] | None:
    """Return the files a process holds a lock on, named as `lock_identity` names them, or None
    when /proc/locks cannot be read.

    /proc/locks prints device numbers in hex, and marks with `->` a process waiting for a lock.
    """
    try:
        text = PROC_LOCKS.read_text(encoding="utf-8")
    except OSError:
        return None
    held = set()
    for line in text.splitlines():
        fields = line.split()
        if fields[1:2] == ["->"]:
            continue
        for field in fields:
            if found := LOCKED_FILE.fullmatch(field):
                held.add((int(found[1], 16), int(found[2], 16), int(found[3])))
                break
    return held


def lock_overlaps(
    resources: tuple[str, ...], start: dict[str, tuple[str, int]] | None = None
) -> tuple[list[str], dict[str, tuple[str, int]]]:
    """Describe the other round lock files for the log, and return each one's text and inode.

    Call it while holding the locks of `resources`. Without `start`, the lines are the round's start
    lines; given what those read, they are its end lines. A marker line counts the files, then each
    gets `others <start|end> <name> held=<yes|no|unknown> changed=<yes|no> holder=<text>`, the free
    text last. A file has changed when its text is not empty and differs from the text at the
    start, a file absent then counting as empty, or when its inode differs because it was deleted
    and recreated; this catches a round that ran within this one. A refused round writes nothing,
    so it changes nothing.

    `held` comes from /proc/locks, which is only read: taking another round's lock to test it, even
    briefly, could refuse that round's attempt. When /proc/locks cannot be read, or does not show
    one of this round's own locks, as on a filesystem whose device numbers it prints differently,
    every `held` is `unknown`. It lists only the locks of this PID namespace, so a round started in
    a sandbox sees the others as free.
    """
    own = [lock_path(resource) for resource in resources]
    held = held_files()
    mine = set()
    for path in own:
        try:
            mine.add(lock_identity(path.stat()))
        except FileNotFoundError:
            continue
    if held is not None and not mine & held:
        held = None
    found, names = {}, {path.name for path in own}
    for path in sorted(ROUND_LOCK.parent.glob("rounds*.lock")):
        if path.name in names:
            continue
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                found[path.name] = (handle.read(), lock_identity(os.fstat(handle.fileno())))
        except FileNotFoundError:
            continue
    phase = "start" if start is None else "end"
    lines = [f"others {phase}: {len(found)} files"]
    for name, (text, identity) in found.items():
        state = "unknown" if held is None else "yes" if identity in held else "no"
        before, inode = (start or {}).get(name, ("", None))
        rewritten = bool(text.strip()) and text.strip() != before.strip()
        changed = start is not None and (rewritten or inode not in (None, identity[2]))
        fields = f"held={state} changed={'yes' if changed else 'no'}"
        lines.append(f"others {phase} {name} {fields} holder={' '.join(text.split())}")
    return lines, {name: (text, identity[2]) for name, (text, identity) in found.items()}


def log_overlaps(
    round_dir: Path, resources: tuple[str, ...], start: dict[str, tuple[str, int]] | None = None
) -> dict[str, tuple[str, int]]:
    """Append the lines of `lock_overlaps` to the round's log.txt, and return what they read."""
    lines, seen = lock_overlaps(resources, start)
    with round_paths(round_dir)["log.txt"].open("a", encoding="utf-8") as log:
        log.write("".join(f"{line}\n" for line in lines))
    return seen


def overlap_note(log: str) -> str | None:
    """Say whether a round overlapped another, from the `others` lines of its log.

    A line that shows another lock held or changed says it did. A line that says `unknown`, or a
    start marker with no end marker after it, as when the runner was killed, leaves it unknown. A
    log of an older runner has no such lines and gets no note.
    """
    overlapped = unknown = started = False
    for line in log.splitlines():
        if marker := re.fullmatch(r"others (start|end): [0-9]+ files", line):
            unknown |= started and marker[1] == "start"
            started = marker[1] == "start"
        elif other := re.match(r"others (?:start|end) \S+ held=(\w+) changed=(\w+) ", line):
            overlapped |= "yes" in (other[1], other[2])
            unknown |= other[1] == "unknown"
    if overlapped:
        return "Overlapped with another round: its minutes are not comparable."
    return "Overlap unknown." if unknown or started else None


# Every tool an audit may have. Agent starts subagents for the skill's passes.
AUDIT_TOOLS = ("Bash", "Read", "Grep", "Glob", "Agent")


def claude_command(
    prompt: str, model: str, directories: list[Path], settings: str | None = None
) -> list[str]:
    """Return the audit command.

    Only user settings load, with hooks off, so the audited repository's own agent settings,
    hooks, skills, and agents never load; the effort is fixed rather than inherited. A run served by
    another provider passes the settings file of `provider_launch`, which also turns hooks off.

    The audit has only the tools in `AUDIT_TOOLS` (`--tools`), which its subagents inherit, so it
    cannot list or message other sessions, schedule work, or start workflows; the web and
    file-editing tools stay disallowed as well. It is still not confined. Bash is allowed without a
    pattern, and this command sets neither a permission mode nor a sandbox (the user settings it
    loads could), so a shell command runs with the rights of the user who started the runner: it
    can read every file that user can read, and it can still write files. What keeps an audit in its
    repository is the prompt's instruction; afterwards `summarize` verifies the prepared repository
    and lists the home paths that tool calls name in full.
    """
    return [
        *("claude", "-p", prompt, "--model", model, "--effort", "high"),
        *(item for directory in directories for item in ("--add-dir", str(directory))),
        *("--tools", *AUDIT_TOOLS),
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
    return {
        "tools": tools,
        "tokens_written": sum(m.get("cacheCreationInputTokens") or 0 for m in models),
        "tokens_read": sum(m.get("cacheReadInputTokens") or 0 for m in models),
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
    names += ("hosted",)
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


def export_catalog(revision: str) -> Path:
    """Extract only the catalog files at a revision, for the catalog-only level."""
    archive = repository_git("archive", "--format=tar", f"{revision}:{SKILL}/references")
    catalog = Path(tempfile.mkdtemp(prefix="catalog."))
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        members = [m for m in tar.getmembers() if re.fullmatch(r"criteria(-[a-z]+)?\.md", m.name)]
        tar.extractall(catalog, members=members, filter="data")
    return catalog


def job_level(data: dict, job: dict) -> str:
    return job.get("level") or data.get("level") or "full"


def job_skill(data: dict, job: dict) -> str:
    """Return the skill a job audits with; plans before per-run revisions kept one skill."""
    return job.get("skill") or data.get("skill") or ""


def job_material(data: dict, job: dict) -> Path | None:
    """Return the directory a job's level gives the agent: the skill, the catalog, or nothing."""
    level = job_level(data, job)
    if level in WITHOUT_CATALOG:
        return None
    return Path(job["catalog"] if level == "catalog" else job_skill(data, job))


def job_prompt(data: dict, job: dict) -> str:
    """Return a job's prompt: its level's, then where to read its snapshot of the hosted state."""
    prompt = PROMPTS[job_level(data, job)].format(path=job_material(data, job))
    hosted = job.get("hosted")
    return f"{prompt}\n\n{HOSTED_PROMPT.format(path=hosted)}" if hosted else prompt


def job_revision(data: dict, job: dict) -> str:
    return job.get("revision") or data["skill_commit"]


def skill_exports(data: dict) -> list[Path]:
    """Return the temporary directories that hold the round's skill and catalog exports."""
    skills = [Path(path).parent for path in (data.get("skills") or {"": data.get("skill")}).values() if path]
    return skills + [Path(path) for path in (data.get("catalogs") or {}).values()]


class HostError(Exception):
    """A GitHub API read that failed, with what `gh` said."""


def case_github(case: Path) -> tuple[str, str] | None:
    """Return the GitHub repository and pinned commit of a case whose `source.json` names one."""
    path = case / "source.json"
    source = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if "github" not in source:
        return None
    name, commit = source["github"], str(source.get("commit", ""))
    if not isinstance(name, str) or not GITHUB_NAME.fullmatch(name):
        raise SystemExit(f"`github` in {path} must be a repository's owner/name, not {name!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit(f"{path} must pin a full 40-character commit SHA")
    return name, commit


def gh_api(path: str):
    """Return one GitHub API response, read with the runner's `gh` login, or raise HostError."""
    try:
        result = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HostError(str(error)) from error
    if result.returncode:
        raise HostError(" ".join(result.stderr.split()) or f"gh exited with {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise HostError(f"gh returned no JSON: {error}") from error


def picked(value: dict, fields: tuple[str, ...]) -> dict:
    return {field: value.get(field) for field in fields}


def without_links(value):
    """Return a JSON value without the API's links and node IDs, at every depth."""
    if isinstance(value, dict):
        return {
            key: without_links(item)
            for key, item in value.items()
            if key not in ("url", "node_id") and not key.endswith("_url")
        }
    return [without_links(item) for item in value] if isinstance(value, list) else value


def hosted_state(repository: str, commit: str) -> dict:
    """Read a GitHub repository's state for a pinned commit with `gh api`, as audits use it.

    The snapshot holds the repository's default branch, visibility, and archive flag; the check
    runs, Actions runs, and commit statuses on the commit, each list with its total count; and the
    default branch's protection and rules, without the API's links. Issues, pull requests, alerts,
    and other settings stay out: the snapshot covers what audits of prepared repositories could
    not read (runs 188 and 189), and issues would change what counts as known. An endpoint that
    fails is recorded as `{"error": message}` and the others are still read, since a 404 such as
    "Branch not protected" is information.
    """
    base = f"repos/{repository}"
    state: dict = {"github": repository, "commit": commit, "taken_at": now()}

    def read(key: str, path: str, keep) -> None:
        try:
            state[key] = keep(gh_api(path))
        except HostError as error:
            state[key] = {"error": str(error)}

    def listed(key: str, fields: tuple[str, ...], *summary: str):
        def keep(response: dict) -> dict:
            items = [picked(item, fields) for item in response.get(key) or []]
            # GitHub gives a commit with no statuses the combined state "pending", which an audit
            # would read as CI still running, so a summary is kept only for a list with items.
            kept = summary if response.get("total_count") else ()
            return picked(response, ("total_count", *kept)) | {key: items}

        return keep

    read("repository", base, lambda r: picked(r, ("default_branch", "visibility", "archived")))
    checks = f"{base}/commits/{commit}/check-runs?per_page=100"
    read("check_runs", checks, listed("check_runs", CHECK_RUN_FIELDS))
    runs = f"{base}/actions/runs?head_sha={commit}&per_page=100"
    read("workflow_runs", runs, listed("workflow_runs", WORKFLOW_RUN_FIELDS))
    statuses = f"{base}/commits/{commit}/status?per_page=100"
    read("commit_status", statuses, listed("statuses", ("context", "state"), "state"))
    default = state["repository"].get("default_branch")
    branch = quote(default) if default else None
    for key, path in (
        ("branch_protection", f"{base}/branches/{branch}/protection"),
        ("branch_rules", f"{base}/rules/branches/{branch}"),
    ):
        if branch:
            read(key, path, without_links)
        else:
            state[key] = {"error": "not read: the default branch is unknown"}
    return state


def write_hosted_state(case: Path, hosted: Path) -> Path | None:
    """Write `<hosted>/<case name>.json` for a case whose `source.json` has `github`."""
    github = case_github(case)
    if not github:
        return None
    state = hosted_state(*github)
    hosted.mkdir(exist_ok=True)
    path = hosted / f"{case.name}.json"
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    failed = [key for key, value in state.items() if isinstance(value, dict) and "error" in value]
    if failed:
        print(f"{case.name}: gh api failed for {', '.join(failed)}; see {path}")
    return path


def plan(round_dir: Path, runs: list[tuple], cases: list[str], revision: str) -> dict:
    """Export each skill revision and prepare a fresh repository for every run of every case.

    A run may name its own revision, so a control and a candidate share one round. Jobs are listed
    case by case with every run of a case together, so the arms run side by side in time instead
    of hours apart, when the service may have changed. A case whose `source.json` names its
    GitHub repository has its hosted state read once (`hosted_state`), and each of its jobs gets a
    copy beside the prepared repository, never inside it.
    """
    check_round_dir(round_dir)
    paths = round_paths(round_dir)
    if paths["plan.json"].exists():
        raise SystemExit(f"{round_dir} already has a plan")
    for case in cases:
        if not (case_path(case) / "expected.json").is_file():
            raise SystemExit(f"unknown case: {case}")
        case_github(case_path(case))
    names = [case_path(case).name for case in cases]
    if len(names) != len(set(names)) or len({r[0] for r in runs}) != len(runs):
        raise SystemExit("duplicate run artifact labels")
    specs = []
    for number, model, *rest in runs:
        backend, model = parse_backend(model, rest[2] if len(rest) > 2 else None)
        wanted = rest[0] if rest and rest[0] else revision
        level = rest[1] if len(rest) > 1 and rest[1] else "full"
        if level not in PROMPTS:
            raise SystemExit(f"unknown level {level!r}; use one of {', '.join(PROMPTS)}")
        # A tag names its commit: an annotated tag is an object of its own.
        commit = repository_git("rev-parse", "--short", f"{wanted}^{{commit}}").decode().strip()
        specs.append((number, model, commit, level, backend))
    for name in ("streams", "reports"):
        paths[name].mkdir(parents=True, exist_ok=True)
    listing = sorted(os.listdir(tempfile.gettempdir()))
    paths["tmp-before.txt"].write_text("\n".join(listing) + "\n", encoding="utf-8")
    wanted_skills = dict.fromkeys(s[2] for s in specs if s[3] == "full")
    wanted_catalogs = dict.fromkeys(s[2] for s in specs if s[3] == "catalog")
    skills = {commit: str(export_skill(commit)) for commit in wanted_skills}
    catalogs = {commit: str(export_catalog(commit)) for commit in wanted_catalogs}
    jobs = []
    for case in cases:
        hosted = write_hosted_state(case_path(case), paths["hosted"])
        for run, model, commit, level, backend in specs:
            directory = Path(tempfile.mkdtemp(prefix="audit."))
            name = case_path(case).name
            prepare(case_path(case), directory / name)
            job = {"run": run, "model": model, "case": case, "name": name, "dir": str(directory)}
            job |= {"revision": commit, "level": level, "backend": backend}
            job |= {"skill": skills[commit]} if level == "full" else {}
            job |= {"catalog": catalogs[commit]} if level == "catalog" else {}
            if hosted:
                job["hosted"] = str(shutil.copyfile(hosted, directory / "hosted-state.json"))
            jobs.append(job)
    revisions = ", ".join(dict.fromkeys(s[2] for s in specs))
    levels = ", ".join(dict.fromkeys(s[3] for s in specs))
    data = {"created": now(), "skill_commit": revisions, "skills": skills, "catalogs": catalogs}
    data["level"] = levels
    data["jobs"] = jobs
    paths["plan.json"].write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


HOSTING_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


# Rounds on different providers may run at once: a CLI that updated itself during a round would run
# its audits on two versions and leave cli-version.txt wrong. Every `claude` the runner starts has
# automatic updates off; a provider's runs get the same setting from PROVIDER_SETTINGS.
NO_UPDATES = {"DISABLE_AUTOUPDATER": "1"}


def audit_environment(round_dir: Path) -> dict[str, str]:
    """Return the audit's environment, with no GitHub CLI login and no automatic updates.

    A prepared repository is not the hosted one: a rewritten history has no hosted runs, and live
    hosting state changes between rounds. With an empty `gh` configuration and no tokens, an audit
    reports remote settings as unverified, the same way in every round, unless its case has a
    snapshot of the hosted state that `plan` read once for every run (`hosted_state`).
    """
    config = round_dir / "gh-config"
    config.mkdir(exist_ok=True)
    clean = {name: value for name, value in os.environ.items() if name not in HOSTING_TOKENS}
    return clean | {"GH_CONFIG_DIR": str(config)} | NO_UPDATES


# Seconds between SIGTERM and SIGKILL when a process group is stopped.
GRACE = 30
EXIT_GRACE = 5


def signal_group(process: subprocess.Popen, number: int) -> None:
    try:
        os.killpg(process.pid, number)
    except ProcessLookupError:
        pass


def stop_groups(processes: list[subprocess.Popen], grace: float | None = None) -> None:
    """End every group, escalating even when its leader has already exited."""
    for process in processes:
        signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + (GRACE if grace is None else grace)
    while time.monotonic() < deadline:
        alive = False
        for process in processes:
            process.poll()
            try:
                os.killpg(process.pid, 0)
                alive = True
            except ProcessLookupError:
                pass
        if not alive:
            break
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    for process in processes:
        signal_group(process, signal.SIGKILL)
        process.wait()


class Running:
    """The commands that run now, so that a stop signal can end their process groups.

    Once `stopped` is set, no command starts.
    """

    def __init__(self) -> None:
        self.processes: set[subprocess.Popen] = set()
        self.stopped, self.lock = threading.Event(), threading.Lock()

    def stop(self) -> int:
        """Refuse new commands, end the running ones, and return how many were running."""
        self.stopped.set()
        with self.lock:
            live = list(self.processes)
        stop_groups(live)
        return len(live)


class Interrupted(BaseException):
    """Raised in the main thread by the handler of a stop signal; the argument is the signal."""


def run_command(
    command: list[str],
    cwd: Path,
    stdout: Path,
    stderr: Path,
    timeout: float,
    environment: dict[str, str] | None = None,
    running: Running | None = None,
    stdin=None,
    capture_stdout: list[str] | None = None,
) -> int:
    """Run in a new session and stop the whole process group on timeout, grandchildren included.

    The group is registered in `running`, so `Running.stop` ends it too; after that, nothing starts.
    """
    running = running or Running()
    with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
        with running.lock:
            if running.stopped.is_set():
                return -signal.SIGTERM
            process = subprocess.Popen(
                command, cwd=cwd, env=environment, stdout=subprocess.PIPE if capture_stdout is not None else out,
                stderr=err, stdin=stdin, start_new_session=True
            )
            running.processes.add(process)
        cleaned = False
        try:
            if capture_stdout is not None:
                output, _ = process.communicate(timeout=timeout)
                capture_stdout.append(output.decode("utf-8", errors="replace"))
                return process.returncode
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_groups([process])
            cleaned = True
            err.write(f"\nstopped after {timeout:.0f} seconds\n")
            return -1
        finally:
            if not cleaned:
                stop_groups([process], EXIT_GRACE)
            if process.stdout is not None:
                process.stdout.close()
            with running.lock:
                running.processes.discard(process)


# Host basics a run of another provider keeps; no Anthropic or Claude Code variable of the parent.
HOST_VARIABLES = (
    *("HOME", "USER", "LOGNAME", "PATH", "LANG", "LC_ALL", "TMPDIR", "TERM"),
    *("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"),
    *("UV_CACHE_DIR", "PNPM_HOME", "CARGO_HOME", "RUSTUP_HOME", "NVM_DIR"),
    *("SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS"),
)
PROVIDER_SETTINGS = {
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_NO_MODEL_FALLBACK": "1",
    "DISABLE_AUTOUPDATER": "1",
    "API_TIMEOUT_MS": "3000000",
    # A one-million-token window makes Claude Code ask for `model[1m]`, which providers refuse.
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "200000",
}


def provider_launch(provider: dict, model: str, config_dir: Path) -> tuple[dict[str, str], Path]:
    """Return the environment and settings file of a run served by another provider.

    The run gets only host basics, its own Claude Code configuration directory, so the CLI does
    not use the user's Claude login, and the provider's base URL. Every model alias names the
    model, so no internal call asks for another one. The key reaches the CLI only through an
    `apiKeyHelper` that reads the key file: the environment holds no key, and the settings file
    holds the command, not the key.

    This does not hide the key from the audit, which runs as the same user with the Bash tool and
    no sandbox (see `claude_command`). The settings deny `Read` on the key and its
    directory, with `//` paths: Claude Code anchors a path with a single leading `/` at the
    directory of the settings file, so `//` is what names the filesystem root. These rules stop
    Claude Code's Read tool and the file commands it recognizes in a Bash command, such as `cat`;
    they do not stop a command that reads without naming the file, or a script that opens it. The
    audit is also limited by the prompt's instruction and by the check of its tool calls
    afterwards, which sees only paths written in full.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    config_dir.chmod(0o700)
    environment = {name: os.environ[name] for name in HOST_VARIABLES if name in os.environ}
    environment |= PROVIDER_SETTINGS | {
        "CLAUDE_CONFIG_DIR": str(config_dir),
        "ANTHROPIC_BASE_URL": provider["url"],
        "CLAUDE_CODE_SUBAGENT_MODEL": model,
    }
    environment |= {f"ANTHROPIC_DEFAULT_{alias}_MODEL": model for alias in ("OPUS", "SONNET", "HAIKU", "FABLE")}
    key = provider["key"]
    deny = [f"Read(/{key})", f"Read(/{key.parent}/**)"]
    settings = {
        "apiKeyHelper": f"cat {shlex.quote(str(key))}",
        "permissions": {"deny": deny},
        "disableAllHooks": True,
    }
    path = config_dir / "run-settings.json"
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return environment, path


def parse_providers(urls: list[str], keys: list[str]) -> dict[str, dict]:
    """Pair each provider model's base URL with its key file."""
    def pairs(values: list[str], flag: str) -> dict[str, str]:
        found = {}
        for value in values:
            model, _, rest = value.partition("=")
            if not model or not rest:
                raise SystemExit(f"{flag} takes MODEL=VALUE, not {value!r}")
            found[model] = rest
        return found

    url, key = pairs(urls, "--provider-url"), pairs(keys, "--provider-key")
    if set(url) != set(key):
        raise SystemExit("Each provider model needs both --provider-url and --provider-key")
    providers = {}
    for model in url:
        path = Path(key[model]).expanduser().resolve()
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise SystemExit(f"The key file must exist and be readable only by you (mode 600): {path}")
        providers[model] = {"url": url[model], "key": path}
    return providers


def init_key_source(stream: Path) -> str | None:
    for line in stream.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            return event.get("apiKeySource")
    return None


class StartSpacer:
    """Space audit launches, so the first one writes the cache of the prompt prefix they share and
    the next ones read it instead of each writing its own copy."""

    def __init__(self, interval: float, clock=time.monotonic, sleep=time.sleep) -> None:
        self.interval, self.clock, self.sleep = interval, clock, sleep
        self.next, self.lock = 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = self.clock()
            start = max(now, self.next)
            self.next = start + self.interval
        if start > now:
            self.sleep(start - now)


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


def warm_up(round_dir: Path, models: list[str], providers: dict[str, dict], running: Running | None = None) -> None:
    """Make one short call per model, one at a time, before any parallel run.

    Parallel runs that find an expired login race to refresh it, and most fail before their first
    tool call; a serial call refreshes it first. It also stops the round when the CLI does not
    serve a requested model, before any audit spends anything.
    """
    for model in models:
        output = round_dir / f"warmup-{model}.json"
        provider = providers.get(model)
        command = ["claude", "-p", "Reply with the single word OK.", "--model", model]
        command += ["--setting-sources", "user", "--strict-mcp-config", "--no-session-persistence"]
        environment = {**os.environ, **NO_UPDATES}
        if provider:
            environment, settings = provider_launch(provider, model, round_dir / "providers" / f"warmup-{model}")
            command += ["--settings", str(settings)]
        code = run_command([*command, "--output-format", "json"], Path(tempfile.gettempdir()),
            output, output.with_suffix(".stderr.txt"), 300, environment, running)
        try:
            event = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            event = {"is_error": True}
        if code or event.get("is_error") or not ran_model([event], model):
            raise SystemExit(f"warm-up failed for {model}; see {output}")
        print(f"warm-up ok: {model}", flush=True)


def repository_clean(repo: Path) -> bool:
    try:
        status = git_at(repo / ".git", "status", "--porcelain", "--ignored", work_tree=repo)
    except (OSError, subprocess.CalledProcessError):
        return False
    return not status


def job_label(job: dict) -> str:
    return f"run{job['run']}-{job['name']}"


def record_identity(data: dict, job: dict) -> dict:
    return {"backend": job.get("backend", "claude"), "model": job["model"],
            "revision": job_revision(data, job), "case": job["case"],
            "prompt_sha256": hashlib.sha256(job_prompt(data, job).encode()).hexdigest()}


def record_path(round_dir: Path, job: dict) -> Path:
    return round_dir / "streams" / f"{job_label(job)}.run.json"


def read_record(round_dir: Path, job: dict) -> dict:
    try:
        value = json.loads(record_path(round_dir, job).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_record(round_dir: Path, data: dict, job: dict, reasons: list[str], status: str | None = None, **details) -> dict:
    record = record_identity(data, job) | {"started": None, "ended": now(), "seconds": None,
        "queue_seconds": None, "manifest_sha256": None} | details
    record |= {"status": status or ("invalid" if reasons else "valid"), "reasons": reasons}
    path = record_path(round_dir, job)
    serialized = json.dumps(record, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(serialized)
        if path.exists():
            number = 1
            while path.with_name(f"{path.stem}.{number}.json").exists():
                number += 1
            shutil.copyfile(path, path.with_name(f"{path.stem}.{number}.json"))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return record


def skipped_job(round_dir: Path, data: dict, job: dict, reason: str, queue_seconds: float | None = None) -> str:
    if not record_path(round_dir, job).exists():
        write_record(round_dir, data, job, [reason], status="skipped", queue_seconds=queue_seconds)
    return f"{job_label(job)}: skipped, {reason}"


def legacy_job(round_dir: Path, job: dict) -> bool:
    record = read_record(round_dir, job)
    return "backend" not in job and (not record_path(round_dir, job).exists() or record.get("status") == "legacy") and (
        round_dir / "reports" / f"{job_label(job)}.md"
    ).is_file() and repository_clean(Path(job["dir"]) / job["name"])


def artifacts_match(round_dir: Path, job: dict, record: dict) -> bool:
    stream = round_dir / "streams" / f"{job_label(job)}.jsonl"
    report = round_dir / "reports" / f"{job_label(job)}.md"
    if job.get("backend", "claude") == "codex":
        return codex_backend.artifacts_match(stream, record, report)
    return report.is_file() and record.get("report_sha256") == sha256(report)


def changed_artifacts(round_dir: Path, data: dict, job: dict) -> bool:
    record = read_record(round_dir, job)
    reason = "artifacts changed after the run"
    if record.get("status") == "valid" and not artifacts_match(round_dir, job, record):
        details = {key: value for key, value in record.items() if key not in ("status", "reasons")}
        write_record(round_dir, data, job, [reason], **details)
        return True
    return reason in record.get("reasons", [])


def resumable(round_dir: Path, data: dict, job: dict) -> bool:
    record = read_record(round_dir, job)
    return (record.get("status") == "valid"
            and all(record.get(k) == v for k, v in record_identity(data, job).items())
            and repository_clean(Path(job["dir"]) / job["name"])
            and artifacts_match(round_dir, job, record))


def audit(round_dir: Path, data: dict, job: dict, launch: dict, queued: float | None = None) -> str:
    """Run one audit and persist its validity independently of the scorer's result."""
    if not (Path(job["dir"]) / job["name"]).is_dir():
        return f"{job_label(job)}: not launched, prepared repository removed; record unchanged"
    if changed_artifacts(round_dir, data, job):
        return f"{job_label(job)}: artifacts changed after the run; delete {record_path(round_dir, job)} to run it again"
    if resumable(round_dir, data, job):
        return f"{job_label(job)}: skipped, valid record exists"
    if legacy_job(round_dir, job):
        if not read_record(round_dir, job):
            write_record(round_dir, data, job, [], status="legacy")
        return f"{job_label(job)}: legacy, unverified"
    queued = queued if queued is not None else time.monotonic()
    if job.get("backend", "claude") == "codex":
        with launch["codex_turn"]:
            return audit_ready(round_dir, data, job, launch, time.monotonic() - queued)
    return audit_ready(round_dir, data, job, launch, 0.0)


def audit_ready(round_dir: Path, data: dict, job: dict, launch: dict, queue_seconds: float) -> str:
    paths, label = round_paths(round_dir), job_label(job)
    repo = Path(job["dir"]) / job["name"]
    report = paths["reports"] / f"{label}.md"
    codex = job.get("backend", "claude") == "codex"
    # These checks are deliberately inside the Codex semaphore: queued jobs must recheck them.
    if launch["running"].stopped.is_set():
        return skipped_job(round_dir, data, job, "stopped", queue_seconds)
    if codex and launch["codex_stop"].is_set():
        return skipped_job(round_dir, data, job, launch["codex_stop_reason"], queue_seconds)
    if not launch["spending"].allows():
        return skipped_job(round_dir, data, job, "budget reached", queue_seconds)
    if not repository_clean(repo):
        return skipped_job(round_dir, data, job, "the prepared repository is missing or changed", queue_seconds)
    provider = launch["providers"].get(job["model"])
    stream, stderr = paths["streams"] / f"{label}.jsonl", paths["streams"] / f"{label}.stderr.txt"
    launch["starts"].wait()
    if not launch["spending"].allows():
        return skipped_job(round_dir, data, job, "budget reached", queue_seconds)
    if launch["running"].stopped.is_set():
        return skipped_job(round_dir, data, job, "stopped", queue_seconds)
    if codex and launch["codex_stop"].is_set():
        return skipped_job(round_dir, data, job, launch["codex_stop_reason"], queue_seconds)
    if report.exists():
        record = read_record(round_dir, job)
        details = {key: value for key, value in record.items() if key not in ("status", "reasons")}
        write_record(round_dir, data, job, ["relaunch started"], **details)
        report.unlink()
    started, tick = now(), time.monotonic()
    result, text, reasons, code = {}, "", [], None
    report_sha256 = None
    try:
        if codex:
            result = codex_backend.run_audit(repo, stream, stderr, job["model"], job_prompt(data, job),
                launch["timeout"], codex_backend.environment(round_dir, HOST_VARIABLES), launch["running"], run_command)
            if result["stop"]:
                launch["codex_stop_reason"] = result["stop"]
                launch["codex_stop"].set()
            text = result.pop("report")
            result.pop("stop")
            reasons = result.pop("reasons")
            code = result["exit_code"]
            message = f"{label}: exit {code}" + (f", {', '.join(reasons)}" if reasons else "")
        else:
            material = job_material(data, job)
            environment, settings = audit_environment(round_dir), None
            if provider:
                environment, settings = provider_launch(provider, job["model"], round_dir / "providers" / label)
                environment |= {"GH_CONFIG_DIR": audit_environment(round_dir)["GH_CONFIG_DIR"]}
            command = claude_command(job_prompt(data, job), job["model"], [material] if material else [], str(settings) if settings else None)
            started, tick = now(), time.monotonic()
            results = []
            for attempt in range(1, ATTEMPTS + 1):
                code = run_command(command, repo, stream, stderr, launch["timeout"], environment, launch["running"])
                results = stream_results(stream)
                if launch["running"].stopped.is_set() or not login_failed(results) or attempt == ATTEMPTS:
                    break
                stream.rename(paths["streams"] / f"{label}.login-failure-{attempt}.jsonl")
                launch["running"].stopped.wait(random.uniform(*launch["pause"]))
            launch["spending"].add(max((r.get("total_cost_usd") or 0 for r in results), default=0))
            text, reasons = report_text(results), []
            if code:
                reasons.append("timeout" if code == -1 else f"nonzero exit {code}")
            if not results:
                reasons.append("no turn end")
            if any(r.get("is_error") for r in results) or login_failed(results):
                reasons.append("error")
            if not text.strip():
                reasons.append("no report")
            if not ran_model(results, job["model"]):
                reasons.append("MODEL MISMATCH")
            source = init_key_source(stream) if provider else None
            if provider and source != "apiKeyHelper":
                reasons.append(f"KEY SOURCE {source}")
            used = sorted({name for r in results for name in r.get("modelUsage") or {}})
            message = f"{label}: exit {code}, models {','.join(used) or 'none'} {' '.join(reasons)}".rstrip()
            result = {"started": started, "ended": now(), "seconds": time.monotonic() - tick,
                      "exit_code": code, "usage": stream_usage(stream, results)}
        if launch["running"].stopped.is_set():
            reasons.append("stopped")
        elif text.strip():
            report.write_text(text, encoding="utf-8")
        if not repository_clean(repo) or repository_problems(case_path(job["case"]), repo):
            reasons.append("changed repository")
        report_sha256 = sha256(report) if report.exists() else None
    except Exception as error:
        reason = f"runner error: {type(error).__name__}"
        reasons.append(reason)
        result = {"started": started, "ended": now(), "seconds": time.monotonic() - tick, "exit_code": code} | result
        if "usage" not in result:
            if codex:
                threads = {str(path): codex_backend.session_info(path) for path in codex_backend.copied_sessions(stream)}
                result["usage"] = codex_backend.session_usage(threads, False)
                result["usage_lower_bound"] = codex_backend.session_usage(threads, False, lower_bound=True)
            elif stream.is_file():
                results = [event for event in codex_backend.records(stream) if event.get("type") == "result"]
                result["usage"] = stream_usage(stream, results) if results else {}
        result.pop("report", None)
        result.pop("stop", None)
        result.pop("reasons", None)
        message = f"{label}: invalid, {reason}"
    write_record(round_dir, data, job, reasons, queue_seconds=queue_seconds,
                 report_sha256=report_sha256, **result)
    return message


def run(
    round_dir: Path,
    jobs: int,
    timeout: float,
    budget: float,
    pause: tuple[int, int] = (20, 60),
    providers: dict[str, dict] | None = None,
    stagger: float = 0.0,
    lock_wait: float = 0.0,
) -> int:
    """Run every planned audit; return 1 when any job is neither valid nor legacy.

    `providers` maps a model served by another provider to its base URL and key file. SIGTERM or
    SIGINT stops the process group of every running audit, starts no other, and returns 128 plus
    the signal number; the handlers are restored afterwards. The whole round, warm-up included,
    holds the lock of every resource its models need (`round_resources`), waiting for them at most
    `lock_wait` seconds.

    Rounds of other providers may run meanwhile on the same host, so log.txt describes the other
    rounds' locks right after this round takes its own and again before it releases them, also
    when it stops early, and `summarize` marks a round that overlapped another. The probe,
    `lock_overlaps`, sees only the locks of this PID namespace.
    """
    data = json.loads(round_paths(round_dir)["plan.json"].read_text(encoding="utf-8"))
    providers = providers or {}
    resources = round_resources(data["jobs"], providers)
    with round_lock(f"claude_rounds run {round_dir.resolve()}", lock_wait, resources):
        start = log_overlaps(round_dir, resources)
        try:
            return run_audits(round_dir, jobs, timeout, budget, pause, providers, stagger, resources)
        finally:
            # Still under the locks: the probe looks for them, and once released every `held` is unknown.
            log_overlaps(round_dir, resources, start)


def run_audits(
    round_dir: Path,
    jobs: int,
    timeout: float,
    budget: float,
    pause: tuple[int, int],
    providers: dict[str, dict] | None,
    stagger: float,
    resources: tuple[str, ...] = (ANTHROPIC,),
) -> int:
    """The body of `run`, under the locks of `resources`."""
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    providers = providers or {}
    running = Running()
    launch = {"timeout": timeout, "pause": pause, "providers": providers, "spending": Spending(budget)}
    launch |= {"starts": StartSpacer(stagger, sleep=running.stopped.wait), "running": running, "codex_turn": threading.Semaphore(1),
               "codex_stop": threading.Event(), "codex_stop_reason": "stopped"}
    pending = []
    for job in data["jobs"]:
        line = None
        if not (Path(job["dir"]) / job["name"]).is_dir():
            line = f"{job_label(job)}: not launched, prepared repository removed; record unchanged"
        elif changed_artifacts(round_dir, data, job):
            line = f"{job_label(job)}: artifacts changed after the run; delete {record_path(round_dir, job)} to run it again"
        elif legacy_job(round_dir, job):
            if not read_record(round_dir, job):
                write_record(round_dir, data, job, [], status="legacy")
        elif not resumable(round_dir, data, job):
            record = read_record(round_dir, job)
            if (record.get("status") == "valid"
                    and any(record.get(k) != v for k, v in record_identity(data, job).items())):
                details = {key: value for key, value in record.items() if key not in ("status", "reasons")}
                write_record(round_dir, data, job, ["plan changed after the run"], **details)
            pending.append(job)
        if line:
            with paths["log.txt"].open("a", encoding="utf-8") as log:
                log.write(line + "\n")
            print(line, flush=True)
    if not pending:
        return int(any(read_record(round_dir, job).get("status") not in ("valid", "legacy") for job in data["jobs"]))

    def interrupt(number: int, frame) -> None:
        if not running.stopped.is_set():
            running.stopped.set()
            raise Interrupted(number)

    interrupted = 0
    previous = {number: signal.signal(number, interrupt) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        updates_off = {**os.environ, **NO_UPDATES}
        claude_models = sorted({j["model"] for j in pending if j.get("backend", "claude") == "claude"})
        codex_models = sorted({j["model"] for j in pending if j.get("backend") == "codex"})
        versions = []
        if any(j.get("backend", "claude") == "claude" and j["model"] not in providers for j in pending):
            auth_output = []
            status = run_command(["claude", "auth", "status"], round_dir, Path(os.devnull),
                Path(os.devnull), 60, updates_off, running, capture_stdout=auth_output)
            (round_dir / "auth-status.json").write_text(json.dumps({"exit_code": status}) + "\n", encoding="utf-8")
            logged_in = any('"loggedIn": true' in output for output in auth_output)
            auth_output.clear()
            if status or not logged_in:
                raise SystemExit("claude is not logged in here: run 'claude auth login' first")
        for backend, models in (("claude", claude_models), ("codex", codex_models)):
            if not models:
                continue
            environment = codex_backend.environment(round_dir, HOST_VARIABLES) if backend == "codex" else updates_off
            if backend == "codex":
                status = run_command(["codex", "login", "status"], round_dir, Path(os.devnull),
                    Path(os.devnull), 60, environment, running, stdin=subprocess.DEVNULL)
                (round_dir / "codex-login.json").write_text(json.dumps({"exit_code": status}) + "\n", encoding="utf-8")
                if status:
                    raise SystemExit("codex is not logged in here: run 'codex login' first")
            output = round_dir / ("codex-cli-version.txt" if backend == "codex" else "cli-version.txt")
            code = run_command([backend, "--version"], round_dir, output, output.with_suffix(".stderr.txt"),
                60, environment, running, stdin=subprocess.DEVNULL)
            if code:
                raise SystemExit(f"{backend} version check failed")
            versions.append(output.read_text(encoding="utf-8").strip())
        if claude_models:
            warm_up(round_dir, claude_models, providers, running)
        if codex_models:
            codex_backend.warm_up(round_dir, codex_models, HOST_VARIABLES, run_command, running)
        with paths["log.txt"].open("a", encoding="utf-8") as log:
            log.write(f"start {now()} {', '.join(versions)}, budget USD {budget:g}\n")
            with ThreadPoolExecutor(max_workers=jobs) as pool, ThreadPoolExecutor(max_workers=1) as codex_pool:
                try:
                    futures = {(codex_pool if job.get("backend") == "codex" else pool).submit(
                        audit, round_dir, data, job, launch, time.monotonic()): job for job in pending}
                    for future in as_completed(futures):
                        job = futures[future]
                        try:
                            line = future.result()
                        except Exception as error:
                            # Persist a status for this job and continue collecting the others.
                            reason = f"runner error: {type(error).__name__}"
                            write_record(round_dir, data, job, [reason])
                            line = f"{job_label(job)}: invalid, {reason}"
                        log.write(line + "\n")
                        log.flush()
                        print(line, flush=True)
                except Interrupted as stop:
                    interrupted = stop.args[0]
                    pool.shutdown(wait=False, cancel_futures=True)
                    codex_pool.shutdown(wait=False, cancel_futures=True)
                    name, ended = signal.Signals(interrupted).name, running.stop()
                    log.write(f"stopped {now()} by {name}: {ended} running audits ended\n")
                    print(f"stopped by {name}: {ended} running audits ended", flush=True)
            log.write(f"end {now()}\n")
    except Interrupted as stop:
        interrupted = stop.args[0]
        running.stop()
    except BaseException:
        running.stop()
        for job in pending:
            skipped_job(round_dir, data, job, "preflight failed")
        raise
    finally:
        for job in pending:
            skipped_job(round_dir, data, job, "stopped" if interrupted else "not launched")
        for number, handler in previous.items():
            signal.signal(number, handler)
    if interrupted:
        return 128 + interrupted
    return int(any(read_record(round_dir, job).get("status") not in ("valid", "legacy") for job in data["jobs"]))


def outside_paths(stream: Path, allowed: list[Path]) -> list[str]:
    """List home or Windows paths in the run's tool calls outside its repository and the skill.

    Executables, such as an interpreter the run started, are left out, and so are search patterns
    that only look like paths and the files where the CLI keeps a long tool output for the run.
    """
    found = set()
    texts = codex_backend.diagnostic_texts(stream)
    for event in codex_backend.records(stream):
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        texts += [json.dumps(item.get("input")) for item in content if isinstance(item, dict)
                  and item.get("type") == "tool_use"] if isinstance(content, list) else []
    for text in texts:
        for match in HOME_PATH.findall(text):
            path = Path(match)
            if any(match == str(a) or match.startswith(f"{a}/") for a in allowed):
                continue
            if any(mark in match for mark in "|\\*") or "/.claude/projects/-tmp-audit" in match:
                continue
            try:
                executable = path.is_file() and os.access(path, os.X_OK)
            except OSError:
                executable = False
            if not executable:
                found.add(match)
    return sorted(found)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def round_date(paths: dict[str, Path], data: dict) -> date:
    """Return the day the round's audits started, in UTC: the first `start` line of log.txt.

    A round that was run in several sessions counts from its first, so a defect found later is not
    held against it. A plan that was never run gives the day it was planned.
    """
    log = paths["log.txt"].read_text(encoding="utf-8") if paths["log.txt"].exists() else ""
    started = re.search(r"^start (\d{4}-\d{2}-\d{2})T", log, re.M)
    return date.fromisoformat(started[1] if started else data["created"][:10])


def repository_problems(case: Path, repo: Path) -> list[str]:
    try:
        return verify(case, repo)
    except (OSError, subprocess.CalledProcessError):
        return ["prepared repository missing or unreadable"]


def add_metrics(job: dict, paths: dict[str, Path], totals: Counter) -> None:
    stream = paths["streams"] / f"{job_label(job)}.jsonl"
    record = read_record(paths["plan.json"].parent, job)
    totals["valid"] += int(record.get("status") == "valid")
    if job.get("backend") == "codex":
        metrics = record.get("usage", {}) | {"seconds": record.get("seconds")}
        totals["codex"] = 1
    else:
        results = stream_results(stream) if stream.exists() else []
        metrics = stream_usage(stream, results) if stream.exists() else {}
        if not results:
            metrics = {key: value if key == "tools" else None for key, value in metrics.items()}
        durations = [r["duration_ms"] for r in results if r.get("duration_ms") is not None]
        costs = [r["total_cost_usd"] for r in results if r.get("total_cost_usd") is not None]
        metrics |= {"seconds": sum(durations) / 1000 if durations else record.get("seconds"),
                    "cents": 100 * max(costs) if costs else None}
    for key, value in metrics.items():
        if value is not None:
            totals[key] += value
            totals[key + "_n"] += 1


def job_status(job: dict, data: dict, paths: dict[str, Path], changed: list[str]) -> str:
    record = read_record(paths["plan.json"].parent, job)
    if record:
        if record.get("status") == "legacy":
            return "legacy, unverified"
        if record.get("status") == "valid" and not artifacts_match(paths["plan.json"].parent, job, record):
            return "invalid: artifacts changed after the run"
        return record.get("status", "invalid") + (": " + ", ".join(record.get("reasons", [])) if record.get("reasons") else "")
    if legacy_job(paths["plan.json"].parent, job):
        return "legacy, unverified"
    return "unverified: no run record"


def repository_note(job: dict, changed: list[str]) -> list[str]:
    if not (Path(job["dir"]) / job["name"]).exists():
        return [f"{job_label(job)}: repository removed"]
    if changed:
        return [f"{job_label(job)}: the prepared repository changed: {'; '.join(changed[:5])}"]
    return []


def available_usage(job: dict, paths: dict[str, Path]) -> str:
    record = read_record(paths["plan.json"].parent, job)
    if record.get("status") in ("valid", "legacy"):
        return "—"
    partial = record.get("usage_lower_bound")
    usage = partial or record.get("usage") or {}
    labels = {"tokens_in": "input", "tokens_read": "cached input", "tokens_out": "output",
              "tokens_reasoning": "reasoning", "tokens_written": "cache writes",
              "tokens_uncached": "uncached input", "tools": "tool calls"}
    values = [f"{value:,} {labels[key]}" for key, value in usage.items() if key in labels and value is not None]
    return (("lower bound: " if partial else "") + ", ".join(values)) if values else "—"


def score_job(
    job: dict, data: dict, paths: dict[str, Path], repo: Path, totals: Counter, as_of: date
) -> dict:
    """Score one run's report and check its stream and prepared repository.

    A report of a level without the catalog has no criterion IDs: only its leaks and citations are
    checked here, and its gaps, defects, and priorities are scored by hand with the rules of
    evals/README.md. The defects count as of the round's date.
    """
    label, case = f"run{job['run']}-{job['name']}", case_path(job["case"])
    report, stream = paths["reports"] / f"{label}.md", paths["streams"] / f"{label}.jsonl"
    expected, result = score_report(report, case, repo, as_of)
    text = report.read_text(encoding="utf-8")
    by_hand = job_level(data, job) in WITHOUT_CATALOG
    defects = (len(result["defects_found"]), len(result["defects_counted"]))
    if by_hand:
        result = {key: [] for key in result} | check_text(text, repo, expected)
    problems = [f"{name} {len(result[key])}" for key, name in PROBLEMS if result.get(key)]
    if result["false_flags"]:
        problems.append(f"false flag {', '.join(result['false_flags'])}")
    if result["leaked"]:
        problems.append("secret copied")
    gaps = f"{len(result['found'])} of {len(expected['must_find'])}"
    if result["missed"]:
        gaps += f" (missed {', '.join(result['missed'])})"
    top = re.search(r"(\d+) of (\d+) in the first five", priority_placement(text, expected) or "")
    passed = not has_problems(result)
    if by_hand:
        gaps, top = "by hand", None
    results = stream_results(stream) if stream.exists() else []
    totals.update(
        found=0 if by_hand else len(result["found"]),
        seeded=0 if by_hand else len(expected["must_find"]),
        defects_found=0 if by_hand else defects[0],
        defects_counted=0 if by_hand else defects[1],
        passed=0 if by_hand else int(passed),
        reports=1,
        top=int(top[1]) if top else 0,
        top_of=int(top[2]) if top else 0,
        bad=len(result["bad_citations"]),
        misplaced=len(misplaced_citations(text, repo)),
        high=sum(row["priority"] == "high" for row in finding_rows(text).values()),
    )
    add_metrics(job, paths, totals)
    notes = []
    if job.get("backend", "claude") == "claude" and not ran_model(results, job["model"]):
        notes.append(f"{label}: the stream does not show {job['model']}")
    changed = repository_problems(case, Path(job["dir"]) / job["name"])
    notes += repository_note(job, changed)
    if result["leaked"]:
        notes.append(f"{label}: copied {', '.join(result['leaked'])}")
    material = job_material(data, job)
    allowed = [Path(job["dir"]), paths["plan.json"].parent / "providers"]
    allowed += [material.parent if job_level(data, job) == "full" else material] if material else []
    outside = outside_paths(stream, allowed) if stream.exists() else []
    if outside:
        notes.append(f"{label}: tool calls name paths outside the run: {', '.join(outside[:8])}")
    cells = [
        job["name"],
        str(job["run"]),
        arm_label(data, job),
        gaps,
        "by hand" if by_hand else "yes" if passed else "no",
        f"{top[1]} of {top[2]}" if top else "—",
        ", ".join(problems) or "—",
        job_status(job, data, paths, changed),
    ]
    # A figure only for a case that counts a defect; a run by hand has none to give.
    figure = None if not defects[1] else "by hand" if by_hand else f"{defects[0]} of {defects[1]}"
    return {
        "cells": cells,
        "defects": figure,
        # The hash comes first: "booking-api run 94: <hash>" reads as an API key to secret scanners.
        "hash": f"- `{sha256(report)}` {job['name']} run {job['run']}",
        "notes": notes,
    }


def leftovers(paths: dict[str, Path], data: dict) -> list[str]:
    """Name new entries of the temporary directory that a run's stream mentions."""
    before = set(paths["tmp-before.txt"].read_text(encoding="utf-8").split())
    planned = {Path(job["dir"]).name for job in data["jobs"]} | {p.name for p in skill_exports(data)}
    streams = {p.stem: p.read_text(encoding="utf-8") + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in codex_backend.copied_sessions(p) if path.is_file()
    ) for p in sorted(paths["streams"].glob("*.jsonl"))}
    notes = []
    for entry in sorted(set(os.listdir(tempfile.gettempdir())) - before - planned):
        location = str(Path(tempfile.gettempdir()) / entry)
        named = [stem for stem, text in streams.items() if location in text]
        if named:
            notes.append(f"left in the temporary directory: {entry}, named by {', '.join(named)}")
    return notes


def arm_label(data: dict, job: dict) -> str:
    """Name a job's model, and its revision and level when the round compares several."""
    label = ("Codex " + job["model"]) if job.get("backend") == "codex" else model_label(job["model"])
    if len({j.get("revision") for j in data["jobs"]}) > 1:
        label += f" @ {job_revision(data, job)}"
    if len({job_level(data, j) for j in data["jobs"]}) > 1:
        label += f" {job_level(data, job)}"
    return label


def missing_report(job: dict, data: dict, paths: dict[str, Path], totals: Counter, as_of: date) -> dict:
    expected = json.loads((case_path(job["case"]) / "expected.json").read_text(encoding="utf-8"))
    by_hand = job_level(data, job) in WITHOUT_CATALOG
    defects = counted_defects(expected, as_of)
    totals.update(reports=1, seeded=0 if by_hand else len(expected["must_find"]),
                  defects_counted=0 if by_hand else len(defects),
                  top_of=0 if by_hand else len(expected.get("top_priorities", [])))
    add_metrics(job, paths, totals)
    changed = repository_problems(case_path(job["case"]), Path(job["dir"]) / job["name"])
    status = job_status(job, data, paths, changed)
    cells = [job["name"], str(job["run"]), arm_label(data, job),
             "by hand" if by_hand else f"0 of {len(expected['must_find'])}", "no", "—", "no report", status]
    report = paths["reports"] / f"{job_label(job)}.md"
    problem = "uncredited report" if report.is_file() else "no report"
    cells[-2] = problem
    notes = [f"{job_label(job)}: {problem}"] + repository_note(job, changed)
    return {"cells": cells, "defects": ("by hand" if by_hand else f"0 of {len(defects)}") if defects else None,
            "hash": f"- `{sha256(report)}` {job['name']} run {job['run']}" if report.is_file() else None, "notes": notes}


def mean_metric(totals: Counter, key: str, n: int, places: int = 0, scale: float = 1) -> str:
    count = totals[key + "_n"]
    if not count:
        return "—"
    value = f"{totals[key] / count / scale:,.{places}f}"
    return value + (f" ({count} of {n})" if totals["codex"] or count != n else "")


def summarize(round_dir: Path) -> str:
    """Score valid and legacy reports, list every job, and write summary.md."""
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    scored_jobs, hashes, notes = [], [], []
    totals: dict[str, Counter] = defaultdict(Counter)
    as_of = round_date(paths, data)
    with ExitStack() as stack:
        repos: dict[str, Path] = {}
        for job in data["jobs"]:
            label = f"run{job['run']}-{job['name']}"
            if job["case"] not in repos:
                repos[job["case"]] = stack.enter_context(case_files(case_path(job["case"])))
            status = job_status(job, data, paths, [])
            if (paths["reports"] / f"{label}.md").exists() and status in ("valid", "legacy, unverified"):
                scored = score_job(job, data, paths, repos[job["case"]], totals[arm_label(data, job)], as_of)
            else:
                scored = missing_report(job, data, paths, totals[arm_label(data, job)], as_of)
            scored["usage"] = available_usage(job, paths)
            notes += [f"{label}: {note}" for note in read_record(round_dir, job).get("notes", [])]
            scored_jobs.append(scored)
            if scored["hash"]:
                hashes.append(scored["hash"])
            notes += scored["notes"]
    notes += leftovers(paths, data)
    overlap = overlap_note(paths["log.txt"].read_text(encoding="utf-8") if paths["log.txt"].exists() else "")
    # Rounds of cases without dated defects keep the shape of older summaries.
    located = any(scored["defects"] for scored in scored_jobs)
    run_header = ["Case", "Run", "Model", "Seeded gaps found", "Passes the scorer"]
    run_header += ["Top priorities in first five", "Problems", "Status", "Available usage"]
    model_header = ["Model", "Seeded gaps found", "Reports that pass the scorer"]
    model_header += ["Top priorities in first five", "Bad citations", "Misplaced citations"]
    model_header += ["High findings", "Mean minutes", "Mean USD", "Mean tool calls"]
    model_header += ["Mean cache writes", "Mean cache reads", "Mean output tokens"]
    has_codex = any(job.get("backend") == "codex" for job in data["jobs"])
    if has_codex:
        model_header += ["Mean uncached input", "Mean reasoning tokens"]
    model_header += ["Valid runs"]
    if located:
        run_header.insert(4, "Defects at location")
        model_header.insert(2, "Defects at location")
    rows = []
    for scored in scored_jobs:
        cells = list(scored["cells"])
        if located:
            cells.insert(4, scored["defects"] or "—")
        cells.append(scored["usage"])
        rows.append("| " + " | ".join(cells) + " |")
    lines = [
        f"# Round summary ({now()})",
        "",
        *([overlap, ""] if overlap else []),
        f"Skill `{data['skill_commit']}`, level {data['level']}, planned {data['created']}.",
        "",
        "| " + " | ".join(run_header) + " |",
        "|" + " --- |" * len(run_header),
        *rows,
        "",
        "| " + " | ".join(model_header) + " |",
        "|" + " --- |" * len(model_header),
    ]
    for model, t in totals.items():
        n = t["reports"] or 1
        metrics = [mean_metric(t, "seconds", n, 1, 60), "—" if t["codex"] else mean_metric(t, "cents", n, 2, 100)]
        metrics += [mean_metric(t, key, n) for key in ("tools", "tokens_written", "tokens_read", "tokens_out")]
        if has_codex:
            metrics += [mean_metric(t, key, n) for key in ("tokens_uncached", "tokens_reasoning")]
        lines.append(
            f"| {model} | {t['found']} of {t['seeded']} "
            + (f"| {t['defects_found']} of {t['defects_counted']} " if located else "")
            + f"| {t['passed']} of {t['reports']} "
            f"| {t['top']} of {t['top_of']} | {t['bad']} | {t['misplaced']} | {t['high']} | "
            + " | ".join(metrics) + f" | {t['valid']} of {t['reports']} |"
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


def parse_backend(model: str, backend: str | None = None) -> tuple[str, str]:
    if ":" in model:
        prefix, model = model.split(":", 1)
        if backend and backend != prefix:
            raise SystemExit("conflicting backends")
        backend = prefix
    backend = backend or "claude"
    if backend not in ("claude", "codex"):
        raise SystemExit(f"unknown backend: {backend}")
    if ":" in model:
        raise SystemExit("model IDs cannot contain ':'")
    if backend == "codex" and not re.fullmatch(r"(?:gpt-\d+(?:\.\d+)+-[a-z0-9][a-z0-9.-]*|o\d+-[a-z0-9][a-z0-9.-]*)", model):
        raise SystemExit(f"Codex needs a full model ID, not {model!r}")
    return backend, model


def parse_runs(values: list[str]) -> list[tuple]:
    """Read NUMBER=[BACKEND:]MODEL[@REVISION][+LEVEL] specifications."""
    runs = []
    for value in values:
        number, _, rest = value.partition("=")
        rest, _, level = rest.partition("+")
        model, _, revision = rest.partition("@")
        if not number.isdigit() or not model:
            raise SystemExit(f"--run takes NUMBER=[BACKEND:]MODEL[@REVISION][+LEVEL], not {value!r}")
        backend, model = parse_backend(model)
        spec = (number, model, revision or None, level or None)
        runs.append((*spec, backend) if backend == "codex" else spec)
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
        help="a run number, [BACKEND:]MODEL, and optionally @REVISION and +LEVEL, such as"
        " 51=claude-opus-5-5 or 300=codex:gpt-6.1-sol; repeat for each run",
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
        "--stagger-seconds",
        type=float,
        default=5,
        help="space audit launches so later ones read the prompt cache the first one wrote",
    )
    run_parser.add_argument(
        "--budget-usd",
        type=float,
        required=True,
        help="stop launching audits once finished ones reach this API-equivalent cost",
    )
    run_parser.add_argument(
        "--provider-url",
        action="append",
        default=[],
        metavar="MODEL=URL",
        help="serve MODEL, such as glm-5.3, from this Anthropic-compatible base URL",
    )
    run_parser.add_argument(
        "--provider-key",
        action="append",
        default=[],
        metavar="MODEL=KEY_FILE",
        help="read MODEL's API key from this file (mode 600) through an apiKeyHelper",
    )
    run_parser.add_argument(
        "--lock-wait-minutes",
        type=float,
        default=0,
        help="wait this long for another round on one of this round's providers to finish; by"
        " default, exit at once",
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
        providers = parse_providers(arguments.provider_url, arguments.provider_key)
        timeout = arguments.timeout_minutes * 60
        return run(
            arguments.round_dir,
            arguments.jobs,
            timeout,
            arguments.budget_usd,
            providers=providers,
            stagger=arguments.stagger_seconds,
            lock_wait=arguments.lock_wait_minutes * 60,
        )
    if arguments.command == "summarize":
        print(summarize(arguments.round_dir), end="")
        return 0
    for path in clean(arguments.round_dir):
        print(f"removed {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
