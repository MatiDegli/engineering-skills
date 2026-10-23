#!/usr/bin/env python3
"""Show where Claude Code tokens go, by kind of token, for sessions, subagents, and rounds.

Each share weights tokens by their price relative to uncached input, which is the same for every
Claude model: input 1, cache write 1.25 with a 5-minute lifetime or 2 with a 1-hour one, cache read
0.1, and output 5. The shares tell which kind of token to reduce; they are not dollars.

`transcripts` reads a Claude Code project directory, such as
`~/.claude/projects/<project>`, with its main sessions and their subagents. `rounds` reads the
round directories of `tools/claude_rounds.py`.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

WEIGHTS = {"input": 1.0, "write_5m": 1.25, "write_1h": 2.0, "read": 0.1, "output": 5.0}
KINDS = ("input", "write_5m", "write_1h", "write_unknown", "read", "output")
PRICES = Path(__file__).with_name("claude_ledger_prices.json")


def message_usage(message: dict) -> dict[str, int]:
    """Split one API response's usage into the kinds of WEIGHTS."""
    usage = message.get("usage") or {}
    creation = usage.get("cache_creation") or {}
    write_1h = creation.get("ephemeral_1h_input_tokens") or 0
    write_5m = creation.get("ephemeral_5m_input_tokens")
    if write_5m is None:
        write_5m = max((usage.get("cache_creation_input_tokens") or 0) - write_1h, 0)
    return {
        "input": usage.get("input_tokens") or 0,
        "write_5m": write_5m,
        "write_1h": write_1h,
        "read": usage.get("cache_read_input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
    }


def read_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def transcript_usage(path: Path) -> tuple[dict[str, int], int, str]:
    """Return a transcript's tokens by kind, its API responses, and its model.

    One response can span several transcript lines that repeat its usage, so each message ID
    counts once.
    """
    totals: dict[str, int] = defaultdict(int)
    seen, model = set(), ""
    for event in read_events(path):
        message = event.get("message")
        if event.get("type") != "assistant" or not isinstance(message, dict) or "usage" not in message:
            continue
        key = message.get("id") or event.get("uuid")
        if key in seen:
            continue
        seen.add(key)
        model = message.get("model") or model
        for kind, value in message_usage(message).items():
            totals[kind] += value
    return dict(totals), len(seen), model


def stream_usage(path: Path) -> dict[str, dict[str, int]]:
    """Return a round stream's tokens by model, from its last result's cumulative usage."""
    results = [e for e in read_events(path) if e.get("type") == "result"]
    usage: dict[str, dict[str, int]] = {}
    for model, counts in ((results[-1].get("modelUsage") or {}) if results else {}).items():
        usage[model] = {
            "input": counts.get("inputTokens") or 0,
            "write_5m": counts.get("cacheCreationInputTokens") or 0,
            "write_1h": 0,
            "read": counts.get("cacheReadInputTokens") or 0,
            "output": counts.get("outputTokens") or 0,
        }
    return usage


def shares(totals: dict[str, int]) -> tuple[float, dict[str, float]]:
    """Return the weighted total and each kind's share of it."""
    weighted = {kind: totals.get(kind, 0) * weight for kind, weight in WEIGHTS.items()}
    total = sum(weighted.values())
    return total, {kind: value / total if total else 0.0 for kind, value in weighted.items()}


def transcripts(directory: Path) -> dict[str, dict]:
    groups: dict[str, dict] = defaultdict(lambda: {"totals": defaultdict(int), "responses": 0})
    for path in sorted(directory.rglob("*.jsonl")):
        totals, responses, model = transcript_usage(path)
        if not responses:
            continue
        kind = "subagent" if "subagents" in path.parts else "session"
        group = groups[f"{kind} {model or 'unknown'}"]
        group["responses"] += responses
        for name, value in totals.items():
            group["totals"][name] += value
    return groups


def rounds(directory: Path) -> dict[str, dict]:
    groups: dict[str, dict] = defaultdict(lambda: {"totals": defaultdict(int), "responses": 0})
    for path in sorted(directory.glob("*/streams/*.jsonl")):
        if ".login-failure-" in path.name:
            continue
        for model, totals in stream_usage(path).items():
            group = groups[f"audit {model}"]
            group["responses"] += 1
            for name, value in totals.items():
                group["totals"][name] += value
    return groups


def load_prices(path: Path = PRICES) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not snapshot.get("as_of") or not snapshot.get("source") or not snapshot.get("models"):
        raise ValueError("a price snapshot needs as_of, source, and models")
    for cards in snapshot["models"].values():
        if not cards:
            raise ValueError("a model needs at least one rate card")
        for card in cards:
            for kind in KINDS:
                if kind == "write_unknown":
                    continue
                value = card[kind]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("prices must be nonnegative numbers")
    return snapshot


def price_interval(record: dict, snapshot: dict) -> tuple[float, float] | None:
    tokens = record["tokens"]
    if not any(tokens.values()):
        return 0.0, 0.0
    cards = snapshot["models"].get(record["model"])
    if not cards:
        return None
    context = sum(tokens[k] for k in KINDS if k != "output")
    if not record["aggregate"]:
        cards = [c for c in cards if c.get("min_context", 0) <= context
                 and (c.get("max_context") is None or context <= c["max_context"])]
        if len(cards) != 1:
            raise ValueError("request context must match exactly one rate card")
    costs = []
    for card in cards:
        fixed = sum(tokens[k] * card[k] for k in KINDS if k != "write_unknown")
        costs.extend((fixed + tokens["write_unknown"] * card[ttl]) / 1e6 for ttl in ("write_5m", "write_1h"))
    return min(costs), max(costs)


def table(groups: dict[str, dict], counted: str) -> str:
    lines = [
        f"| Group | {counted} | Weighted tokens | Uncached input | 5-minute writes | 1-hour writes | Reads | Output |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, group in sorted(groups.items(), key=lambda item: -shares(item[1]["totals"])[0]):
        total, part = shares(group["totals"])
        cells = " | ".join(f"{100 * part[kind]:.0f}%" for kind in WEIGHTS)
        lines.append(f"| {name} | {group['responses']} | {total / 1e6:.2f}M | {cells} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("transcripts", help="a Claude Code project directory").add_argument("directory", type=Path)
    commands.add_parser("rounds", help="a directory of runner rounds").add_argument("directory", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "transcripts":
        print(table(transcripts(arguments.directory.expanduser()), "API responses"))
    else:
        print(table(rounds(arguments.directory.expanduser()), "Runs"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
