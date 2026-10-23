#!/usr/bin/env python3
"""Read Claude logs without model calls; report tokens and dated list-price equivalents.

Unknown cache-write TTLs and aggregate context tiers produce price intervals. Nonzero usage from
unknown models remains unpriced. CLI-recorded costs are separate; these amounts do not measure plan quota.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

KINDS = ("input", "write_5m", "write_1h", "write_unknown", "read", "output")
PRICES = Path(__file__).with_name("claude_ledger_prices.json")


def count(value) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("token counts must be nonnegative integers")
    return value


def message_usage(message: dict) -> dict[str, int]:
    usage = message.get("usage") or {}
    flat = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    iterations = usage.get("iterations") or []
    if not any(count(usage.get(k)) for k in flat) and iterations:
        total = dict.fromkeys(KINDS, 0)
        for iteration in iterations:
            for kind, value in message_usage({"usage": iteration}).items():
                total[kind] += value
        return total
    creation = usage.get("cache_creation") or {}
    w5 = count(creation.get("ephemeral_5m_input_tokens"))
    w1 = count(creation.get("ephemeral_1h_input_tokens"))
    written = count(usage.get("cache_creation_input_tokens", w5 + w1))
    if written < w5 + w1:
        raise ValueError("cache TTL counts exceed the reported cache writes")
    return dict(zip(KINDS, (count(usage.get("input_tokens")), w5, w1, written - w5 - w1,
                            count(usage.get("cache_read_input_tokens")), count(usage.get("output_tokens")))))


def events(path: Path, issues: dict):
    with path.open(encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    yield number, event
            except json.JSONDecodeError:
                issues["invalid_json_lines"] += 1
                issues.setdefault("invalid_json_locations", []).append(f"{path}:{number}")
                if not line.startswith("\0"):
                    continue
                try:
                    recovered = json.loads(line.lstrip("\0"))
                except json.JSONDecodeError:
                    continue
                if not isinstance(recovered, dict):
                    continue
                message = recovered.get("message")
                if ("usage" in recovered or "modelUsage" in recovered
                        or isinstance(message, dict) and "usage" in message):
                    continue
                issues["recovered_nul_padded_lines"] += 1


def timestamp(value: str | None) -> float | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.timestamp()


def keep_record(records: dict, key, record: dict, issues: dict):
    previous = records.get(key)
    if previous is None:
        records[key] = record
        return
    issues["duplicate_records"] += 1
    old, new = previous["tokens"], record["tokens"]
    if previous["model"] != record["model"]:
        raise ValueError("one response ID names conflicting models")
    if old == new:
        return
    if all(new[k] >= old[k] for k in KINDS):
        records[key] = record
    elif not all(old[k] >= new[k] for k in KINDS):
        raise ValueError("one response ID has conflicting non-cumulative usage")


def transcript_records(directory: Path, issues: dict) -> list[dict]:
    records = {}
    for path in sorted(directory.rglob("*.jsonl")):
        role = "subagent" if "subagents" in path.parts else "session"
        meta = path.with_suffix(".meta.json")
        if role == "subagent" and meta.exists():
            role = json.loads(meta.read_text()).get("agentType") or role
        for number, event in events(path, issues):
            message = event.get("message")
            if event.get("type") != "assistant" or not isinstance(message, dict) or "usage" not in message:
                continue
            key = message.get("id") or event.get("uuid") or (str(path), number)
            record = {"model": message.get("model") or "unknown", "role": role,
                      "agent": str(path.resolve()),
                      "timestamp": timestamp(event.get("timestamp")), "aggregate": False,
                      "tokens": message_usage(message), "recorded_cli_usd": None}
            keep_record(records, key, record, issues)
    return list(records.values())


def result_records(result: dict) -> list[dict]:
    usage = result.get("modelUsage") or {}
    own = message_usage(result)
    rows = []
    for model, values in usage.items():
        totals = dict(zip(KINDS, (count(values.get("inputTokens")), 0, 0,
                                  count(values.get("cacheCreationInputTokens")),
                                  count(values.get("cacheReadInputTokens")), count(values.get("outputTokens")))))
        # A result's usage can cover only the lead, while modelUsage includes helpers.
        if len(usage) == 1 and all(totals[k] == own[k] for k in ("input", "read", "output")) and (
                totals["write_unknown"] == sum(own[k] for k in KINDS if k.startswith("write_"))):
            totals = own
        recorded = values.get("costUSD")
        if recorded is not None and (not isinstance(recorded, (int, float)) or isinstance(recorded, bool)
                                     or not math.isfinite(recorded) or recorded < 0):
            raise ValueError("recorded CLI costs must be nonnegative numbers")
        rows.append({"model": model, "role": "audit", "timestamp": timestamp(result.get("timestamp")),
                     "aggregate": True, "tokens": totals, "recorded_cli_usd": recorded})
    return rows


def round_records(directory: Path, issues: dict) -> list[dict]:
    records = {}
    for path in sorted(directory.rglob("*.jsonl")):
        if path.parent.name != "streams" or ".login-failure-" in path.name or path.name.startswith("warmup"):
            continue
        last = None
        for _, event in events(path, issues):
            if event.get("type") == "result":
                last = event
        if last is None or not last.get("modelUsage"):
            issues["streams_without_model_totals"] += 1
            continue
        identity = last.get("uuid") or str(path)
        for record in result_records(last):
            keep_record(records, (identity, record["model"]), record, issues)
    return list(records.values())


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


def accepted_outcomes(path: Path, start: float | None, end: float | None) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not document.get("unit") or not document.get("source"):
        raise ValueError("outcomes need an explicit unit and source")
    seen, accepted = set(), 0
    for item in document["items"]:
        if item["id"] in seen:
            raise ValueError("outcome IDs must be unique")
        seen.add(item["id"])
        moment = timestamp(item["completed_at"])
        if moment is None:
            raise ValueError("outcomes need a completion timestamp")
        if item["status"] == "accepted" and (start is None or moment >= start) and (end is None or moment < end):
            accepted += 1
    return {"unit": document["unit"], "source": document["source"], "accepted": accepted}


def report(records: list[dict], snapshot: dict, issues: dict, start=None, end=None, outcomes=None) -> dict:
    groups = {}
    selected = []
    for record in records:
        moment = record["timestamp"]
        if moment is None and (start is not None or end is not None):
            issues["undated_records_excluded"] += 1
            continue
        if moment is not None and ((start is not None and moment < start) or (end is not None and moment >= end)):
            continue
        selected.append(record)
        key = record["role"] + " " + record["model"]
        group = groups.setdefault(key, {"responses": 0, "totals": dict.fromkeys(KINDS, 0),
                                       "usd_min": 0.0, "usd_max": 0.0, "unpriced_records": 0,
                                       "recorded_cli_usd": 0.0, "recorded_cli_records": 0})
        group["responses"] += 1
        for kind, value in record["tokens"].items():
            group["totals"][kind] += value
        interval = price_interval(record, snapshot)
        if interval is None:
            group["unpriced_records"] += 1
        else:
            group["usd_min"] += interval[0]
            group["usd_max"] += interval[1]
        if record["recorded_cli_usd"] is not None:
            group["recorded_cli_usd"] += record["recorded_cli_usd"]
            group["recorded_cli_records"] += 1
    dated = [r["timestamp"] for r in selected if r["timestamp"] is not None]
    source_complete = (issues.get("invalid_json_lines", 0) <= issues.get("recovered_nul_padded_lines", 0)
                       and not any(issues.get(k) for k in
                                   ("streams_without_model_totals", "undated_records_excluded")))
    complete = bool(selected) and len(dated) == len(selected) and source_complete

    def bucket_hours(buckets):
        return sum(min((bucket + 1) * 600, end if end is not None else math.inf)
                   - max(bucket * 600, start if start is not None else -math.inf)
                   for bucket in buckets) / 3600

    project_active = bucket_hours({int(t // 600) for t in dated}) if complete else None
    agent_buckets = {(r["agent"], int(r["timestamp"] // 600)) for r in selected
                     if r.get("agent") is not None and r["timestamp"] is not None}
    agent_hours = (bucket_hours(bucket for _, bucket in agent_buckets)
                   if complete and all(r.get("agent") is not None for r in selected) else None)
    low, high = sum(g["usd_min"] for g in groups.values()), sum(g["usd_max"] for g in groups.values())
    priced = bool(selected) and not any(g["unpriced_records"] for g in groups.values())

    def per(denominator):
        return [low / denominator, high / denominator] if denominator and priced and source_complete else None

    return {"price_snapshot": {k: snapshot[k] for k in ("as_of", "source")},
            "basis": "List-price revaluation, not billing or subscription quota; intervals include unknown TTL/context tiers",
            "window": {"since": start, "until": end}, "groups": groups, "issues": dict(issues),
            "responses": len(selected), "priced_records_only_usd": [low, high], "fully_priced": priced,
            "source_complete": source_complete,
            "agent_hours_10min_buckets": agent_hours, "usd_per_agent_hour": per(agent_hours),
            "project_active_hours_10min_buckets": project_active,
            "usd_per_project_active_hour": per(project_active),
            "outcomes": outcomes, "usd_per_accepted_outcome": per(outcomes["accepted"]) if outcomes else None}


def table(result: dict) -> str:
    lines = [result["basis"], "", f"Price snapshot: {result['price_snapshot']['as_of']}", "",
             "| Group | Responses/runs | Input | Writes 5m / 1h / unknown | Reads | Output | Repriced USD range | Unpriced |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, group in sorted(result["groups"].items()):
        t = group["totals"]
        lines.append(f"| {name} | {group['responses']} | {t['input']} | {t['write_5m']} / {t['write_1h']} / {t['write_unknown']} | "
                     f"{t['read']} | {t['output']} | {group['usd_min']:.4f}-{group['usd_max']:.4f} | {group['unpriced_records']} |")
    lines.extend(("", f"Agent hours (10-minute buckets per transcript): {result['agent_hours_10min_buckets']}",
                  f"USD per agent hour: {result['usd_per_agent_hour']}",
                  f"Project activity hours (union of 10-minute buckets): {result['project_active_hours_10min_buckets']}",
                  f"USD per project activity hour: {result['usd_per_project_active_hour']}",
                  f"Accepted outcomes: {result['outcomes']}", f"USD per accepted outcome: {result['usd_per_accepted_outcome']}",
                  f"Recorded CLI USD is separate and available in --json; issues: {result['issues']}"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("transcripts", "rounds"):
        command = commands.add_parser(name)
        command.add_argument("directory", type=Path)
        command.add_argument("--since", help="inclusive ISO timestamp, with timezone")
        command.add_argument("--until", help="exclusive ISO timestamp, with timezone")
        command.add_argument("--prices", type=Path, default=PRICES)
        command.add_argument("--outcomes", type=Path, help="explicit accepted-outcome records")
        command.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args()
    try:
        start, end = timestamp(args.since), timestamp(args.until)
        if start is not None and end is not None and start >= end:
            raise ValueError("since must be earlier than until")
        if not args.directory.expanduser().is_dir():
            raise ValueError("the input directory must exist")
        issues = defaultdict(int)
        reader = transcript_records if args.command == "transcripts" else round_records
        records = reader(args.directory.expanduser(), issues)
        outcomes = accepted_outcomes(args.outcomes, start, end) if args.outcomes else None
        result = report(records, load_prices(args.prices), issues, start, end, outcomes)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2) if args.json else table(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
