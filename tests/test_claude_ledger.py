"""Regressions for duplicated history, missing cache TTLs, pricing tiers and denominators."""

import io
import json
import tempfile
import unittest
from collections import defaultdict
from itertools import permutations
from pathlib import Path
from unittest.mock import patch

from tools.claude_ledger import (KINDS, accepted_outcomes, load_prices, main, message_usage,
                                price_interval, report, result_records, round_records,
                                table, timestamp, transcript_records)

COUNTERS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
ROUND_COUNTERS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")


def response(identifier, model="claude-opus-5-5", moment="2026-10-22T12:00:00Z", **usage):
    return {"type": "assistant", "timestamp": moment,
            "message": {"id": identifier, "model": model, "usage": dict.fromkeys(COUNTERS, 0) | usage}}


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def record(model="claude-opus-5-5", aggregate=False, **tokens):
    return {"model": model, "role": "session", "aggregate": aggregate,
            "agent": "fixture.jsonl",
            "timestamp": timestamp("2026-10-22T12:00:00Z"),
            "tokens": {k: tokens.get(k, 0) for k in KINDS}, "recorded_cli_usd": None}


class LedgerTests(unittest.TestCase):
    def read_orders(self, root, paths, reader=transcript_records, snapshot=None):
        snapshot = load_prices() if snapshot is None else snapshot
        results = []
        orders = permutations(paths) if 3 <= len(paths) <= 5 else (paths, paths[::-1])
        for order in orders:
            issues = defaultdict(int)
            with patch.object(Path, "rglob", return_value=iter(order)):
                rows = reader(root, issues, snapshot)
            results.append((rows, report(rows, snapshot, issues)))
        for result in results[1:]:
            self.assertEqual(results[0], result)
        return results[0]

    def test_containment_chain_keeps_three_two_and_one_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Paths deliberately favor the last resumption if containment is skipped.
            a, b, c = [root / name for name in ("z.jsonl", "m.jsonl", "a.jsonl")]
            events = [response(str(i), moment=f"2026-10-22T12:{i * 10:02}:00Z", output_tokens=i + 1)
                      for i in range(6)]
            for path, length in ((a, 3), (b, 5), (c, 6)):
                write(path, events[:length])
            rows, result = self.read_orders(root, [a, b, c])
        self.assertEqual([sum(r["path"] == str(p) for r in rows) for p in (a, b, c)], [3, 2, 1])
        self.assertEqual([r["tokens"]["output"] for r in rows], [1, 2, 3, 4, 5, 6])
        self.assertEqual(result["responses"], 6)
        self.assertEqual(result["agent_hours_10min_buckets"], 1)

    def test_full_resume_and_tail_only_resume_leave_original_responses_in_place(self):
        for tail_only in (False, True):
            with self.subTest(tail_only=tail_only), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                original, resumed = root / "z.jsonl", root / "a.jsonl"
                events = [response(str(i), moment=f"2026-10-22T12:{i * 10:02}:00Z", output_tokens=i + 1)
                          for i in range(4)]
                write(original, events)
                write(resumed, events[2:] if tail_only else events + [response(
                    "new", moment="2026-10-22T12:40:00Z", output_tokens=5)])
                rows, _ = self.read_orders(root, [original, resumed])
                self.assertEqual([r["path"] for r in rows if r["tokens"]["output"] <= 4], [str(original)] * 4)
                self.assertEqual(len(rows), 4 if tail_only else 5)

    def test_containment_requires_every_extra_response_to_be_dated_and_at_or_after_last(self):
        for extras, winner in ((["2026-10-22T12:00:00Z"], "z"),
                               (["2026-10-22T11:59:59Z"], "a"),
                               ([None], "a"),
                               (["2026-10-22T13:00:00Z", None], "a"),
                               (["2026-10-22T11:00:00Z", "2026-10-22T13:00:00Z"], "a")):
            with self.subTest(extras=extras), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, z = root / "a.jsonl", root / "z.jsonl"
                shared = response("shared", output_tokens=1)
                write(z, [shared])
                write(a, [shared] + [response(f"extra-{i}", moment=t) for i, t in enumerate(extras)])
                rows, _ = self.read_orders(root, [a, z])
                owner = next(r for r in rows if r["tokens"]["output"])
                self.assertEqual(owner["path"], str(root / f"{winner}.jsonl"))

    def test_containment_needs_a_dated_original_response_and_equal_sets_use_path(self):
        for shared_time, extra_time in ((None, None), (None, "2026-10-22T13:00:00Z"),
                                        ("2026-10-22T12:00:00Z", "equal-set")):
            with self.subTest(shared=shared_time, extra=extra_time), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, z = root / "a.jsonl", root / "z.jsonl"
                shared = response("shared", moment=shared_time, output_tokens=1)
                write(z, [shared])
                write(a, [shared] + ([] if extra_time == "equal-set" else [response("extra", moment=extra_time)]))
                rows, _ = self.read_orders(root, [a, z])
                self.assertEqual(next(r for r in rows if r["tokens"]["output"])["path"], str(a))

    def test_containment_only_compares_files_tied_on_the_earliest_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            write(z, [response("shared", moment="2026-10-22T12:01:00Z", output_tokens=100)])
            write(a, [response("shared", output_tokens=1), response("extra", moment="2026-10-22T13:00:00Z")])
            rows, _ = self.read_orders(root, [a, z])
        shared = next(r for r in rows if r["tokens"]["output"])
        self.assertEqual(shared["path"], str(a))
        self.assertEqual(shared["tokens"]["output"], 100)
        self.assertEqual(shared["timestamp"], timestamp("2026-10-22T12:00:00Z"))

    def test_any_undated_response_in_subset_blocks_containment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            shared = [response("dated", output_tokens=1), response("undated", moment=None, output_tokens=2)]
            write(z, shared)
            write(a, shared + [response("extra", moment="2026-10-22T13:00:00Z")])
            rows, _ = self.read_orders(root, [a, z])
        self.assertEqual([r["path"] for r in rows if r["tokens"]["output"]], [str(a)] * 2)

    def test_subset_dates_are_read_in_the_subset_file_itself(self):
        # u is undated in z, so z's set is not fully dated, though a dates u.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            write(z, [response("d", output_tokens=1), response("u", moment=None, output_tokens=2)])
            write(a, [response("d", output_tokens=1), response("u", moment="2026-10-22T12:30:00Z", output_tokens=2),
                      response("e", moment="2026-10-22T13:00:00Z", output_tokens=3)])
            rows, _ = self.read_orders(root, [a, z])
        self.assertEqual([r["path"] for r in rows if r["tokens"]["output"]], [str(a)] * 3)

    def test_containment_uses_each_keys_earliest_timestamp_in_each_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            early = response("first", moment="2026-10-22T10:00:00Z", output_tokens=1)
            shared = response("shared", output_tokens=2)
            write(z, [early, response("first", moment=None, output_tokens=1), shared,
                      response("first", moment="2026-10-22T14:00:00Z", output_tokens=10)])
            write(a, [early, shared, response("extra", moment="2026-10-22T13:00:00Z")])
            rows, _ = self.read_orders(root, [a, z])
        self.assertEqual([r["path"] for r in rows if r["tokens"]["output"]], [str(z)] * 2)
        self.assertEqual(sum(r["tokens"]["output"] for r in rows), 12)

    def test_containment_response_sets_include_usageless_assistant_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            shared = response("shared", output_tokens=1)
            extra = response("extra", moment="2026-10-22T13:00:00Z")
            del extra["message"]["usage"]
            write(z, [shared])
            write(a, [shared, extra])
            rows, _ = self.read_orders(root, [a, z])
        self.assertEqual(rows[0]["path"], str(z))

    def test_repeated_key_uses_earliest_time_even_when_later_line_is_earlier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            shared = response("shared", output_tokens=1)
            write(z, [shared])
            write(a, [shared, response("extra", moment="2026-10-22T13:00:00Z", output_tokens=2),
                      response("extra", moment="2026-10-22T11:00:00Z", output_tokens=2)])
            rows, _ = self.read_orders(root, [a, z])
        self.assertEqual([r["path"] for r in rows], [str(a)] * 2)

    def test_dropped_tied_file_can_still_drop_another_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, x, y = [root / f"{name}.jsonl" for name in ("a", "x", "y")]
            shared = response("a", output_tokens=1)
            write(x, [shared])
            write(y, [shared, response("b", moment="2026-10-22T12:10:00Z", output_tokens=2)])
            write(a, [shared, response("b", moment="2026-10-22T11:00:00Z", output_tokens=2),
                      response("c", moment="2026-10-22T12:20:00Z", output_tokens=3)])
            rows, _ = self.read_orders(root, [a, x, y])
        self.assertEqual({r["tokens"]["output"]: r["path"] for r in rows}, {1: str(x), 2: str(a), 3: str(a)})

    def test_own_activity_excludes_dropped_rivals_for_original_full_copy_and_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            z, x, w = [root / f"{name}.jsonl" for name in ("z", "x", "w")]
            original = [response(f"z{i}", moment=f"2026-10-22T1{i}:00:00Z", output_tokens=i + 1)
                        for i in range(3)]
            write(z, original)
            write(x, original + [response("x1", moment="2026-10-22T14:00:00Z", output_tokens=4)])
            write(w, original[-1:] + [response("w1", moment="2026-10-22T13:00:00Z", output_tokens=5)])
            rows, _ = self.read_orders(root, [z, x, w])
        self.assertEqual([sum(r["path"] == str(p) for r in rows) for p in (z, x, w)], [3, 1, 1])

    def test_own_activity_uses_per_file_earliest_time_without_outside_rivals(self):
        for own_time, winner in (("11:00", "z"), ("11:45", "a")):
            with self.subTest(own_time=own_time), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, z, outside = [root / f"{name}.jsonl" for name in ("a", "z", "outside")]
                shared = response("shared", output_tokens=1)
                write(a, [shared, response("own-a", moment="2026-10-22T11:30:00Z")])
                write(z, [shared, response("own-z", moment="2026-10-22T13:00:00Z"),
                          response("own-z", moment=f"2026-10-22T{own_time}:00Z")])
                write(outside, [response("own-z", moment="2026-10-22T10:00:00Z")])
                rows, _ = self.read_orders(root, [a, z, outside])
                owner = next(r for r in rows if r["tokens"]["output"])
                self.assertEqual(owner["path"], str(root / f"{winner}.jsonl"))

    def test_round_own_activity_ignores_undated_responses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = [root / name / "streams/run.jsonl" for name in ("a", "z")]
            for path, models in ((a, ["shared"]), (z, ["shared", "own-z"])):
                write(path, [{"type": "result", "uuid": "shared", "modelUsage": {
                    model: dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 1} for model in models}}])
            rows, _ = self.read_orders(root, [a, z], round_records)
        self.assertEqual(next(r for r in rows if r["model"] == "shared")["path"], str(a))

    def test_four_and_five_file_chains_are_independent_of_every_read_order(self):
        for length in (4, 5):
            with self.subTest(length=length), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [root / f"{length - i}.jsonl" for i in range(length)]
                events = [response(str(i), moment=f"2026-10-22T12:{i:02}:00Z", output_tokens=i + 1)
                          for i in range(length * 2)]
                for i, path in enumerate(paths):
                    write(path, events[:(i + 1) * 2])
                rows, _ = self.read_orders(root, paths)
                self.assertEqual([sum(r["path"] == str(p) for r in rows) for p in paths], [2] * length)

    def test_bad_usageless_timestamps_still_participate_in_containment_sets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            shared = response("shared", output_tokens=1)
            extra = {"type": "assistant", "timestamp": "bad", "message": {"id": "extra"}}
            # The unknown extra prevents z from being dropped as an extension of a.
            write(a, [shared])
            write(z, [shared, extra, response("own-z", moment="2026-10-22T13:00:00Z")])
            rows, _ = self.read_orders(root, [a, z])
        self.assertEqual(next(r for r in rows if r["tokens"]["output"])["path"], str(z))

    def test_round_reader_uses_the_same_containment_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b, c = [root / name / "streams/run.jsonl" for name in ("z", "m", "a")]
            for path, length in ((a, 3), (b, 5), (c, 6)):
                write(path, [{"type": "result", "uuid": "shared", "timestamp": "2026-10-22T12:00:00Z",
                              "modelUsage": {f"model-{i}": dict.fromkeys(ROUND_COUNTERS, 0)
                                             | {"outputTokens": i + 1} for i in range(length)}}])
            rows, _ = self.read_orders(root, [a, b, c], round_records)
        self.assertEqual([sum(r["path"] == str(p) for r in rows) for p in (a, b, c)], [3, 2, 1])

    def test_modifier_only_mismatch_is_unpriced_even_when_every_other_field_is_equal(self):
        for field, values in (("speed", ("fast", "standard")), ("inference_geo", ("us", "global")),
                              ("inference_geo", ("us", ""))):
            for output in (0, 100):
                with self.subTest(field=field, output=output), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    path = root / "a.jsonl"
                    write(path, [response("shared", output_tokens=output, **{field: v}) for v in values])
                    rows, result = self.read_orders(root, [path])
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["line"], 1)
                self.assertIsNone(price_interval(rows[0], load_prices()))
                self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
                self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{path}:1", f"{path}:2"])
                self.assertEqual(result["issues"].get("conflicting_copies", 0), 0)
                self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 0)
                self.assertTrue(result["source_complete"])
                self.assertFalse(result["fully_priced"])
                self.assertEqual(result["agent_hours_10min_buckets"], 1 / 6)

    def test_modifier_mismatch_preserves_fullest_tokens_hours_and_other_records_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            write(a, [response("shared", speed="fast", output_tokens=10),
                      response("priced", "claude-sonnet-5-5", moment="2026-10-22T11:00:00Z", output_tokens=1000000)])
            write(z, [response("shared", speed="standard", output_tokens=1000000)])
            rows, result = self.read_orders(root, [a, z])
        shared = next(r for r in rows if r["model"] == "claude-opus-5-5")
        self.assertEqual(shared["path"], str(a))
        self.assertEqual(shared["tokens"]["output"], 1000000)
        self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
        self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{a}:1", f"{z}:1"])
        self.assertEqual(result["priced_records_only_usd"], [10, 10])
        self.assertEqual(result["groups"]["session claude-sonnet-5-5"]["usd_min"], 10)
        self.assertEqual(result["groups"]["session claude-opus-5-5"]["totals"]["output"], 1000000)
        self.assertTrue(result["source_complete"])
        self.assertEqual(result["agent_hours_10min_buckets"], 1 / 3)
        self.assertEqual(result["project_active_hours_10min_buckets"], 1 / 3)
        self.assertIsNone(result["usd_per_agent_hour"])
        self.assertIsNone(result["usd_per_project_active_hour"])

    def test_mismatch_locations_include_all_known_copies_and_sort_numeric_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            write(a, [{"type": "user"}] * 8 + [response("shared", speed="fast"),
                                                         response("shared", speed="standard")])
            write(z, [response("shared"), response("shared", speed="fast")])
            _, result = self.read_orders(root, [a, z])
        self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
        self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{a}:9", f"{a}:10", f"{z}:2"])

    def test_standard_modifier_aliases_from_active_snapshot_do_not_mismatch(self):
        prices = load_prices()
        prices["modifiers"]["speed"]["standard_values"].append("custom-standard")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            write(a, [response("shared", speed="standard", inference_geo="", output_tokens=1000000)])
            write(z, [response("shared", speed="custom-standard", inference_geo="global", output_tokens=1000000)])
            rows, result = self.read_orders(root, [a, z], snapshot=prices)
            price_path = root / "prices.json"
            price_path.write_text(json.dumps(prices))
            with patch("sys.argv", ["claude_ledger", "transcripts", str(root), "--prices", str(price_path), "--json"]), \
                    patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(main(), 0)
            cli_result = json.loads(stdout.getvalue())
        self.assertEqual(result, cli_result)
        self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
        self.assertEqual(price_interval(rows[0], prices), (20, 20))
        self.assertTrue(result["fully_priced"])

    def test_known_modifiers_survive_less_complete_copies_in_either_file(self):
        for known_in_a in (False, True):
            with self.subTest(known_in_a=known_in_a), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, z = root / "a.jsonl", root / "z.jsonl"
                known, full = (a, z) if known_in_a else (z, a)
                write(known, [response("shared", output_tokens=10, speed="fast", inference_geo="us")])
                write(full, [response("shared", output_tokens=1000000)])
                rows, result = self.read_orders(root, [a, z])
            self.assertEqual(rows[0]["path"], str(a))
            self.assertEqual(rows[0]["speed"], "fast")
            self.assertEqual(rows[0]["inference_geo"], "us")
            self.assertEqual(rows[0]["tokens"]["output"], 1000000)
            self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
            self.assertAlmostEqual(result["priced_records_only_usd"][0], 44)

    def test_known_modifier_and_mismatch_from_copy_outside_timestamp_tie(self):
        for earlier_speed in (None, "fast"):
            with self.subTest(earlier_speed=earlier_speed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, z = root / "a.jsonl", root / "z.jsonl"
                write(a, [response("s", output_tokens=1000000,
                                   **({} if earlier_speed is None else {"speed": earlier_speed}))])
                write(z, [response("s", moment="2026-10-22T12:05:00Z", output_tokens=10,
                                   speed="fast" if earlier_speed is None else "standard")])
                rows, result = self.read_orders(root, [a, z])
            self.assertEqual(rows[0]["path"], str(a))
            self.assertEqual(rows[0].get("speed"), "fast")
            if earlier_speed is None:
                self.assertEqual(price_interval(rows[0], load_prices()), (40, 40))
                self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
            else:
                self.assertIsNone(price_interval(rows[0], load_prices()))
                self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
                self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{a}:1", f"{z}:1"])

    def test_null_modifiers_keep_known_values_in_both_readers_and_round_scopes(self):
        for reader in (transcript_records, round_records):
            for matched in (False, True) if reader is round_records else (True,):
                for known_first in (False, True):
                    with self.subTest(reader=reader.__name__, matched=matched, known_first=known_first), \
                            tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        paths = [root / (f"{n}/streams/run.jsonl" if reader is round_records else f"{n}.jsonl")
                                 for n in ("a", "z")]
                        known = {"speed": "fast", "inference_geo": "us"}
                        unknown = dict.fromkeys(known)
                        for path, modifiers in zip(paths, (known, unknown) if known_first else (unknown, known)):
                            if reader is transcript_records:
                                event = response("s", output_tokens=1000000, **modifiers)
                            else:
                                event = {"type": "result", "uuid": "s", "usage": dict.fromkeys(COUNTERS, 0)
                                         | {"output_tokens": 1000000 if matched else 10} | modifiers,
                                         "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                                        | {"outputTokens": 1000000}}}
                            write(path, [event])
                        rows, result = self.read_orders(root, paths, reader)
                    values = rows[0] if matched else rows[0]["unattributed_modifiers"]
                    self.assertEqual({k: values.get(k) for k in known}, known)
                    self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
                    if matched:
                        self.assertAlmostEqual(price_interval(rows[0], load_prices())[0], 44)
                    else:
                        self.assertEqual(result["issues"]["records_unsupported_modifiers"], 1)

    def test_empty_modifiers_are_standard_under_any_snapshot_in_both_readers(self):
        prices = load_prices()
        for modifier in prices["modifiers"].values():
            modifier["standard_values"] = [v for v in modifier["standard_values"] if v != ""]
        for reader in (transcript_records, round_records):
            for matched in (False, True) if reader is round_records else (True,):
                with self.subTest(reader=reader.__name__, matched=matched), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    paths = [root / (f"{n}/streams/run.jsonl" if reader is round_records else f"{n}.jsonl")
                             for n in ("a", "z")]
                    for path, modifiers in zip(paths, ({"speed": "", "inference_geo": ""},
                                                       {"speed": "standard", "inference_geo": "global"})):
                        if reader is transcript_records:
                            event = response("s", output_tokens=1000000, **modifiers)
                        else:
                            event = {"type": "result", "uuid": "s", "usage": dict.fromkeys(COUNTERS, 0)
                                     | {"output_tokens": 1000000 if matched else 10} | modifiers,
                                     "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                                    | {"outputTokens": 1000000}}}
                        write(path, [event])
                    rows, result = self.read_orders(root, paths, reader, prices)
                self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
                self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 0)
                self.assertEqual(price_interval(rows[0], prices), (20, 20))

    def test_lone_null_modifiers_price_like_absent_including_unattributed_totals(self):
        prices = load_prices()
        row = record(output=1000000)
        absent = report([row.copy()], prices, defaultdict(int))
        row.update(speed=None, inference_geo=None, unattributed_modifiers={"speed": None, "inference_geo": None})
        self.assertEqual(price_interval(row, prices), (20, 20))
        self.assertEqual(report([row], prices, defaultdict(int)), absent)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "a.jsonl"
            write(path, [response("s", output_tokens=1000000, speed=None, inference_geo=None)])
            rows, result = self.read_orders(root, [path])
        self.assertTrue(result["fully_priced"])
        self.assertEqual(price_interval(rows[0], prices), (20, 20))

    def test_mismatch_can_also_count_as_unsupported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "a.jsonl"
            write(path, [response("s", speed=speed, output_tokens=1000000) for speed in ("turbo", "standard")])
            _, result = self.read_orders(root, [path])
        self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
        self.assertEqual(result["issues"]["records_unsupported_modifiers"], 1)

    def test_modifiers_merge_field_by_field_from_different_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / f"{name}.jsonl" for name in ("a", "b", "c")]
            for path, modifiers, output in zip(paths, ({"speed": "fast"}, {"inference_geo": "us"}, {}), (1, 2, 1000000)):
                write(path, [response("shared", output_tokens=output, **modifiers)])
            rows, result = self.read_orders(root, paths)
        self.assertEqual((rows[0]["speed"], rows[0]["inference_geo"]), ("fast", "us"))
        self.assertAlmostEqual(result["priced_records_only_usd"][0], 44)

    def test_round_unattributed_modifiers_merge_field_by_field_from_less_complete_copies(self):
        for speed, geo in (("fast", "us"), ("standard", "global")):
            with self.subTest(speed=speed, geo=geo), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [root / name / "streams/run.jsonl" for name in ("a", "b", "c")]
                for path, modifiers, output in zip(paths, ({"speed": speed}, {"inference_geo": geo}, {}), (10, 20, 1000000)):
                    write(path, [{"type": "result", "uuid": "shared", "usage": dict.fromkeys(COUNTERS, 0) | modifiers,
                                  "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                                 | {"outputTokens": output}}}])
                rows, result = self.read_orders(root, paths, round_records)
            self.assertEqual(rows[0]["unattributed_modifiers"], {"speed": speed, "inference_geo": geo})
            self.assertEqual(rows[0]["tokens"]["output"], 1000000)
            self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
            self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), int(speed == "fast"))
            self.assertEqual(result["fully_priced"], speed == "standard")

    def test_round_modifier_mismatches_cover_matched_and_unattributed_modifiers(self):
        for matched in (False, True):
            with self.subTest(matched=matched), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [root / name / "streams/run.jsonl" for name in ("a", "z")]
                for path, speed in zip(paths, ("standard", "fast")):
                    write(path, [{"type": "result", "uuid": "shared", "usage": dict.fromkeys(COUNTERS, 0)
                                  | {"output_tokens": 1000000 if matched else 10, "speed": speed},
                                  "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                                 | {"outputTokens": 1000000}}}])
                rows, result = self.read_orders(root, paths, round_records)
            self.assertEqual(len(rows), 1)
            self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
            self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{p}:1" for p in paths])
            self.assertEqual(result["issues"].get("conflicting_copies", 0), 0)
            self.assertTrue(result["source_complete"])
            self.assertFalse(result["fully_priced"])

    def test_round_mismatch_counts_records_and_lists_shared_locations_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name / "streams/run.jsonl" for name in ("a", "z")]
            for path, geo in zip(paths, ("global", "us")):
                write(path, [{"type": "result", "uuid": "shared", "usage": dict.fromkeys(COUNTERS, 0)
                              | {"output_tokens": 1, "inference_geo": geo},
                              "modelUsage": {model: dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 1000000}
                                             for model in ("claude-opus-5-5", "claude-sonnet-5-5")}}])
            rows, result = self.read_orders(root, paths, round_records)
        self.assertEqual(len(rows), 2)
        self.assertEqual(result["issues"]["records_modifier_mismatch"], 2)
        self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{p}:1" for p in paths])
        self.assertTrue(result["source_complete"])
        self.assertEqual(sum(g["unpriced_records"] for g in result["groups"].values()), 2)
        self.assertEqual(sum(g["totals"]["output"] for g in result["groups"].values()), 2000000)

    def test_fullest_matched_round_has_no_unattributed_modifiers_but_still_compares_copies(self):
        for smaller_speed in ("fast", "standard"):
            with self.subTest(smaller_speed=smaller_speed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [root / name / "streams/run.jsonl" for name in ("a", "z")]
                for path, output, speed in ((paths[0], 1000000, "fast"), (paths[1], 10, smaller_speed)):
                    write(path, [{"type": "result", "uuid": "s", "usage": dict.fromkeys(COUNTERS, 0)
                                  | {"output_tokens": 1000000, "speed": speed},
                                  "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                                 | {"outputTokens": output}}}])
                rows, result = self.read_orders(root, paths, round_records)
            self.assertTrue(rows[0]["totals_from_lead"])
            self.assertEqual(rows[0]["unattributed_modifiers"], {})
            self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 0)
            if smaller_speed == "fast":
                self.assertEqual(price_interval(rows[0], load_prices()), (40, 40))
                self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
            else:
                self.assertIsNone(price_interval(rows[0], load_prices()))
                self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
                self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{p}:1" for p in paths])

    def test_round_reader_uses_active_snapshot_for_standard_aliases(self):
        prices = load_prices()
        prices["modifiers"]["speed"]["standard_values"].append("custom-standard")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name / "streams/run.jsonl" for name in ("a", "z")]
            for path, speed in zip(paths, ("standard", "custom-standard")):
                write(path, [{"type": "result", "uuid": "s", "usage": dict.fromkeys(COUNTERS, 0)
                              | {"output_tokens": 1000000, "speed": speed},
                              "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                             | {"outputTokens": 1000000}}}])
            rows, result = self.read_orders(root, paths, round_records, prices)
            price_path = root / "prices.json"
            price_path.write_text(json.dumps(prices))
            with patch("sys.argv", ["claude_ledger", "rounds", str(root), "--prices", str(price_path), "--json"]), \
                    patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(main(), 0)
            self.assertEqual(result, json.loads(stdout.getvalue()))
        self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
        self.assertEqual(price_interval(rows[0], prices), (20, 20))

    def test_new_attribution_does_not_change_equal_fullness_round_token_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = [root / name / "streams/run.jsonl" for name in ("a", "z")]
            for path, lead_output, helper in ((a, 1000000, False), (z, 10, True)):
                models = {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 1000000}}
                if helper:
                    models["claude-haiku-5-5"] = dict.fromkeys(ROUND_COUNTERS, 0)
                write(path, [{"type": "result", "uuid": "s", "usage": dict.fromkeys(COUNTERS, 0)
                              | {"output_tokens": lead_output, "speed": "fast"}, "modelUsage": models}])
            rows, result = self.read_orders(root, [a, z], round_records)
        opus = next(r for r in rows if r["model"] == "claude-opus-5-5")
        self.assertEqual(opus["path"], str(a))
        self.assertFalse(opus["totals_from_lead"])
        self.assertEqual(opus["unattributed_modifiers"], {"speed": "fast"})
        self.assertEqual(result["issues"]["records_unsupported_modifiers"], 2)

    def test_modifier_mismatches_do_not_replace_model_or_non_cumulative_conflicts(self):
        for model, tokens in (("claude-sonnet-5-5", {"input_tokens": 10}),
                               ("claude-opus-5-5", {"output_tokens": 10})):
            with self.subTest(model=model, tokens=tokens), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "a.jsonl"
                write(path, [response("shared", input_tokens=10, speed="fast"),
                             response("shared", model, speed="standard", **tokens)])
                _, result = self.read_orders(root, [path])
            self.assertEqual(result["issues"]["conflicting_copies"], 2)
            self.assertFalse(result["source_complete"])
            self.assertIsNone(result["agent_hours_10min_buckets"])

    def test_round_model_and_unattributed_lead_modifiers_keep_their_separate_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name / "streams/run.jsonl" for name in ("a", "z")]
            event = {"type": "result", "uuid": "shared", "usage": dict.fromkeys(COUNTERS, 0) | {"speed": "fast"},
                     "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                    | {"outputTokens": 1000000, "speed": "standard"}}}
            for path in paths:
                write(path, [event])
            for selected in (paths[:1], paths):
                rows, result = self.read_orders(root, selected, round_records)
                self.assertEqual(rows[0]["speed"], "standard")
                self.assertEqual(rows[0]["unattributed_modifiers"], {"speed": "fast"})
                self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
                self.assertEqual(result["issues"]["records_unsupported_modifiers"], 1)
                self.assertTrue(result["source_complete"])
                self.assertFalse(result["fully_priced"])

    def test_known_modifier_in_smaller_matched_round_does_not_price_fuller_helper_totals(self):
        for fuller_speed in (None, "standard"):
            with self.subTest(fuller_speed=fuller_speed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                paths = [root / name / "streams/run.jsonl" for name in ("a", "z")]
                for path, output, speed in ((paths[0], 10, "fast"), (paths[1], 1000000, fuller_speed)):
                    usage = dict.fromkeys(COUNTERS, 0) | {"output_tokens": 10}
                    if speed is not None:
                        usage["speed"] = speed
                    write(path, [{"type": "result", "uuid": "shared", "usage": usage,
                                  "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                                 | {"outputTokens": output}}}])
                rows, result = self.read_orders(root, paths, round_records)
            self.assertEqual(rows[0]["speed"], "fast")
            self.assertEqual(rows[0]["tokens"]["output"], 1000000)
            self.assertFalse(result["fully_priced"])
            self.assertTrue(result["source_complete"])
            self.assertIsNone(price_interval(rows[0], load_prices()))
            if fuller_speed is None:
                self.assertEqual(rows[0]["unattributed_modifiers"], {"speed": "fast"})
                self.assertEqual(result["issues"]["records_unsupported_modifiers"], 1)
                self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
            else:
                self.assertEqual(result["issues"]["records_modifier_mismatch"], 1)
                self.assertEqual(result["issues"]["modifier_mismatch_locations"], [f"{p}:1" for p in paths])

    def test_modifier_mismatch_count_and_locations_follow_the_selected_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "a.jsonl"
            write(path, [response("shared", speed="fast"), response("shared", speed="standard"),
                         response("later", moment="2026-10-22T13:00:00Z", output_tokens=1000000)])
            issues = defaultdict(int)
            rows = transcript_records(root, issues)
            result = report(rows, load_prices(), issues, start=timestamp("2026-10-22T13:00:00Z"))
        self.assertEqual(result["issues"].get("records_modifier_mismatch", 0), 0)
        self.assertNotIn("modifier_mismatch_locations", result["issues"])
        self.assertTrue(result["fully_priced"])
        self.assertTrue(result["source_complete"])

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

    def test_conflicting_non_cumulative_usage_keeps_attributed_copy_and_suppresses_hours(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("m1", input_tokens=10), response("m1", input_tokens=20, output_tokens=20),
                         response("m1", output_tokens=10)])
            issues = defaultdict(int)
            rows = transcript_records(Path(directory), issues)
            result = report(rows, load_prices(), issues,
                            outcomes={"accepted": 1, "unit": "change", "source": "test"})
        self.assertEqual(rows[0]["tokens"]["input"], 10)
        self.assertEqual(rows[0]["tokens"]["output"], 0)
        self.assertEqual(issues["conflicting_copies"], 2)
        self.assertEqual(issues["conflicting_copy_locations"], [f"{path}:1", f"{path}:3"])
        self.assertEqual(result["responses"], 1)
        self.assertFalse(result["source_complete"])
        for key in ("agent_hours_10min_buckets", "project_active_hours_10min_buckets", "usd_per_agent_hour",
                    "usd_per_project_active_hour", "usd_per_accepted_outcome"):
            self.assertIsNone(result[key], key)

    def test_conflicting_models_keep_earliest_copy_and_list_both_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("m1", moment="2026-10-22T12:10:00Z"),
                         response("m1", "claude-sonnet-5-5", input_tokens=100)])
            issues = defaultdict(int)
            rows = transcript_records(Path(directory), issues)
        self.assertEqual(rows[0]["model"], "claude-sonnet-5-5")
        self.assertEqual(rows[0]["tokens"]["input"], 100)
        self.assertEqual(issues["conflicting_copies"], 2)
        self.assertEqual(issues["conflicting_copy_locations"], [f"{path}:1", f"{path}:2"])

    def test_earliest_timestamp_owns_cumulative_tokens_from_a_later_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "a.jsonl", [response("own-a", moment="2026-10-22T10:00:00Z"),
                                      response("shared", moment="2026-10-22T12:10:00Z", output_tokens=100)])
            write(root / "z.jsonl", [response("shared", output_tokens=10)])
            issues = defaultdict(int)
            rows = transcript_records(root, issues)
        shared = next(r for r in rows if r["tokens"]["output"])
        self.assertEqual(shared["agent"], str(root / "z.jsonl"))
        self.assertEqual(shared["timestamp"], timestamp("2026-10-22T12:00:00Z"))
        self.assertEqual(shared["tokens"]["output"], 100)
        self.assertEqual(issues["conflicting_copies"], 0)

    def test_decreasing_cumulative_copies_are_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("shared", output_tokens=100), response("shared", output_tokens=10),
                         response("shared")])
            issues = defaultdict(int)
            rows = transcript_records(Path(directory), issues)
        self.assertEqual(rows[0]["tokens"]["output"], 100)
        self.assertEqual(issues["conflicting_copies"], 0)

    def test_fullest_cumulative_copy_includes_input_when_output_ties(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("shared", input_tokens=10, output_tokens=100),
                         response("shared", input_tokens=20, output_tokens=100)])
            issues = defaultdict(int)
            rows = transcript_records(Path(directory), issues)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tokens"]["input"], 20)
        self.assertEqual(rows[0]["tokens"]["output"], 100)
        self.assertEqual(rows[0]["line"], 1)
        self.assertEqual(issues["conflicting_copies"], 0)

    def test_dated_copy_precedes_undated_copy_without_inventing_own_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "a.jsonl", [response("shared", moment=None, output_tokens=100),
                                      response("undated-own", moment=None)])
            write(root / "z.jsonl", [response("shared", output_tokens=10)])
            rows = transcript_records(root, defaultdict(int))
        shared = next(r for r in rows if r["tokens"]["output"])
        self.assertEqual(shared["agent"], str(root / "z.jsonl"))
        self.assertEqual(shared["timestamp"], timestamp("2026-10-22T12:00:00Z"))
        self.assertEqual(shared["tokens"]["output"], 100)

    def test_timestamp_ties_use_own_activity_and_preserve_role_in_reverse_read_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "subagents/z.jsonl"
            shared = response("shared", output_tokens=100)
            write(a, [shared, response("own-a", moment="2026-10-22T12:30:00Z")])
            write(z, [shared, response("own-z", moment="2026-10-22T11:00:00Z"),
                      response("later-z", moment="2026-10-22T13:00:00Z")])
            z.with_suffix(".meta.json").write_text('{"agentType": "implementer"}')

            def measure(paths):
                issues = defaultdict(int)
                with patch.object(Path, "rglob", return_value=iter(paths)):
                    rows = transcript_records(root, issues)
                return rows, report(rows, load_prices(), issues)

            rows, result = measure([a, z])
            self.assertEqual(measure([z, a]), (rows, result))
        owner = next(r for r in rows if r["tokens"]["output"])
        self.assertEqual(owner["agent"], str(z))
        self.assertEqual(owner["role"], "implementer")
        self.assertEqual(result["groups"]["implementer claude-opus-5-5"]["responses"], 3)

    def test_file_without_own_activity_loses_tie_even_with_earlier_copied_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = response("old", moment="2026-10-22T08:00:00Z")
            shared = response("shared", output_tokens=10)
            write(root / "a.jsonl", [old, shared, shared])
            write(root / "z.jsonl", [old, shared, response("own", moment="2026-10-22T11:00:00Z")])
            rows = transcript_records(root, defaultdict(int))
        self.assertTrue(all(r["agent"] == str(root / "z.jsonl") for r in rows))

    def test_own_activity_repeated_inside_one_file_still_breaks_timestamp_tie(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            own = response("own-a", moment="2026-10-22T11:00:00Z")
            shared = response("shared", output_tokens=10)
            write(a, [own, own, shared])
            write(z, [shared, response("own-z", moment="2026-10-22T11:30:00Z")])
            for paths in ([a, z], [z, a]):
                with self.subTest(paths=paths), patch.object(Path, "rglob", return_value=iter(paths)):
                    rows = transcript_records(root, defaultdict(int))
                owner = next(r for r in rows if r["tokens"]["output"])
                self.assertEqual(owner["agent"], str(a))

    def test_undated_own_activity_is_ignored_and_none_falls_back_to_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, y, z = (root / f"{name}.jsonl" for name in ("a", "y", "z"))
            shared = response("shared", output_tokens=10)
            write(a, [shared])
            write(y, [shared, response("own-y", moment=None)])
            for dated in (True, False):
                # Earlier own activity keeps this from being a copied extension of a.
                write(z, [shared] + ([response("own-z", moment="2026-10-22T11:00:00Z")] if dated else []))
                for paths in ([a, y, z], [z, y, a]):
                    with self.subTest(dated=dated, paths=paths), patch.object(Path, "rglob", return_value=iter(paths)):
                        rows = transcript_records(root, defaultdict(int))
                    owner = next(r for r in rows if r["tokens"]["output"])
                    self.assertEqual(owner["agent"], str(z if dated else a))

    def test_usageless_assistant_with_bad_or_missing_timestamp_gives_no_own_activity(self):
        for value in ("missing", None, 12345, False, [], {}, "", "bad", "2026-10-22T12:00:00"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shared = response("shared", output_tokens=100)
                no_usage = {"type": "assistant", "message": {"id": "own-z", "model": "m"}}
                if value != "missing":
                    no_usage["timestamp"] = value
                write(root / "a.jsonl", [shared])
                write(root / "z.jsonl", [no_usage, shared])
                issues = defaultdict(int)
                rows = transcript_records(root, issues)
                result = report(rows, load_prices(), issues)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["agent"], str(root / "a.jsonl"))
            self.assertEqual(result["responses"], 1)
            self.assertTrue(result["source_complete"])
            self.assertTrue(result["fully_priced"])
            self.assertEqual(result["agent_hours_10min_buckets"], 1 / 6)

    def test_usage_records_keep_strict_timestamp_handling(self):
        for value, error in (("bad", ValueError), ("2026-10-22T12:00:00", ValueError), (12345, AttributeError)):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                write(Path(directory) / "a.jsonl", [response("usage", moment=value)])
                with self.assertRaises(error):
                    transcript_records(Path(directory), defaultdict(int))

    def test_copy_outside_dispute_does_not_remove_own_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = response("shared", output_tokens=10)
            write(root / "a.jsonl", [shared, response("own-a", moment="2026-10-22T11:00:00Z")])
            write(root / "b.jsonl", [shared, response("own-b", moment="2026-10-22T11:30:00Z")])
            write(root / "z.jsonl", [{"type": "assistant", "timestamp": 12345,
                                     "message": {"id": "own-a", "model": "m"}}])
            rows = transcript_records(root, defaultdict(int))
        owner = next(r for r in rows if r["tokens"]["output"])
        self.assertEqual(owner["agent"], str(root / "a.jsonl"))
        self.assertEqual(len(rows), 3)

    def test_dated_usageless_activity_is_own_even_when_copied_outside_dispute(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            no_usage = response("no-usage", moment="2026-10-22T10:00:00Z")
            del no_usage["message"]["usage"]
            write(root / "a.jsonl", [response("shared", output_tokens=10),
                                      response("own-a", moment="2026-10-22T11:00:00Z")])
            write(root / "z.jsonl", [no_usage, response("shared", output_tokens=10)])
            rows = transcript_records(root, defaultdict(int))
            shared = next(r for r in rows if r["tokens"]["output"])
            self.assertEqual(shared["agent"], str(root / "z.jsonl"))
            # A file outside the dispute does not remove this ID from z's own activity.
            write(root / "b.jsonl", [no_usage])
            rows = transcript_records(root, defaultdict(int))
            shared = next(r for r in rows if r["tokens"]["output"])
            self.assertEqual(shared["agent"], str(root / "z.jsonl"))

    def test_last_resort_is_smallest_path_then_group(self):
        for own_activity in (False, True):
            with self.subTest(own_activity=own_activity), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ("a", "z"):
                    rows = [response("shared", output_tokens=10)]
                    if own_activity:
                        rows.append(response(name, moment="2026-10-22T11:00:00Z"))
                    write(root / f"{name}.jsonl", rows)
                with patch.object(Path, "rglob", return_value=iter([root / "z.jsonl", root / "a.jsonl"])):
                    rows = transcript_records(root, defaultdict(int))
                owner = next(r for r in rows if r["tokens"]["output"])
                self.assertEqual(owner["agent"], str(root / "a.jsonl"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("shared", "claude-sonnet-5-5"), response("shared")])
            rows = transcript_records(Path(directory), defaultdict(int))
        self.assertEqual(rows[0]["model"], "claude-opus-5-5")

    def test_conflict_result_is_independent_of_file_read_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / f"{name}.jsonl" for name in ("a", "b", "c")]
            for path, usage in zip(paths, ({"input_tokens": 10}, {"output_tokens": 10},
                                          {"input_tokens": 20, "output_tokens": 20})):
                write(path, [response("shared", **usage)])
            results = []
            for order in (paths, paths[::-1]):
                issues = defaultdict(int)
                with patch.object(Path, "rglob", return_value=iter(order)):
                    results.append(report(transcript_records(root, issues), load_prices(), issues))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]["issues"]["conflicting_copies"], 2)

    def test_read_prices_differ_by_exact_model(self):
        prices = load_prices()
        self.assertEqual(price_interval(record(read=1000000), prices), (0.2, 0.2))
        self.assertEqual(price_interval(record("claude-sonnet-5-5", read=1000000), prices), (0.1, 0.1))
        self.assertIsNone(price_interval(record("glm-5.3", read=1000000), prices))

    def test_missing_counters_are_unpriced_but_keep_hours_even_when_all_known_tokens_are_zero(self):
        for counter in COUNTERS:
            for output in (0, 100):
                with self.subTest(counter=counter, output=output), tempfile.TemporaryDirectory() as directory:
                    event = response("missing", output_tokens=output)
                    del event["message"]["usage"][counter]
                    write(Path(directory) / "a.jsonl", [event])
                    issues = defaultdict(int)
                    result = report(transcript_records(Path(directory), issues), load_prices(), issues,
                                    outcomes={"accepted": 1, "unit": "change", "source": "test"})
                self.assertEqual(result["responses"], 1)
                self.assertEqual(result["issues"].get("records_missing_counters", 0), 1)
                self.assertEqual(result["groups"]["session claude-opus-5-5"]["unpriced_records"], 1)
                self.assertFalse(result["fully_priced"])
                self.assertTrue(result["source_complete"])
                self.assertEqual(result["priced_records_only_usd"], [0, 0])
                self.assertEqual(result["agent_hours_10min_buckets"], 1 / 6)
                self.assertEqual(result["project_active_hours_10min_buckets"], 1 / 6)
                for key in ("usd_per_agent_hour", "usd_per_project_active_hour", "usd_per_accepted_outcome"):
                    self.assertIsNone(result[key], key)

    def test_nested_missing_counters_and_explicit_null_are_unknown(self):
        for usage in ({"iterations": [dict.fromkeys(COUNTERS, 0), {"output_tokens": 10}]},
                      dict.fromkeys(COUNTERS, 0) | {"input_tokens": None}):
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as directory:
                event = response("nested")
                event["message"]["usage"] = usage
                write(Path(directory) / "a.jsonl", [event])
                issues = defaultdict(int)
                rows = transcript_records(Path(directory), issues)
                result = report(rows, load_prices(), issues)
            self.assertEqual(result["issues"].get("records_missing_counters", 0), 1)
            self.assertFalse(result["fully_priced"])

    def test_complete_cumulative_copy_can_supply_missing_counters_without_moving_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incomplete = response("shared")
            incomplete["message"]["usage"] = {"output_tokens": 100}
            write(root / "a.jsonl", [incomplete])
            write(root / "z.jsonl", [response("shared", output_tokens=100)])
            issues = defaultdict(int)
            rows = transcript_records(root, issues)
            result = report(rows, load_prices(), issues)
        self.assertEqual(rows[0]["agent"], str(root / "a.jsonl"))
        self.assertEqual(result["issues"].get("records_missing_counters", 0), 0)
        self.assertTrue(result["fully_priced"])

    def test_fast_and_us_modifiers_stack_on_every_token_category(self):
        prices = load_prices()
        for kind in KINDS:
            for speed, geo, factor in (("fast", None, 2), (None, "us", 1.1), ("fast", "us", 2.2)):
                with self.subTest(kind=kind, speed=speed, geo=geo):
                    row = record(**{kind: 1000000})
                    base = price_interval(row, prices)
                    row.update({k: v for k, v in (("speed", speed), ("inference_geo", geo)) if v is not None})
                    actual = price_interval(row, prices)
                    for value, standard in zip(actual, base):
                        self.assertAlmostEqual(value, standard * factor)

    def test_modifier_defaults_and_model_eligibility_come_from_snapshot(self):
        prices = load_prices()
        self.assertEqual(prices["modifiers"]["speed"]["models"],
                         ["claude-opus-5-5", "claude-opus-5", "claude-opus-4-8"])
        self.assertEqual(prices["modifiers"]["inference_geo"]["models"],
                         ["claude-opus-5-5", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-6",
                          "claude-opus-4-7", "claude-sonnet-5-5", "claude-sonnet-5", "claude-sonnet-4-6",
                          "claude-haiku-5-5", "claude-fable-5", "claude-fable-5-1"])
        for speed in (None, "standard"):
            for geo in (None, "", "global"):
                row = record(input=1000000)
                row.update({k: v for k, v in (("speed", speed), ("inference_geo", geo)) if v is not None})
                self.assertEqual(price_interval(row, prices), (4, 4))
        for field, modifier in prices["modifiers"].items():
            for model in modifier["models"]:
                with self.subTest(field=field, model=model):
                    if model not in prices["models"]:
                        unknown = record(model, output=100)
                        unknown[field] = modifier["value"]
                        result = report([unknown], prices, defaultdict(int))
                        self.assertFalse(result["fully_priced"])
                        self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 0)
                    # Eligibility can be tested without inventing published base rates for these models.
                    prices["models"][model] = prices["models"]["claude-opus-5-5"]
                    row = record(model, input=1000000)
                    row[field] = modifier["value"]
                    expected = 4 * modifier["multiplier"]
                    self.assertEqual(price_interval(row, prices), (expected, expected))
        row = record(input=1000000)
        row["speed"] = "fast"
        prices["modifiers"]["speed"]["multiplier"] = 3
        self.assertEqual(price_interval(row, prices), (12, 12))
        prices["modifiers"]["speed"]["models"] = []
        self.assertIsNone(price_interval(row, prices))

    def test_unsupported_modifiers_are_counted_unpriced_and_keep_hours(self):
        cases = [("claude-opus-5-5", "speed", v) for v in ("turbo", False, 1, [], {})]
        cases += [("claude-opus-5-5", "inference_geo", v) for v in ("eu", "US", False, 1, [], {})]
        cases += [("claude-sonnet-5-5", "speed", "fast"), ("claude-haiku-4-5-20251001", "inference_geo", "us"),
                  ("glm-5.3", "speed", "fast")]
        for model, field, value in cases:
            for output in (0, 100):
                with self.subTest(model=model, field=field, value=value, output=output):
                    with tempfile.TemporaryDirectory() as directory:
                        write(Path(directory) / "a.jsonl", [response("modifier", model, output_tokens=output,
                                                                    **{field: value})])
                        issues = defaultdict(int)
                        result = report(transcript_records(Path(directory), issues), load_prices(), issues,
                                        outcomes={"accepted": 1, "unit": "change", "source": "test"})
                    self.assertEqual(result["responses"], 1)
                    self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 1)
                    self.assertFalse(result["fully_priced"])
                    self.assertTrue(result["source_complete"])
                    self.assertEqual(result["agent_hours_10min_buckets"], 1 / 6)
                    self.assertEqual(result["project_active_hours_10min_buckets"], 1 / 6)
                    for key in ("usd_per_agent_hour", "usd_per_project_active_hour", "usd_per_accepted_outcome"):
                        self.assertIsNone(result[key], key)

    def test_transcript_modifiers_survive_cumulative_copy_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "a.jsonl", [response("shared")])
            write(root / "z.jsonl", [response("shared", output_tokens=1000000, speed="fast", inference_geo="us")])
            issues = defaultdict(int)
            result = report(transcript_records(root, issues), load_prices(), issues)
        self.assertAlmostEqual(result["priced_records_only_usd"][0], 44)
        self.assertTrue(result["fully_priced"])

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

    def test_invalid_lines_are_counted_and_located_in_both_readers(self):
        for reader in (transcript_records, round_records):
            with self.subTest(reader=reader.__name__), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "streams/a.jsonl"
                write(path, [])
                path.write_text('{broken\n\0still broken\n')
                issues = defaultdict(int)
                reader(Path(directory), issues)
                self.assertEqual(issues["invalid_json_lines"], 2)
                self.assertEqual(issues["invalid_json_locations"], [f"{path}:1", f"{path}:2"])
                self.assertEqual(issues["recovered_nul_padded_lines"], 0)

    def test_non_object_json_is_invalid_located_and_suppresses_in_both_readers(self):
        for reader in (transcript_records, round_records):
            for value in ([], None, 1, "text", True):
                with self.subTest(reader=reader.__name__, value=value), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "streams/a.jsonl"
                    valid = (response("paid", output_tokens=100) if reader == transcript_records else
                             {"type": "result", "modelUsage": {"claude-opus-5-5":
                              dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 100}}})
                    write(path, [valid, value])
                    issues = defaultdict(int)
                    result = report(reader(Path(directory), issues), load_prices(), issues,
                                    outcomes={"accepted": 1, "unit": "change", "source": "test"})
                self.assertEqual(issues["invalid_json_lines"], 1)
                self.assertEqual(issues["invalid_json_locations"], [f"{path}:2"])
                self.assertEqual(issues["recovered_nul_padded_lines"], 0)
                self.assertEqual(result["responses"], 1)
                self.assertFalse(result["source_complete"])
                for key in ("agent_hours_10min_buckets", "project_active_hours_10min_buckets", "usd_per_agent_hour",
                            "usd_per_project_active_hour", "usd_per_accepted_outcome"):
                    self.assertIsNone(result[key], key)

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

    def test_invalid_json_locations_sort_by_path_then_numeric_line_in_both_readers(self):
        for reader in (transcript_records, round_records):
            with self.subTest(reader=reader.__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, z = root / "a/streams/a.jsonl", root / "z/streams/z.jsonl"
                for path in (a, z):
                    write(path, [{"type": "user"}] * 8 + [None, None])
                issues = defaultdict(int)
                with patch.object(Path, "rglob", return_value=iter([z, a])):
                    reader(root, issues)
                self.assertEqual(issues["invalid_json_locations"],
                                 [f"{a}:9", f"{a}:10", f"{z}:9", f"{z}:10"])

    def test_conflicting_copy_locations_sort_by_path_then_numeric_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a.jsonl", root / "z.jsonl"
            for path, identifier in ((a, "a"), (z, "z")):
                write(path, [{"type": "user"}] * 8 + [response(identifier, input_tokens=10),
                                                        response(identifier, output_tokens=10)])
            issues = defaultdict(int)
            with patch.object(Path, "rglob", return_value=iter([z, a])):
                transcript_records(root, issues)
        self.assertEqual(issues["conflicting_copy_locations"],
                         [f"{a}:9", f"{a}:10", f"{z}:9", f"{z}:10"])
        self.assertEqual(issues["conflicting_copies"], 4)

    def test_nul_padded_non_usage_line_is_recovered_without_suppressing_normalizers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a.jsonl"
            write(path, [response("paid", output_tokens=1000000)])
            with path.open("a") as stream:
                stream.write('\0' * 20 + json.dumps({"type": "user"}) + '\n')
            issues = defaultdict(int)
            result = report(transcript_records(Path(directory), issues), load_prices(), issues,
                            outcomes={"accepted": 1, "unit": "change", "source": "test"})
        self.assertEqual(result["issues"]["invalid_json_lines"], 1)
        self.assertEqual(result["issues"]["invalid_json_locations"], [f"{path}:2"])
        self.assertEqual(result["issues"]["recovered_nul_padded_lines"], 1)
        self.assertTrue(result["source_complete"])
        self.assertEqual(result["agent_hours_10min_buckets"], 1 / 6)
        self.assertEqual(result["project_active_hours_10min_buckets"], 1 / 6)
        self.assertEqual(result["usd_per_agent_hour"], [120.0, 120.0])
        self.assertEqual(result["usd_per_project_active_hour"], [120.0, 120.0])
        self.assertEqual(result["usd_per_accepted_outcome"], [20.0, 20.0])

    def test_nul_padded_usage_and_mixed_invalid_lines_still_suppress(self):
        for event in (response("lost", output_tokens=100), {"usage": {}}, {"modelUsage": {}}, ["user"]):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "a.jsonl"
                write(path, [response("paid", output_tokens=100)])
                with path.open("a") as stream:
                    stream.write('\0' + json.dumps({"type": "user"}) + '\n')
                    stream.write('\0' + json.dumps(event) + '\n')
                issues = defaultdict(int)
                result = report(transcript_records(Path(directory), issues), load_prices(), issues)
                self.assertEqual(issues["invalid_json_lines"], 2)
                self.assertEqual(issues["recovered_nul_padded_lines"], 1)
                self.assertFalse(result["source_complete"])
                self.assertIsNone(result["usd_per_agent_hour"])

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

    def test_round_counter_completeness_follows_selected_totals_without_changing_ttl_rule(self):
        for counter in ROUND_COUNTERS:
            with self.subTest(counter=counter):
                values = dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 100}
                del values[counter]
                row = result_records({"modelUsage": {"claude-opus-5-5": values}})[0]
                self.assertTrue(row["missing_counters"])
                self.assertIsNone(price_interval(row, load_prices()))
                result = report([row], load_prices(), defaultdict(int))
                self.assertEqual(result["issues"].get("records_missing_counters", 0), 1)
        usage = dict.fromkeys(COUNTERS, 0) | {"cache_creation_input_tokens": 10,
                                             "cache_creation": {"ephemeral_1h_input_tokens": 10}}
        values = dict.fromkeys(ROUND_COUNTERS, 0) | {"cacheCreationInputTokens": 10}
        event = {"usage": usage, "modelUsage": {"claude-opus-5-5": values}}
        row = result_records(event)[0]
        self.assertEqual(row["tokens"]["write_1h"], 10)
        self.assertEqual(price_interval(row, load_prices()), (0.00008, 0.00008))
        del usage["input_tokens"]
        self.assertIsNone(price_interval(result_records(event)[0], load_prices()))
        values["outputTokens"] = 100
        row = result_records(event)[0]
        self.assertFalse(row["missing_counters"])
        self.assertEqual(row["tokens"]["write_unknown"], 10)
        self.assertEqual(row["tokens"]["write_1h"], 0)
        self.assertEqual(row["tokens"]["output"], 100)
        self.assertIsNotNone(price_interval(row, load_prices()))

    def test_matched_round_checks_missing_model_counters_even_when_lead_is_complete(self):
        for counter in ROUND_COUNTERS:
            with self.subTest(counter=counter):
                usage = dict.fromkeys(COUNTERS, 0)
                values = dict.fromkeys(ROUND_COUNTERS, 0)
                del values[counter]
                rows = result_records({"usage": usage, "modelUsage": {"claude-opus-5-5": values}})
                result = report(rows, load_prices(), defaultdict(int))
                self.assertEqual(result["responses"], 1)
                self.assertFalse(result["fully_priced"])
                self.assertEqual(result["issues"].get("records_missing_counters", 0), 1)
                self.assertIsNone(price_interval(rows[0], load_prices()))

    def test_round_modifiers_price_matched_lead_totals(self):
        usage = dict.fromkeys(COUNTERS, 0) | {"output_tokens": 1000000,
                                             "speed": "fast", "inference_geo": "us"}
        values = dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 1000000}
        rows = result_records({"usage": usage, "modelUsage": {"claude-opus-5-5": values}})
        self.assertEqual(rows[0]["tokens"]["output"], 1000000)
        self.assertAlmostEqual(price_interval(rows[0], load_prices())[0], 44)
        result = report(rows, load_prices(), defaultdict(int))
        self.assertTrue(result["fully_priced"])
        self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 0)

    def test_nonstandard_lead_modifiers_leave_every_model_total_unpriced(self):
        for modifiers in ({"speed": "fast"}, {"inference_geo": "us"},
                          {"speed": "fast", "inference_geo": "us"},
                          {"speed": "turbo"}):
            for lead_output, model_output, helper_output in ((1000000, 2000000, None),
                                                            (10, 1000000, None),
                                                            (1000000, 1000000, 0),
                                                            (1000000, 1000000, 500)):
                with self.subTest(modifiers=modifiers, lead=lead_output, model=model_output, helper=helper_output):
                    usage = dict.fromkeys(COUNTERS, 0) | {"output_tokens": lead_output} | modifiers
                    models = {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": model_output}}
                    if helper_output is not None:
                        models["claude-haiku-5-5"] = dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": helper_output}
                    rows = result_records({"usage": usage, "modelUsage": models})
                    result = report(rows, load_prices(), defaultdict(int))
                    self.assertEqual([row["tokens"]["output"] for row in rows],
                                     [model_output] + ([] if helper_output is None else [helper_output]))
                    self.assertEqual(result["responses"], len(models))
                    self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), len(models))
                    self.assertFalse(result["fully_priced"])
                    self.assertTrue(result["source_complete"])
                    self.assertEqual(result["priced_records_only_usd"], [0, 0])
                    self.assertTrue(all(price_interval(row, load_prices()) is None for row in rows))

    def test_standard_lead_modifiers_do_not_change_model_total_prices(self):
        for modifiers in ({}, {"speed": "standard", "inference_geo": "global"},
                          {"speed": "", "inference_geo": ""}, {"speed": None, "inference_geo": None}):
            for helper in (False, True):
                with self.subTest(modifiers=modifiers, helper=helper):
                    models = {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 1000000}}
                    if helper:
                        models["claude-sonnet-5-5"] = dict.fromkeys(ROUND_COUNTERS, 0) | {"outputTokens": 1000000}
                    usage = dict.fromkeys(COUNTERS, 0) | {"output_tokens": 10} | modifiers
                    rows = result_records({"usage": usage, "modelUsage": models})
                    result = report(rows, load_prices(), defaultdict(int))
                    self.assertTrue(result["fully_priced"])
                    self.assertEqual(result["issues"].get("records_unsupported_modifiers", 0), 0)
                    self.assertEqual(result["priced_records_only_usd"], [30, 30] if helper else [20, 20])

    def test_unattributed_lead_modifier_defaults_come_from_snapshot(self):
        prices = load_prices()
        prices["modifiers"]["speed"]["standard_values"].append("custom-standard")
        rows = result_records({"usage": dict.fromkeys(COUNTERS, 0) | {"speed": "custom-standard"},
                               "modelUsage": {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0)
                                              | {"outputTokens": 1000000}}})
        self.assertEqual(price_interval(rows[0], prices), (20, 20))

    def test_round_conflicts_are_located_and_do_not_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, z = root / "a/streams/a.jsonl", root / "z/streams/z.jsonl"
            for path, usage in ((a, {"inputTokens": 10}), (z, {"outputTokens": 10})):
                write(path, [{"type": "result", "uuid": "shared", "modelUsage":
                              {"claude-opus-5-5": dict.fromkeys(ROUND_COUNTERS, 0) | usage}}])
            results = []
            for paths in ([a, z], [z, a]):
                issues = defaultdict(int)
                with patch.object(Path, "rglob", return_value=iter(paths)):
                    rows = round_records(root, issues)
                    results.append(report(rows, load_prices(), issues))
                self.assertEqual(rows[0]["tokens"]["input"], 10)
                self.assertEqual(rows[0]["tokens"]["output"], 0)
                self.assertEqual(issues["conflicting_copies"], 2)
                self.assertEqual(issues["conflicting_copy_locations"], [f"{a}:1", f"{z}:1"])
                self.assertFalse(results[-1]["source_complete"])
            self.assertEqual(results[0], results[1])

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

    def test_missing_counter_issues_count_only_records_inside_window(self):
        with tempfile.TemporaryDirectory() as directory:
            moments = ("2026-10-22T11:59:59Z", "2026-10-22T12:00:00Z", "2026-10-22T12:10:00Z",
                       "2026-10-22T12:20:00Z", "2026-10-22T12:20:01Z", None)
            events = [response(str(index), moment=moment, output_tokens=100) for index, moment in enumerate(moments)]
            for event in events:
                del event["message"]["usage"]["input_tokens"]
            write(Path(directory) / "a.jsonl", events)
            issues = defaultdict(int)
            result = report(transcript_records(Path(directory), issues), load_prices(), issues,
                            timestamp("2026-10-22T12:00:00Z"), timestamp("2026-10-22T12:20:00Z"))
        self.assertEqual(result["responses"], 2)
        self.assertEqual(result["issues"].get("records_missing_counters", 0), 2)
        self.assertEqual(result["issues"]["undated_records_excluded"], 1)
        self.assertEqual(result["groups"]["session claude-opus-5-5"]["unpriced_records"], 2)

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

    def test_dated_round_totals_do_not_invent_hours(self):
        rows = result_records({"timestamp": "2026-10-22T12:00:00Z", "modelUsage":
                               {"claude-opus-5-5": {"outputTokens": 1000}}})
        result = report(rows, load_prices(), defaultdict(int))
        self.assertIsNone(result["agent_hours_10min_buckets"])
        self.assertIsNone(result["usd_per_agent_hour"])
        self.assertIsNone(result["project_active_hours_10min_buckets"])
        self.assertIsNone(result["usd_per_project_active_hour"])

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

    def test_invalid_modifier_snapshot_fails(self):
        for field in ("speed", "inference_geo"):
            for key, value in (("multiplier", -1), ("multiplier", 0), ("multiplier", True),
                               ("multiplier", float("inf")), ("multiplier", float("nan")),
                               ("multiplier", "2"), ("models", []), ("models", "model"), ("models", [None]),
                               ("models", [""]), ("source", ""), ("as_of", ""),
                               ("standard_values", None), ("standard_values", [None]), ("value", None),
                               ("value", ""), ("value", "standard" if field == "speed" else "global")):
                with self.subTest(field=field, key=key, value=value), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "prices.json"
                    prices = load_prices()
                    prices["modifiers"][field][key] = value
                    path.write_text(json.dumps(prices))
                    with self.assertRaises(ValueError):
                        load_prices(path)

    def test_prices_without_modifiers_name_missing_key_and_file_in_cli_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replacement-prices.json"
            prices = load_prices()
            del prices["modifiers"]
            path.write_text(json.dumps(prices))
            with patch("sys.argv", ["claude_ledger", "transcripts", directory, "--prices", str(path)]), \
                    patch("sys.stderr", new_callable=io.StringIO) as stderr:
                with self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(error.exception.code, 2)
            self.assertIn("missing required key: modifiers", stderr.getvalue())
            self.assertIn(str(path), stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
