"""Regressions for duplicated history, missing cache TTLs, pricing tiers and denominators."""

import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

from tools.claude_ledger import (KINDS, accepted_outcomes, load_prices, message_usage,
                                price_interval, report, result_records, round_records,
                                table, timestamp, transcript_records)


def response(identifier, model="claude-opus-5-5", moment="2026-10-22T12:00:00Z", **usage):
    return {"type": "assistant", "timestamp": moment,
            "message": {"id": identifier, "model": model, "usage": usage}}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def record(model="claude-opus-5-5", aggregate=False, **tokens):
    return {"model": model, "role": "session", "aggregate": aggregate,
            "agent": "fixture.jsonl",
            "timestamp": timestamp("2026-10-22T12:00:00Z"),
            "tokens": {k: tokens.get(k, 0) for k in KINDS}, "recorded_cli_usd": None}


class LedgerTests(unittest.TestCase):
    def test_copied_history_counts_once_across_files_and_preserves_mixed_models(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = response("m1", cache_read_input_tokens=1000)
            write(root / "a.jsonl", [first, first, response("m2", "claude-sonnet-5-5", output_tokens=20)])
            write(root / "carried.jsonl", [first])
            issues = defaultdict(int)
            rows = transcript_records(root, issues)
        self.assertEqual(len(rows), 2)
        self.assertEqual(issues["duplicate_records"], 2)
        self.assertEqual({r["model"] for r in rows}, {"claude-opus-5-5", "claude-sonnet-5-5"})

    def test_roles_come_from_metadata_instead_of_review_words_in_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session/subagents/agent-1.jsonl"
            write(path, [{"type": "user", "message": {"content": "Fix the reviewer's findings"}},
                         response("m1", "claude-sonnet-5-5", output_tokens=20)])
            path.with_suffix(".meta.json").write_text('{"agentType": "lab-implementer"}')
            self.assertEqual(transcript_records(Path(directory), defaultdict(int))[0]["role"], "lab-implementer")

    def test_nested_usage_is_recovered_without_counting_iterations_twice(self):
        nested = {"input_tokens": 2, "output_tokens": 7, "cache_read_input_tokens": 300,
                  "cache_creation_input_tokens": 10, "cache_creation": {"ephemeral_1h_input_tokens": 10}}
        self.assertEqual(message_usage({"usage": {"iterations": [nested]}})["read"], 300)
        flat = dict(nested, iterations=[nested])
        self.assertEqual(message_usage({"usage": flat})["output"], 7)

    def test_unknown_ttl_is_not_assigned_to_five_minutes(self):
        tokens = message_usage({"usage": {"cache_creation_input_tokens": 500}})
        self.assertEqual((tokens["write_5m"], tokens["write_1h"], tokens["write_unknown"]), (0, 0, 500))

    def test_known_ttls_and_remaining_unknown_tokens_are_conserved(self):
        tokens = message_usage({"usage": {"cache_creation_input_tokens": 500, "cache_creation":
                                          {"ephemeral_5m_input_tokens": 100, "ephemeral_1h_input_tokens": 300}}})
        self.assertEqual((tokens["write_5m"], tokens["write_1h"], tokens["write_unknown"]), (100, 300, 100))

    def test_invalid_counts_and_inconsistent_ttls_are_rejected(self):
        for usage in ({"input_tokens": -1}, {"output_tokens": True},
                      {"cache_creation_input_tokens": 2, "cache_creation": {"ephemeral_1h_input_tokens": 3}}):
            with self.subTest(usage=usage), self.assertRaises(ValueError):
                message_usage({"usage": usage})

    def test_zero_placeholder_is_replaced_by_complete_response(self):
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory) / "a.jsonl", [response("m1"), response("m1", output_tokens=100)])
            rows = transcript_records(Path(directory), defaultdict(int))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tokens"]["output"], 100)

    def test_conflicting_non_cumulative_usage_fails_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory) / "a.jsonl", [response("m1", input_tokens=10), response("m1", output_tokens=10)])
            with self.assertRaises(ValueError):
                transcript_records(Path(directory), defaultdict(int))

    def test_conflicting_models_for_one_response_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory) / "a.jsonl", [response("m1"), response("m1", "claude-sonnet-5-5")])
            with self.assertRaisesRegex(ValueError, "conflicting models"):
                transcript_records(Path(directory), defaultdict(int))

    def test_read_prices_differ_by_exact_model(self):
        prices = load_prices()
        self.assertEqual(price_interval(record(read=1000000), prices), (0.2, 0.2))
        self.assertEqual(price_interval(record("claude-sonnet-5-5", read=1000000), prices), (0.1, 0.1))
        self.assertIsNone(price_interval(record("glm-5.3", read=1000000), prices))

    def test_zero_token_unknown_models_cost_zero_and_stay_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory) / "a.jsonl", [response("paid", output_tokens=1000000),
                                               response("zero", "<synthetic>")])
            result = report(transcript_records(Path(directory), defaultdict(int)), load_prices(), defaultdict(int),
                            outcomes={"accepted": 1, "unit": "change", "source": "test"})
        self.assertEqual(result["responses"], 2)
        self.assertEqual(result["groups"]["session <synthetic>"]["responses"], 1)
        self.assertEqual(result["groups"]["session <synthetic>"]["unpriced_records"], 0)
        self.assertEqual(result["priced_records_only_usd"], [20.0, 20.0])
        self.assertTrue(result["fully_priced"])
        self.assertEqual(result["usd_per_agent_hour"], [120.0, 120.0])
        self.assertEqual(result["usd_per_accepted_outcome"], [20.0, 20.0])
        self.assertEqual(price_interval(record("<synthetic>", aggregate=True), load_prices()), (0.0, 0.0))

    def test_invalid_lines_are_counted_in_both_readers(self):
        for reader in (transcript_records, round_records):
            with self.subTest(reader=reader.__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "streams/a.jsonl"
                write(path, [])
                path.write_text('{broken\n\0still broken\n')
                issues = defaultdict(int)
                reader(Path(directory), issues)
                self.assertEqual(issues["invalid_json_lines"], 2)

    def test_invalid_line_suppresses_all_normalizers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("paid", output_tokens=1000000)])
            with path.open("a") as stream:
                stream.write('broken\n')
            issues = defaultdict(int)
            result = report(transcript_records(Path(directory), issues), load_prices(), issues,
                            outcomes={"accepted": 1, "unit": "change", "source": "test"})
        self.assertFalse(result["source_complete"])
        self.assertEqual(result["responses"], 1)
        self.assertEqual(result["priced_records_only_usd"], [20.0, 20.0])
        for key in ("agent_hours_10min_buckets", "project_active_hours_10min_buckets", "usd_per_agent_hour",
                    "usd_per_project_active_hour", "usd_per_accepted_outcome"):
            self.assertIsNone(result[key], key)

    def test_haiku_tier_counts_cached_input_and_prices_the_whole_request(self):
        prices = load_prices()
        low = price_interval(record("claude-haiku-5-5", read=100000, output=1000000), prices)
        high = price_interval(record("claude-haiku-5-5", read=100001, output=1000000), prices)
        self.assertAlmostEqual(low[0], 0.501)
        self.assertAlmostEqual(high[0], 2.50500005)

    def test_unknown_write_ttl_and_aggregate_haiku_have_price_intervals(self):
        prices = load_prices()
        self.assertEqual(price_interval(record(write_unknown=1000000), prices), (5.0, 8.0))
        self.assertEqual(price_interval(record("claude-haiku-5-5", aggregate=True, output=1000000), prices),
                         (0.5, 2.5))

    def test_round_keeps_last_result_and_deduplicates_its_archived_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            early = {"type": "result", "uuid": "early", "modelUsage": {"glm-5.3": {"outputTokens": 1}}}
            last = {"type": "result", "uuid": "last", "modelUsage":
                    {"glm-5.3": {"outputTokens": 30, "cacheReadInputTokens": 500, "costUSD": 9}}}
            write(root / "round1/real/streams/run1-case.jsonl", [early, last])
            write(root / "archive/streams/run1-case.jsonl", [last])
            write(root / "round1/streams/run1-case.login-failure-1.jsonl", [dict(last, uuid="failed")])
            write(root / "round1/streams/warmup-opus.jsonl", [dict(last, uuid="warmup")])
            issues = defaultdict(int)
            rows = round_records(root, issues)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tokens"]["output"], 30)
        self.assertEqual(rows[0]["recorded_cli_usd"], 9)
        self.assertIsNone(price_interval(rows[0], load_prices()))

    def test_invalid_recorded_cli_costs_are_rejected(self):
        for cost in (-1, True, "1", float("nan"), float("inf")):
            with self.subTest(cost=cost), self.assertRaisesRegex(ValueError, "recorded CLI costs"):
                result_records({"modelUsage": {"claude-opus-5-5": {"outputTokens": 1, "costUSD": cost}}})

    def test_lead_ttl_is_not_extrapolated_to_helper_totals(self):
        event = {"usage": {"cache_creation_input_tokens": 10, "output_tokens": 1,
                           "cache_creation": {"ephemeral_1h_input_tokens": 10}},
                 "modelUsage": {"claude-sonnet-5-5": {"cacheCreationInputTokens": 40, "outputTokens": 5}}}
        row = result_records(event)[0]
        self.assertEqual(row["tokens"]["write_unknown"], 40)
        event["modelUsage"]["claude-sonnet-5-5"].update(cacheCreationInputTokens=10, outputTokens=1)
        self.assertEqual(result_records(event)[0]["tokens"]["write_1h"], 10)

    def test_missing_round_result_is_reported_and_suppresses_per_outcome_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            write(Path(directory) / "round/streams/failed.jsonl", [{"type": "system"}])
            issues = defaultdict(int)
            self.assertEqual(round_records(Path(directory), issues), [])
            result = report([record(output=100)], load_prices(), issues,
                            outcomes={"accepted": 1, "unit": "change", "source": "test"})
        self.assertFalse(result["source_complete"])
        self.assertIsNone(result["usd_per_accepted_outcome"])

    def test_half_open_window_and_occupied_ten_minute_buckets(self):
        start, end = timestamp("2026-10-22T12:00:00Z"), timestamp("2026-10-22T12:20:00Z")
        rows = [record(output=1000000) for _ in range(4)]
        for row, moment in zip(rows, (start - 1, start, start + 600, end)):
            row["timestamp"] = moment
        result = report(rows, load_prices(), defaultdict(int), start, end,
                        {"accepted": 2, "unit": "change", "source": "test"})
        self.assertEqual(result["responses"], 2)
        self.assertAlmostEqual(result["agent_hours_10min_buckets"], 1 / 3)
        self.assertAlmostEqual(result["project_active_hours_10min_buckets"], 1 / 3)
        self.assertEqual(result["usd_per_accepted_outcome"], [20.0, 20.0])
        self.assertAlmostEqual(result["usd_per_agent_hour"][0], 120.0)
        self.assertAlmostEqual(result["usd_per_project_active_hour"][0], 120.0)
        with self.assertRaises(ValueError):
            timestamp("2026-10-22T12:00:00")

    def test_agent_hour_contract_parallel_waiting_overlapping_and_reimported_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            times = [f"2026-10-22T12:{minute:02d}:00Z" for minute in range(0, 60, 5)]
            paths = [root / "lead.jsonl", root / "lead/subagents/agent-a.jsonl",
                     root / "lead/subagents/agent-b.jsonl"]
            for agent, path in enumerate(paths):
                write(path, [response(f"{agent}-{index}", moment=moment, output_tokens=1000)
                             for index, moment in enumerate(times)])

            def measure():
                issues = defaultdict(int)
                return report(transcript_records(root, issues), load_prices(), issues)

            busy = measure()
            self.assertEqual(busy["responses"], 36)
            self.assertEqual(busy["agent_hours_10min_buckets"], 3.0)
            self.assertEqual(busy["project_active_hours_10min_buckets"], 1.0)
            self.assertAlmostEqual(busy["usd_per_agent_hour"][0], 0.24)
            self.assertAlmostEqual(busy["usd_per_project_active_hour"][0], 0.72)
            rendered = table(busy)
            self.assertIn("Agent hours (10-minute buckets per transcript): 3.0", rendered)
            self.assertIn("Project activity hours (union of 10-minute buckets): 1.0", rendered)
            # Re-reading the identical file must not add responses, cost, or buckets.
            with patch.object(Path, "rglob", return_value=iter([*paths, paths[0]])):
                repeated = measure()
            for key in ("responses", "priced_records_only_usd", "agent_hours_10min_buckets",
                        "project_active_hours_10min_buckets", "usd_per_agent_hour"):
                self.assertEqual(repeated[key], busy[key], key)
            write(paths[0], [response("lead-start", moment=times[0], output_tokens=1000),
                             response("lead-end", moment="2026-10-22T12:59:00Z", output_tokens=1000)])
            waiting = measure()
            self.assertEqual(waiting["responses"], 26)
            self.assertAlmostEqual(waiting["agent_hours_10min_buckets"], 2 + 1 / 3)
            self.assertEqual(waiting["project_active_hours_10min_buckets"], 1.0)

    def test_agent_and_project_buckets_are_clipped_at_each_window_edge(self):
        for start_text, end_text, moment_text, seconds in (
                ("12:08:00", "12:10:00", "12:09:00", 120),
                ("12:00:00", "12:02:00", "12:01:00", 120),
                ("12:08:00", "12:12:00", "12:09:00", 120),
                ("12:08:00", "12:09:00", "12:08:30", 60)):
            with self.subTest(start=start_text, end=end_text):
                start, end, moment = [timestamp(f"2026-10-22T{t}Z")
                                      for t in (start_text, end_text, moment_text)]
                row = record(output=1000000)
                row["timestamp"] = moment
                result = report([row], load_prices(), defaultdict(int), start, end)
                self.assertAlmostEqual(result["agent_hours_10min_buckets"], seconds / 3600)
                self.assertAlmostEqual(result["project_active_hours_10min_buckets"], seconds / 3600)
                self.assertAlmostEqual(result["usd_per_agent_hour"][0], 20 / (seconds / 3600))

    def test_dated_round_totals_do_not_invent_agent_identity(self):
        rows = result_records({"timestamp": "2026-10-22T12:00:00Z", "modelUsage":
                               {"claude-opus-5-5": {"outputTokens": 1000}}})
        result = report(rows, load_prices(), defaultdict(int))
        self.assertIsNone(result["agent_hours_10min_buckets"])
        self.assertIsNone(result["usd_per_agent_hour"])
        self.assertEqual(result["project_active_hours_10min_buckets"], 1 / 6)

    def test_undated_and_unpriced_records_do_not_produce_false_normalizers(self):
        undated = record()
        undated["timestamp"] = None
        result = report([undated], load_prices(), defaultdict(int), start=0)
        self.assertEqual(result["issues"]["undated_records_excluded"], 1)
        self.assertIsNone(result["agent_hours_10min_buckets"])
        self.assertIsNone(result["project_active_hours_10min_buckets"])
        result = report([undated], load_prices(), defaultdict(int))
        self.assertEqual(result["responses"], 1)
        self.assertIsNone(result["agent_hours_10min_buckets"])
        self.assertIsNone(result["project_active_hours_10min_buckets"])
        self.assertIsNone(result["usd_per_agent_hour"])
        result = report([record("unknown", read=1000)], load_prices(), defaultdict(int),
                        outcomes={"accepted": 1, "unit": "change", "source": "test"})
        self.assertFalse(result["fully_priced"])
        self.assertIsNone(result["usd_per_accepted_outcome"])

    def test_outcomes_are_explicit_deduplicated_and_filtered_to_the_same_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outcomes.json"
            doc = {"unit": "merged change", "source": "review receipts", "items":
                   [{"id": "a", "completed_at": "2026-10-22T12:00:00Z", "status": "accepted"},
                    {"id": "b", "completed_at": "2026-10-22T12:10:00Z", "status": "rejected"},
                    {"id": "c", "completed_at": "2026-10-22T12:20:00Z", "status": "accepted"}]}
            path.write_text(json.dumps(doc))
            result = accepted_outcomes(path, timestamp("2026-10-22T12:00:00Z"), timestamp("2026-10-22T12:20:00Z"))
            self.assertEqual(result["accepted"], 1)
            doc["items"].append(doc["items"][0])
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                accepted_outcomes(path, None, None)

    def test_invalid_price_snapshot_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.json"
            prices = load_prices()
            prices["models"]["claude-opus-5-5"][0]["read"] = float("nan")
            path.write_text(json.dumps(prices))
            with self.assertRaises(ValueError):
                load_prices(path)


if __name__ == "__main__":
    unittest.main()
