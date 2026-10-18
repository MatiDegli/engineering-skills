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
from urllib.parse import urlsplit

from tools.evals import (
    CASES,
    case_files,
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
# The levels of evals/README.md: the skill, its catalog with the report format, or a bare request.
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
}
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
# provider's lock is a file beside it. Rounds of different providers run at once on one host.
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


def round_resources(models: list[str], providers: dict[str, dict]) -> tuple[str, ...]:
    """Return the resources a round's models need, sorted and without repeats.

    A model served by the Claude login needs `anthropic`, and one served by `--provider-url` its
    provider's resource; a provider of a model the round does not run adds nothing.
    """
    needed = {provider_resource(providers[m]["url"]) if m in providers else ANTHROPIC for m in models}
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


def claude_command(
    prompt: str, model: str, directories: list[Path], settings: str | None = None
) -> list[str]:
    """Return the audit command.

    Only user settings load, with hooks off, so the audited repository's own agent settings,
    hooks, skills, and agents never load; the effort is fixed rather than inherited. A run served by
    another provider passes the settings file of `provider_launch`, which also turns hooks off.

    The audit is not confined. Bash is allowed without a pattern, and this command sets neither a
    permission mode nor a sandbox (the user settings it loads could), so a shell command runs with
    the rights of the user who started the runner: it can read every file that user can read, and
    it can still write files. Only the web and file-editing tools are disallowed. What keeps an
    audit in its repository is the prompt's instruction; afterwards `summarize` verifies the
    prepared repository and lists the home paths that tool calls name in full.
    """
    return [
        *("claude", "-p", prompt, "--model", model, "--effort", "high"),
        *(item for directory in directories for item in ("--add-dir", str(directory))),
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
    if level == "none":
        return None
    return Path(job["catalog"] if level == "catalog" else job_skill(data, job))


def job_revision(data: dict, job: dict) -> str:
    return job.get("revision") or data["skill_commit"]


def skill_exports(data: dict) -> list[Path]:
    """Return the temporary directories that hold the round's skill and catalog exports."""
    skills = [Path(path).parent for path in (data.get("skills") or {"": data.get("skill")}).values() if path]
    return skills + [Path(path) for path in (data.get("catalogs") or {}).values()]


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
        level = rest[1] if len(rest) > 1 and rest[1] else "full"
        if level not in PROMPTS:
            raise SystemExit(f"unknown level {level!r}; use one of {', '.join(PROMPTS)}")
        # A tag names its commit: an annotated tag is an object of its own.
        commit = repository_git("rev-parse", "--short", f"{wanted}^{{commit}}").decode().strip()
        specs.append((number, model, commit, level))
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
        for run, model, commit, level in specs:
            directory = Path(tempfile.mkdtemp(prefix="audit."))
            name = case_path(case).name
            prepare(case_path(case), directory / name)
            job = {"run": run, "model": model, "case": case, "name": name, "dir": str(directory)}
            job |= {"revision": commit, "level": level}
            job |= {"skill": skills[commit]} if level == "full" else {}
            job |= {"catalog": catalogs[commit]} if level == "catalog" else {}
            jobs.append(job)
    revisions = ", ".join(dict.fromkeys(s[2] for s in specs))
    levels = ", ".join(dict.fromkeys(s[3] for s in specs))
    data = {"created": now(), "skill_commit": revisions, "skills": skills, "catalogs": catalogs}
    data["level"] = levels
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


# Seconds between SIGTERM and SIGKILL when a process group is stopped.
GRACE = 30


def signal_group(process: subprocess.Popen, number: int) -> None:
    try:
        os.killpg(process.pid, number)
    except ProcessLookupError:
        pass


def stop_groups(processes: list[subprocess.Popen]) -> None:
    """Send SIGTERM to every process group, then SIGKILL to those whose leader outlives GRACE."""
    for process in processes:
        signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + GRACE
    for process in processes:
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
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
            live = [process for process in self.processes if process.poll() is None]
        stop_groups(live)
        return len(live)


class Interrupted(Exception):
    """Raised in the main thread by the handler of a stop signal; the argument is the signal."""


def run_command(
    command: list[str],
    cwd: Path,
    stdout: Path,
    stderr: Path,
    timeout: float,
    environment: dict[str, str] | None = None,
    running: Running | None = None,
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
                command, cwd=cwd, env=environment, stdout=out, stderr=err, start_new_session=True
            )
            running.processes.add(process)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_groups([process])
            err.write(f"\nstopped after {timeout:.0f} seconds\n")
            return -1
        finally:
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


def warm_up(round_dir: Path, models: list[str], providers: dict[str, dict]) -> None:
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
        environment = None
        if provider:
            environment, settings = provider_launch(provider, model, round_dir / "providers" / f"warmup-{model}")
            command += ["--settings", str(settings)]
        with output.open("w", encoding="utf-8") as out:
            subprocess.run(
                [*command, "--output-format", "json"],
                cwd=tempfile.gettempdir(),
                env=environment,
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
    if launch["running"].stopped.is_set():
        return f"{label}: skipped, stopped"
    if not launch["spending"].allows():
        return f"{label}: skipped, budget reached"
    provider = launch["providers"].get(job["model"])
    stream, stderr = paths["streams"] / f"{label}.jsonl", paths["streams"] / f"{label}.stderr.txt"
    material = job_material(data, job)
    prompt = PROMPTS[job_level(data, job)].format(path=material)
    directories = [material] if material else []
    environment, settings = audit_environment(round_dir), None
    if provider:
        environment, settings = provider_launch(provider, job["model"], round_dir / "providers" / label)
        environment |= {"GH_CONFIG_DIR": audit_environment(round_dir)["GH_CONFIG_DIR"]}
    command = claude_command(prompt, job["model"], directories, str(settings) if settings else None)
    launch["starts"].wait()
    for attempt in range(1, ATTEMPTS + 1):
        code = run_command(command, repo, stream, stderr, launch["timeout"], environment, launch["running"])
        if launch["running"].stopped.is_set():
            return f"{label}: stopped"
        results = stream_results(stream)
        if not login_failed(results) or attempt == ATTEMPTS:
            break
        stream.rename(paths["streams"] / f"{label}.login-failure-{attempt}.jsonl")
        launch["running"].stopped.wait(random.uniform(*launch["pause"]))
    launch["spending"].add(max((r.get("total_cost_usd") or 0 for r in results), default=0))
    if results:
        report.write_text(report_text(results), encoding="utf-8")
    used = sorted({name for r in results for name in r.get("modelUsage") or {}})
    flag = "" if ran_model(results, job["model"]) else " MODEL MISMATCH"
    source = init_key_source(stream) if provider else None
    if provider and source != "apiKeyHelper":
        flag += f" KEY SOURCE {source}"
    return f"{label}: exit {code}, models {','.join(used) or 'none'}{flag}"


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
    """Run every planned audit; return 1 when a model differs or an audit was skipped.

    `providers` maps a model served by another provider to its base URL and key file. SIGTERM or
    SIGINT stops the process group of every running audit, starts no other, and returns 128 plus
    the signal number; the handlers are restored afterwards. The whole round, warm-up included,
    holds the lock of every resource its models need (`round_resources`), waiting for them at most
    `lock_wait` seconds.
    """
    data = json.loads(round_paths(round_dir)["plan.json"].read_text(encoding="utf-8"))
    providers = providers or {}
    resources = round_resources([job["model"] for job in data["jobs"]], providers)
    with round_lock(f"claude_rounds run {round_dir.resolve()}", lock_wait, resources):
        return run_audits(round_dir, jobs, timeout, budget, pause, providers, stagger, resources)


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
    # A round served only by other providers needs no Claude login; checking it would refuse the
    # round when the login has expired, and touch the login outside the lock of the rounds using it.
    if ANTHROPIC in resources:
        status = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=60)
        if '"loggedIn": true' not in status.stdout:
            raise SystemExit("claude is not logged in here: run 'claude auth login' first")
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=60)
    (round_dir / "cli-version.txt").write_text(version.stdout, encoding="utf-8")
    providers = providers or {}
    warm_up(round_dir, sorted({job["model"] for job in data["jobs"]}), providers)
    running = Running()
    launch = {"timeout": timeout, "pause": pause, "providers": providers, "spending": Spending(budget)}
    launch |= {"starts": StartSpacer(stagger), "running": running}

    def interrupt(number: int, frame) -> None:
        if not running.stopped.is_set():
            running.stopped.set()
            raise Interrupted(number)

    lines, interrupted = [], 0
    previous = {number: signal.signal(number, interrupt) for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        with paths["log.txt"].open("a", encoding="utf-8") as log:
            log.write(f"start {now()} {version.stdout.strip()}, budget USD {budget:g}\n")
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                try:
                    futures = [
                        pool.submit(audit, round_dir, data, job, launch) for job in data["jobs"]
                    ]
                    for future in as_completed(futures):
                        lines.append(future.result())
                        log.write(lines[-1] + "\n")
                        log.flush()
                        print(lines[-1], flush=True)
                except Interrupted as stop:
                    interrupted = stop.args[0]
                    pool.shutdown(wait=False, cancel_futures=True)
                    name, ended = signal.Signals(interrupted).name, running.stop()
                    log.write(f"stopped {now()} by {name}: {ended} running audits ended\n")
                    print(f"stopped by {name}: {ended} running audits ended", flush=True)
            log.write(f"end {now()}\n")
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    if interrupted:
        return 128 + interrupted
    marks = ("MODEL MISMATCH", "KEY SOURCE", "skipped, the", "skipped, budget")
    return int(any(mark in line for line in lines for mark in marks))


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


def round_date(paths: dict[str, Path], data: dict) -> date:
    """Return the day the round's audits started, in UTC: the first `start` line of log.txt.

    A round that was run in several sessions counts from its first, so a defect found later is not
    held against it. A plan that was never run gives the day it was planned.
    """
    log = paths["log.txt"].read_text(encoding="utf-8") if paths["log.txt"].exists() else ""
    started = re.search(r"^start (\d{4}-\d{2}-\d{2})T", log, re.M)
    return date.fromisoformat(started[1] if started else data["created"][:10])


def score_job(
    job: dict, data: dict, paths: dict[str, Path], repo: Path, totals: Counter, as_of: date
) -> dict:
    """Score one run's report and check its stream and prepared repository.

    A report of the no-skill level has no criterion IDs: only its leaks and citations are checked
    here, and its gaps, defects, and priorities are scored by hand with the rules of evals/README.md.
    The defects count as of the round's date.
    """
    label, case = f"run{job['run']}-{job['name']}", case_path(job["case"])
    report, stream = paths["reports"] / f"{label}.md", paths["streams"] / f"{label}.jsonl"
    expected, result = score_report(report, case, repo, as_of)
    text = report.read_text(encoding="utf-8")
    by_hand = job_level(data, job) == "none"
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
    material = job_material(data, job)
    allowed = [Path(job["dir"]), paths["plan.json"].parent / "providers"]
    allowed += [material.parent if job_level(data, job) == "full" else material] if material else []
    outside = outside_paths(stream, allowed) if results else []
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
    streams = {p.stem: p.read_text(encoding="utf-8") for p in sorted(paths["streams"].glob("*.jsonl"))}
    notes = []
    for entry in sorted(set(os.listdir(tempfile.gettempdir())) - before - planned):
        location = str(Path(tempfile.gettempdir()) / entry)
        named = [stem for stem, text in streams.items() if location in text]
        if named:
            notes.append(f"left in the temporary directory: {entry}, named by {', '.join(named)}")
    return notes


def arm_label(data: dict, job: dict) -> str:
    """Name a job's model, and its revision and level when the round compares several."""
    label = model_label(job["model"])
    if len({j.get("revision") for j in data["jobs"]}) > 1:
        label += f" @ {job_revision(data, job)}"
    if len({job_level(data, j) for j in data["jobs"]}) > 1:
        label += f" {job_level(data, job)}"
    return label


def summarize(round_dir: Path) -> str:
    """Score every report, check the prepared repositories, and write summary.md."""
    paths = round_paths(round_dir)
    data = json.loads(paths["plan.json"].read_text(encoding="utf-8"))
    scored_jobs, hashes, notes = [], [], []
    totals: dict[str, Counter] = defaultdict(Counter)
    as_of = round_date(paths, data)
    with ExitStack() as stack:
        repos: dict[str, Path] = {}
        for job in data["jobs"]:
            label = f"run{job['run']}-{job['name']}"
            if not (paths["reports"] / f"{label}.md").exists():
                notes.append(f"{label}: no report")
                continue
            if job["case"] not in repos:
                repos[job["case"]] = stack.enter_context(case_files(case_path(job["case"])))
            scored = score_job(
                job, data, paths, repos[job["case"]], totals[arm_label(data, job)], as_of
            )
            scored_jobs.append(scored)
            hashes.append(scored["hash"])
            notes += scored["notes"]
    notes += leftovers(paths, data)
    # Rounds of cases without dated defects keep the shape of older summaries.
    located = any(scored["defects"] for scored in scored_jobs)
    run_header = ["Case", "Run", "Model", "Seeded gaps found", "Passes the scorer"]
    run_header += ["Top priorities in first five", "Problems"]
    model_header = ["Model", "Seeded gaps found", "Reports that pass the scorer"]
    model_header += ["Top priorities in first five", "Bad citations", "Misplaced citations"]
    model_header += ["High findings", "Mean minutes", "Mean USD", "Mean tool calls"]
    model_header += ["Mean cache writes", "Mean cache reads", "Mean output tokens"]
    if located:
        run_header.insert(4, "Defects at location")
        model_header.insert(2, "Defects at location")
    rows = []
    for scored in scored_jobs:
        cells = list(scored["cells"])
        if located:
            cells.insert(4, scored["defects"] or "—")
        rows.append("| " + " | ".join(cells) + " |")
    lines = [
        f"# Round summary ({now()})",
        "",
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
        lines.append(
            f"| {model} | {t['found']} of {t['seeded']} "
            + (f"| {t['defects_found']} of {t['defects_counted']} " if located else "")
            + f"| {t['passed']} of {t['reports']} "
            f"| {t['top']} of {t['top_of']} | {t['bad']} | {t['misplaced']} | {t['high']} "
            f"| {t['seconds'] / 60 / n:.1f} | {t['cents'] / 100 / n:.2f} | {t['tools'] / n:.0f} "
            f"| {t['tokens_written'] / n:,.0f} | {t['tokens_read'] / n:,.0f} | {t['tokens_out'] / n:,.0f} |"
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


def parse_runs(values: list[str]) -> list[tuple[str, str, str | None, str | None]]:
    """Read NUMBER=MODEL[@REVISION][+LEVEL] specifications."""
    runs = []
    for value in values:
        number, _, rest = value.partition("=")
        rest, _, level = rest.partition("+")
        model, _, revision = rest.partition("@")
        if not number.isdigit() or not model:
            raise SystemExit(f"--run takes NUMBER=MODEL[@REVISION][+LEVEL], not {value!r}")
        runs.append((number, model, revision or None, level or None))
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
