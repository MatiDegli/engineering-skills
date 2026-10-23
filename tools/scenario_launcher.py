#!/usr/bin/env python3
"""Run a scenario's agent inside its sandbox as the sandbox's PID 1.

`tools/scenario_rounds.py` delivers this file into the sandbox's /run and starts it under
`bwrap --as-pid-1`, then sends one JSON object on standard input: the files to write, the processes
to start, the agent's command, environment, prompt, and time limit, and the number of the
descriptor for the record. Nothing about the fixtures is written anywhere the agent can read. It
works in this order:

1. delete its own file and show a plain init in the process table, so that nothing the agent can
   read says what runs as PID 1;
2. start the `process` fixtures, each a real command in the workspace, held to its own time bound;
3. start the agent, give it the prompt on standard input, and enforce the time limit; meanwhile
   collect the processes that lose their parent, as an init does;
4. stop every other process except the fixtures and what they started;
5. record each fixture as alive, exited, killed by a signal, or past its bound, then stop them;
6. write the record, one JSON line, to the descriptor.

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

# Seconds between SIGTERM and SIGKILL for an agent that outlives its time limit.
GRACE = 10
SWEEP_SECONDS = 10
# How often the launcher looks at the fixtures' bounds while it waits for the agent.
TICK = 0.5
# What the process table shows for this process: a plain init.
TITLE = b"/sbin/init"
# The directory the runner delivers this file into; only a file there is deleted.
DELIVERED_IN = "/run"


def signal_group(process: subprocess.Popen, number: int) -> None:
    try:
        os.killpg(process.pid, number)
    except ProcessLookupError:
        pass


def signal_name(number: int) -> str:
    """Name a signal; the real-time ones (35 to 63) have no name in `signal.Signals`."""
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"SIG{number}"


def status_of(process: subprocess.Popen) -> dict:
    """Describe a child by how it ended; None from `poll` means that it still runs."""
    code = process.poll()
    if code is None:
        return {"state": "alive"}
    if code < 0:
        return {"state": "killed", "signal": signal_name(-code)}
    return {"state": "exited", "code": code}


class Fixture:
    """A real command started in the workspace, ended by the launcher when its bound runs out."""

    def __init__(self, spec: dict, workspace: Path, environment: dict[str, str]) -> None:
        self.name, self.expired, self.error = spec["name"], False, None
        self.deadline = time.monotonic() + spec["seconds"]
        try:
            self.process = subprocess.Popen(
                spec["command"],
                cwd=workspace / spec.get("cwd", "."),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            self.process, self.error = None, str(error)

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    def enforce_bound(self) -> None:
        """End the command and what it started once its bound has run out."""
        if self.process and self.process.poll() is None and time.monotonic() >= self.deadline:
            signal_group(self.process, signal.SIGKILL)
            self.process.wait()
            self.expired = True

    def status(self) -> dict:
        if self.process is None:
            return {"state": "failed", "error": self.error}
        return {"state": "expired"} if self.expired else status_of(self.process)

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            signal_group(self.process, signal.SIGKILL)
            self.process.wait()


def wait_for(agent: subprocess.Popen, seconds: float, fixtures: list[Fixture]) -> bool:
    """Wait for the agent to end, for at most `seconds`; return whether it ended.

    The fixtures' bounds are enforced meanwhile, so that none outlives its own, and the processes
    that lost their parent are collected, so that none stays `<defunct>` while the agent works.
    """
    deadline = time.monotonic() + seconds
    spared = {agent.pid, *(fixture.pid for fixture in fixtures if fixture.pid)}
    while True:
        for fixture in fixtures:
            fixture.enforce_bound()
        reap_orphans(spared)
        left = deadline - time.monotonic()
        try:
            agent.wait(timeout=max(0.0, min(left, TICK)))
            return True
        except subprocess.TimeoutExpired:
            if left <= 0:
                return False


def run_agent(payload: dict, fixtures: list[Fixture]) -> tuple[dict, float]:
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
    timed_out = not wait_for(agent, payload["limit"], fixtures)
    if timed_out:
        signal_group(agent, signal.SIGTERM)
        if not wait_for(agent, GRACE, fixtures):
            signal_group(agent, signal.SIGKILL)
            agent.wait()
    outcome = status_of(agent)
    return {"timed_out": timed_out, **outcome}, time.monotonic() - begun


def processes_other_than_this(keep: set[int]) -> list[tuple[int, str]]:
    """List the (pid, state) of every process of the namespace but this one and the kept sessions.

    A fixture leads a session of its own, and what it starts stays in it, so keeping a fixture's PID
    as a session keeps the fixture and its children.
    """
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == os.getpid():
            continue
        try:
            fields = Path(f"/proc/{name}/stat").read_text().rpartition(")")[2].split()
            state, session = fields[0], int(fields[3])
        except (OSError, IndexError, ValueError):
            continue
        if int(name) not in keep and session not in keep:
            found.append((int(name), state))
    return found


def live_processes(keep: set[int]) -> list[int]:
    """List the processes of the namespace other than this one, the kept ones, and zombies."""
    return [pid for pid, state in processes_other_than_this(keep) if state != "Z"]


def reap_orphans(spared: set[int]) -> None:
    """Collect the exit status of every zombie that is this process's to collect, as an init does.

    What a process leaves when its parent has gone is passed to PID 1, and stays `<defunct>` in the
    process table until PID 1 waits for it. `spared` holds the children that `subprocess` reads
    itself: reaping one here would make it report an exit code of 0 and not the real status.
    """
    for pid, state in processes_other_than_this(set()):
        if state == "Z" and pid not in spared:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass


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
        for pid, _ in processes_other_than_this(keep):
            try:
                os.waitpid(pid, os.WNOHANG)
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


def remove_own_file() -> None:
    """Delete the file this process was started from, which Python has read in full by now.

    Only a file delivered into /run goes, so a copy run by hand elsewhere is never touched.
    """
    path = Path(sys.argv[0])
    if str(path.parent) == DELIVERED_IN:
        try:
            path.unlink()
        except OSError:
            pass


def rename_process() -> None:
    """Show a plain init in the process table: set the name, and overwrite the command line.

    The command line that started the launcher names its file, and any process can read it under
    /proc/1. The kernel serves it from the memory where the arguments live, so writing a title
    there, padded with zeros to the old length, replaces it.
    """
    try:
        fields = Path("/proc/self/stat").read_text().rpartition(")")[2].split()
        start, end = int(fields[45]), int(fields[46])  # arg_start and arg_end
        if end - start > len(TITLE) and start > 0:
            ctypes.memmove(start, TITLE.ljust(end - start, b"\0"), end - start)
        ctypes.CDLL(None).prctl(15, b"init", 0, 0, 0)  # PR_SET_NAME
    except (OSError, AttributeError, IndexError, ValueError):
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
    remove_own_file()
    rename_process()
    payload = json.load(sys.stdin)
    forbid_inspection()
    for name, text in payload.get("files", {}).items():
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    workspace = Path(payload["cwd"])
    fixtures = [Fixture(spec, workspace, payload["fixture_environment"]) for spec in payload["fixtures"]]
    agent, seconds = run_agent(payload, fixtures)
    running = stop_others({fixture.pid for fixture in fixtures if fixture.pid})
    for fixture in fixtures:
        fixture.enforce_bound()
    record = {"agent": agent, "seconds": round(seconds, 1), "left_running": running}
    record["fixtures"] = {fixture.name: fixture.status() for fixture in fixtures}
    for fixture in fixtures:
        fixture.stop()
    os.write(payload["status_fd"], (json.dumps(record) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
