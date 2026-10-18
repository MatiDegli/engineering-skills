#!/usr/bin/env python3
"""Run a scenario's agent inside its sandbox as the sandbox's PID 1.

`tools/scenario_rounds.py` starts this file under `bwrap --as-pid-1` and sends one JSON object on
standard input: the files to write, the processes to start, the agent's command, environment,
prompt, and time limit, and the number of the descriptor for the record. Nothing about the fixtures
is written anywhere the agent can read. It works in this order:

1. start the `process` fixtures, whose command line is their label, and wait until they show it;
2. start the agent, give it the prompt on standard input, and enforce the time limit;
3. stop every other process, so that nothing the agent left running can touch a fixture;
4. record each fixture as alive, exited, or killed by a signal, then stop them;
5. write the record, one JSON line, to the descriptor.

As PID 1 the launcher ignores the signals that a process inside the sandbox sends it, so the agent
cannot kill it. That holds only for a signal with no handler, so it first restores the default
disposition of the ones Python handles (SIGINT). It refuses to run as anything else: stopping
"every other process" is only safe in a PID namespace of its own. It uses only the standard
library, because nothing else is mounted.
"""

from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SLEEP = "/bin/sleep"
# Seconds between SIGTERM and SIGKILL for an agent that outlives its time limit.
GRACE = 10
SWEEP_SECONDS = 10


def signal_group(process: subprocess.Popen, number: int) -> None:
    try:
        os.killpg(process.pid, number)
    except ProcessLookupError:
        pass


def status_of(process: subprocess.Popen) -> dict:
    """Describe a child by how it ended; None from `poll` means that it still runs."""
    code = process.poll()
    if code is None:
        return {"state": "alive"}
    if code < 0:
        return {"state": "killed", "signal": signal.Signals(-code).name}
    return {"state": "exited", "code": code}


def start_fixtures(fixtures: list[dict]) -> dict[str, subprocess.Popen]:
    """Start each fixture as a sleeper whose command line starts with its label."""
    started = {}
    for fixture in fixtures:
        started[fixture["name"]] = subprocess.Popen(
            [fixture["label"], str(int(fixture["seconds"]))],
            executable=SLEEP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    deadline = time.monotonic() + 5
    for fixture in fixtures:
        process, wanted = started[fixture["name"]], fixture["label"].encode()
        while time.monotonic() < deadline:
            try:
                if Path(f"/proc/{process.pid}/cmdline").read_bytes().startswith(wanted):
                    break
            except OSError:
                break
            time.sleep(0.01)
    return started


def run_agent(payload: dict) -> tuple[dict, float]:
    """Run the agent to its end or its time limit; return how it ended and for how long."""
    begun = time.monotonic()
    try:
        agent = subprocess.Popen(
            payload["command"],
            cwd=payload["cwd"],
            env=payload["environment"],
            stdin=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        return {"error": str(error)}, 0.0
    try:
        agent.stdin.write(payload["prompt"].encode("utf-8"))
        agent.stdin.close()
    except BrokenPipeError:
        pass
    timed_out = False
    try:
        agent.wait(timeout=payload["limit"])
    except subprocess.TimeoutExpired:
        timed_out = True
        signal_group(agent, signal.SIGTERM)
        try:
            agent.wait(timeout=GRACE)
        except subprocess.TimeoutExpired:
            signal_group(agent, signal.SIGKILL)
            agent.wait()
    outcome = status_of(agent)
    return {"timed_out": timed_out, **outcome}, time.monotonic() - begun


def live_processes(keep: set[int]) -> list[int]:
    """List the processes of the namespace other than this one, the kept ones, and zombies."""
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == os.getpid() or int(name) in keep:
            continue
        try:
            state = Path(f"/proc/{name}/stat").read_text().rpartition(")")[2].split()[0]
        except (OSError, IndexError):
            continue
        if state != "Z":
            found.append(int(name))
    return found


def stop_others(keep: set[int]) -> int:
    """Kill every process except this one and `keep`, and reap what it can; return how many ran.

    A process that forks while being killed is caught by the next pass.
    """
    count = len(live_processes(keep))
    deadline = time.monotonic() + SWEEP_SECONDS
    while time.monotonic() < deadline:
        pids = live_processes(keep)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for name in os.listdir("/proc"):
            if name.isdigit() and int(name) not in keep and int(name) != os.getpid():
                try:
                    os.waitpid(int(name), os.WNOHANG)
                except ChildProcessError:
                    pass
        if not pids:
            break
        time.sleep(0.05)
    return count


def forbid_inspection() -> None:
    """Make this process non-dumpable, so the agent cannot open its descriptors under /proc."""
    try:
        ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE
    except (OSError, AttributeError):
        pass


def restore_default_signals() -> None:
    """Give every signal that Python handles back its default disposition.

    The kernel drops a signal that a process in the namespace sends to PID 1 unless PID 1 has a
    handler for it. Python installs one for SIGINT at start-up, so `kill -INT 1` from inside would
    reach it and end the launcher; with the default disposition the signal is dropped.
    """
    for number in signal.valid_signals():
        if callable(signal.getsignal(number)):
            signal.signal(number, signal.SIG_DFL)


def main() -> int:
    restore_default_signals()
    if os.getpid() != 1:
        print("the launcher runs only as PID 1 of a sandbox", file=sys.stderr)
        return 2
    payload = json.load(sys.stdin)
    forbid_inspection()
    for name, text in payload.get("files", {}).items():
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    fixtures = start_fixtures(payload["fixtures"])
    agent, seconds = run_agent(payload)
    running = stop_others({process.pid for process in fixtures.values()})
    record = {"agent": agent, "seconds": round(seconds, 1), "left_running": running}
    record["fixtures"] = {name: status_of(process) for name, process in fixtures.items()}
    for process in fixtures.values():
        if process.poll() is None:
            signal_group(process, signal.SIGKILL)
            process.wait()
    os.write(payload["status_fd"], (json.dumps(record) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
