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
COUNTERS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
ROUND_COUNTERS = ("inputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "outputTokens")


def count(value) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("token counts must be nonnegative integers")
    return value


def usage_sources(usage: dict) -> list[dict]:
    """Select flat counters or nested iterations, never both."""
    iterations = usage.get("iterations") or []
    if not any(count(usage.get(k)) for k in COUNTERS) and iterations:
        return [source for iteration in iterations for source in usage_sources(iteration)]
    return [usage]


def missing_counters(usage: dict, counters=COUNTERS) -> bool:
    sources = usage_sources(usage) if counters == COUNTERS else [usage]
    return any(source.get(k) is None for source in sources for k in counters)


def message_usage(message: dict) -> dict[str, int]:
    total = dict.fromkeys(KINDS, 0)
    for usage in usage_sources(message.get("usage") or {}):
        creation = usage.get("cache_creation") or {}
        w5 = count(creation.get("ephemeral_5m_input_tokens"))
        w1 = count(creation.get("ephemeral_1h_input_tokens"))
        written = count(usage.get("cache_creation_input_tokens", w5 + w1))
        if written < w5 + w1:
            raise ValueError("cache TTL counts exceed the reported cache writes")
        values = (count(usage.get("input_tokens")), w5, w1, written - w5 - w1,
                  count(usage.get("cache_read_input_tokens")), count(usage.get("output_tokens")))
        for kind, value in zip(KINDS, values):
            total[kind] += value
    return total


def location_key(location: str) -> tuple[str, int]:
    path, number = location.rsplit(":", 1)
    return path, int(number)


def events(path: Path, issues: dict):
    with path.open(encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("JSON line is not an object")
                yield number, event
            except (json.JSONDecodeError, ValueError):
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
    if "invalid_json_locations" in issues:
        issues["invalid_json_locations"].sort(key=location_key)


def timestamp(value: str | None) -> float | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.timestamp()


def file_own_activity(copies: dict) -> dict:
    # Preserve the existing copy order for equal-fullness token selection and output ordering.
    own_activity = {}
    for rows in copies.values():
        if len({r["path"] for r in rows}) == 1:
            for row in rows:
                if not row.get("has_activity", True):
                    continue
                path = row["path"]
                own_activity.setdefault(path, math.inf)
                if row["timestamp"] is not None:
                    own_activity[path] = min(own_activity.get(path, math.inf), row["timestamp"])
    return own_activity


def disputed_own_activity(responses: dict, paths: frozenset) -> dict:
    # Only dated responses unique among the files still in dispute establish a start.
    starts = {}
    for path in paths:
        rivals = set().union(*(responses[other] for other in paths if other != path))
        starts[path] = min((responses[path][key] for key in responses[path].keys() - rivals
                            if responses[path][key] is not None), default=math.inf)
    return starts


def standard_modifier(value, modifier: dict) -> bool:
    return value == "" or value in modifier["standard_values"]


def deduplicate_records(copies: dict, issues: dict, activity=None, snapshot=None) -> list[dict]:
    activity = copies if activity is None else activity
    own_activity = file_own_activity(activity)
    disputed_activity = {}
    snapshot = load_prices() if snapshot is None else snapshot
    responses = defaultdict(dict)
    for key, rows in activity.items():
        for row in rows:
            times = responses[row["path"]]
            previous = times.get(key)
            moment = row["timestamp"]
            times[key] = min(previous, moment) if previous is not None and moment is not None else (
                previous if moment is None else moment)
    last_response = {path: max((t for t in times.values() if t is not None), default=None)
                     for path, times in responses.items()}
    extensions = {}

    def copied_extension(original, extended):
        pair = original, extended
        if pair not in extensions:
            first, second = responses[original], responses[extended]
            last = last_response[original]
            extensions[pair] = (first.keys() < second.keys() and last is not None
                                and all(t is not None for t in first.values())
                                and all(second[key] is not None and second[key] >= last
                                        for key in second.keys() - first.keys()))
        return extensions[pair]

    def attribution(row):
        return (row["timestamp"] if row["timestamp"] is not None else math.inf,
                row["path"] not in own_activity,
                own_activity.get(row["path"], math.inf), row["path"],
                row["role"] + " " + row["model"], row["line"])

    def cumulative(new, old):
        return all(new["tokens"][k] >= old["tokens"][k] for k in KINDS)

    records, conflicts = [], set()
    for rows in copies.values():
        if len(rows) > 1:
            issues["duplicate_records"] += len(rows) - 1
        rows = sorted(rows, key=attribution)
        conflicting = set()
        for index, old in enumerate(rows):
            for new in rows[index + 1:]:
                if old["model"] != new["model"] or not (cumulative(new, old) or cumulative(old, new)):
                    conflicting.update((old["location"], new["location"]))
        tied = [row for row in rows if row["timestamp"] == rows[0]["timestamp"]]
        paths = {row["path"] for row in tied}
        dropped = {y for y in paths if any(copied_extension(x, y) for x in paths if x != y)}
        disputed = frozenset(paths - dropped)
        if disputed not in disputed_activity:
            disputed_activity[disputed] = disputed_own_activity(responses, disputed)
        starts = disputed_activity[disputed]
        chosen = dict(min((row for row in tied if row["path"] in disputed),
                          key=lambda row: (starts[row["path"]], row["path"],
                                           row["role"] + " " + row["model"], row["line"])))
        if conflicting:
            # Keep the attributed copy intact; conflicting totals are not reconcilable.
            conflicts.update(conflicting)
        else:
            fullest = max(rows, key=lambda r: (sum(r["tokens"].values()), not r["missing_counters"]))
            for field in ("tokens", "missing_counters", "recorded_cli_usd", "totals_from_lead"):
                if field in fullest:
                    chosen[field] = fullest[field]
                else:
                    chosen.pop(field, None)
            mismatch = set()
            for field, modifier in snapshot["modifiers"].items():
                for container in (None, "unattributed_modifiers"):
                    # A matched smaller lead copy cannot price a fuller total including helpers.
                    source = "lead_modifiers" if container is not None else None
                    known = [(row, values[field]) for row in rows
                             for values in [row if source is None else row.get(source, {})]
                             if values.get(field) is not None]
                    for index, (old, old_value) in enumerate(known):
                        for new, new_value in known[index + 1:]:
                            if old_value != new_value and not (
                                    standard_modifier(old_value, modifier)
                                    and standard_modifier(new_value, modifier)):
                                mismatch.update((old["location"], new["location"]))
                    if container is not None and fullest.get("totals_from_lead", False):
                        chosen[container] = {}
                        continue
                    values = [row if source is None else row.get(source, {})
                              for row in [fullest, *rows]]
                    value = next((v for v in values if v.get(field) is not None), None)
                    target = chosen if container is None else chosen.get(container, {}).copy()
                    if value is not None:
                        target[field] = value[field]
                    else:
                        target.pop(field, None)
                    if container is not None and (target or container in chosen):
                        chosen[container] = target
            if mismatch:
                chosen["modifier_mismatch_locations"] = sorted(mismatch, key=location_key)
        records.append(chosen)
    if conflicts:
        issues["conflicting_copies"] += len(conflicts)
        issues.setdefault("conflicting_copy_locations", []).extend(conflicts)
        issues["conflicting_copy_locations"].sort(key=location_key)
    return sorted(records, key=attribution)


def transcript_records(directory: Path, issues: dict, snapshot=None) -> list[dict]:
    copies = defaultdict(list)
    activity = defaultdict(list)
    for path in directory.rglob("*.jsonl"):
        role = "subagent" if "subagents" in path.parts else "session"
        meta = path.with_suffix(".meta.json")
        if role == "subagent" and meta.exists():
            role = json.loads(meta.read_text()).get("agentType") or role
        for number, event in events(path, issues):
            message = event.get("message")
            if event.get("type") != "assistant" or not isinstance(message, dict):
                continue
            key = message.get("id") or event.get("uuid") or (str(path), number)
            if "usage" in message:
                moment = timestamp(event.get("timestamp"))
            else:
                value = event.get("timestamp")
                try:
                    moment = timestamp(value) if isinstance(value, str) else None
                except (ValueError, OverflowError, OSError):
                    moment = None
            activity[key].append({"path": str(path), "timestamp": moment,
                                  "has_activity": "usage" in message or moment is not None})
            if "usage" not in message:
                continue
            usage = message.get("usage") or {}
            record = {"model": message.get("model") or "unknown", "role": role,
                      "agent": str(path.resolve()),
                      "path": str(path), "line": number, "location": f"{path}:{number}",
                      "timestamp": moment, "aggregate": False,
                      "tokens": message_usage(message), "recorded_cli_usd": None,
                      "missing_counters": missing_counters(usage),
                      **{k: usage[k] for k in ("speed", "inference_geo") if k in usage}}
            copies[key].append(record)
    return deduplicate_records(copies, issues, activity, snapshot)


def result_records(result: dict) -> list[dict]:
    usage = result.get("modelUsage") or {}
    own = message_usage(result)
    rows = []
    for model, values in usage.items():
        metadata = values
        # Lead modifiers cannot be assigned to totals that also include helpers.
        unattributed = {k: result["usage"][k] for k in ("speed", "inference_geo")
                        if k in (result.get("usage") or {})}
        lead_modifiers = unattributed.copy()
        missing = missing_counters(values, ROUND_COUNTERS)
        totals = dict(zip(KINDS, (count(values.get("inputTokens")), 0, 0,
                                  count(values.get("cacheCreationInputTokens")),
                                  count(values.get("cacheReadInputTokens")), count(values.get("outputTokens")))))
        # A result's usage can cover only the lead, while modelUsage includes helpers.
        if len(usage) == 1 and all(totals[k] == own[k] for k in ("input", "read", "output")) and (
                totals["write_unknown"] == sum(own[k] for k in KINDS if k.startswith("write_"))):
            totals = own
            metadata = result.get("usage") or values
            unattributed = {}
            if result.get("usage"):
                missing = missing or missing_counters(result["usage"])
        recorded = values.get("costUSD")
        if recorded is not None and (not isinstance(recorded, (int, float)) or isinstance(recorded, bool)
                                     or not math.isfinite(recorded) or recorded < 0):
            raise ValueError("recorded CLI costs must be nonnegative numbers")
        rows.append({"model": model, "role": "audit", "timestamp": timestamp(result.get("timestamp")),
                     "aggregate": True, "tokens": totals, "recorded_cli_usd": recorded,
                     "missing_counters": missing, "unattributed_modifiers": unattributed,
                     "totals_from_lead": totals is own, "lead_modifiers": lead_modifiers,
                     **{k: metadata[k] for k in ("speed", "inference_geo") if k in metadata}})
    return rows


def round_records(directory: Path, issues: dict, snapshot=None) -> list[dict]:
    copies = defaultdict(list)
    for path in directory.rglob("*.jsonl"):
        if path.parent.name != "streams" or ".login-failure-" in path.name or path.name.startswith("warmup"):
            continue
        last = None
        for number, event in events(path, issues):
            if event.get("type") == "result":
                last = event
                last_number = number
        if last is None or not last.get("modelUsage"):
            issues["streams_without_model_totals"] += 1
            continue
        identity = last.get("uuid") or str(path)
        for record in result_records(last):
            record.update(path=str(path), line=last_number, location=f"{path}:{last_number}")
            copies[(identity, record["model"])].append(record)
    return deduplicate_records(copies, issues, snapshot=snapshot)


def load_prices(path: Path = PRICES) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not snapshot.get("as_of") or not snapshot.get("source") or not snapshot.get("models"):
        raise ValueError("a price snapshot needs as_of, source, and models")
    if "modifiers" not in snapshot:
        raise ValueError(f"price snapshot {path} is missing required key: modifiers")
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
    for field in ("speed", "inference_geo"):
        modifier = snapshot["modifiers"][field]
        value = modifier["multiplier"]
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or value <= 0 or not isinstance(modifier.get("models"), list) or not modifier["models"]
                or not all(isinstance(model, str) and model for model in modifier["models"])
                or not modifier.get("source")
                or not modifier.get("as_of") or not isinstance(modifier.get("standard_values"), list)
                or not all(isinstance(item, str) for item in modifier["standard_values"])
                or not isinstance(modifier.get("value"), str) or not modifier["value"]
                or modifier["value"] in modifier["standard_values"]):
            raise ValueError("modifiers need a positive multiplier, models, source, date, and standard values")
    return snapshot


def pricing_multiplier(record: dict, snapshot: dict) -> float | None:
    multiplier = 1.0
    for field, modifier in snapshot["modifiers"].items():
        unattributed = record.get("unattributed_modifiers", {})
        if unattributed.get(field) is not None and not standard_modifier(unattributed[field], modifier):
            return None
        if record.get(field) is None:
            continue
        value = record[field]
        if standard_modifier(value, modifier):
            continue
        if value != modifier["value"] or record["model"] not in modifier["models"]:
            return None
        multiplier *= modifier["multiplier"]
    return multiplier


def price_interval(record: dict, snapshot: dict) -> tuple[float, float] | None:
    multiplier = pricing_multiplier(record, snapshot)
    if record.get("missing_counters") or record.get("modifier_mismatch_locations") or multiplier is None:
        return None
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
        costs.extend(multiplier * (fixed + tokens["write_unknown"] * card[ttl]) / 1e6
                     for ttl in ("write_5m", "write_1h"))
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
        if record.get("modifier_mismatch_locations"):
            issues["records_modifier_mismatch"] += 1
            locations = issues.setdefault("modifier_mismatch_locations", [])
            locations[:] = sorted(set(locations) | set(record["modifier_mismatch_locations"]), key=location_key)
        if record.get("missing_counters"):
            issues["records_missing_counters"] += 1
        if pricing_multiplier(record, snapshot) is None:
            issues["records_unsupported_modifiers"] += 1
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
                                   ("streams_without_model_totals", "undated_records_excluded", "conflicting_copies")))
    complete = bool(selected) and len(dated) == len(selected) and source_complete

    def bucket_hours(buckets):
        return sum(min((bucket + 1) * 600, end if end is not None else math.inf)
                   - max(bucket * 600, start if start is not None else -math.inf)
                   for bucket in buckets) / 3600

    # A round total is dated at its end only, so one bucket would not be its activity.
    project_active = (bucket_hours({int(t // 600) for t in dated})
                      if complete and not any(r["aggregate"] for r in selected) else None)
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
        snapshot = load_prices(args.prices)
        records = reader(args.directory.expanduser(), issues, snapshot)
        outcomes = accepted_outcomes(args.outcomes, start, end) if args.outcomes else None
        result = report(records, snapshot, issues, start, end, outcomes)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2) if args.json else table(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
