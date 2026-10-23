"""Check that the ledger counts each response once and weights each kind of token."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.claude_ledger import KINDS, load_prices, price_interval, rounds, shares, transcripts


def response(identifier, model, **usage):
    return {"type": "assistant", "message": {"id": identifier, "model": model, "usage": usage}}


def record(model="claude-opus-5-5", aggregate=False, **tokens):
    return {"model": model, "role": "session", "aggregate": aggregate,
            "tokens": {k: tokens.get(k, 0) for k in KINDS}, "recorded_cli_usd": None}


class LedgerTests(unittest.TestCase):
    def test_sessions_and_subagents_count_each_response_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "session" / "subagents").mkdir(parents=True)
            first = response("m1", "claude-opus-5-5", cache_read_input_tokens=1000, output_tokens=10,
                             cache_creation={"ephemeral_1h_input_tokens": 100})
            lines = [first, first, response("m2", "claude-opus-5-5", cache_read_input_tokens=1000),
                     {"type": "user", "message": {"content": "hi"}}]
            (root / "session.jsonl").write_text("\n".join(json.dumps(e) for e in lines) + "\nnot json\n")
            helper = response("s1", "claude-sonnet-5-5", cache_creation_input_tokens=400, output_tokens=20)
            (root / "session" / "subagents" / "agent-1.jsonl").write_text(json.dumps(helper) + "\n")
            groups = transcripts(root)
        session = groups["session claude-opus-5-5"]
        self.assertEqual(session["responses"], 2)
        self.assertEqual(session["totals"]["read"], 2000)
        self.assertEqual(session["totals"]["write_1h"], 100)
        total, part = shares(session["totals"])
        self.assertAlmostEqual(total, 2000 * 0.1 + 100 * 2 + 10 * 5)
        self.assertAlmostEqual(part["read"], 200 / 450)
        self.assertEqual(groups["subagent claude-sonnet-5-5"]["totals"]["write_5m"], 400)

    def test_rounds_use_each_stream_last_cumulative_result(self):
        with tempfile.TemporaryDirectory() as directory:
            streams = Path(directory) / "round1" / "streams"
            streams.mkdir(parents=True)
            early = {"type": "result", "modelUsage": {"glm-5.3": {"outputTokens": 1}}}
            last = {"type": "result", "modelUsage": {"glm-5.3": {"outputTokens": 30, "cacheReadInputTokens": 500}}}
            (streams / "run1-case.jsonl").write_text(json.dumps(early) + "\n" + json.dumps(last) + "\n")
            (streams / "run1-case.login-failure-1.jsonl").write_text(json.dumps(last) + "\n")
            groups = rounds(Path(directory))
        self.assertEqual(groups["audit glm-5.3"]["responses"], 1)
        self.assertEqual(groups["audit glm-5.3"]["totals"]["output"], 30)
        self.assertEqual(groups["audit glm-5.3"]["totals"]["read"], 500)

    def test_read_prices_differ_by_exact_model(self):
        prices = load_prices()
        self.assertEqual(price_interval(record(read=1000000), prices), (0.2, 0.2))
        self.assertEqual(price_interval(record("claude-sonnet-5-5", read=1000000), prices), (0.1, 0.1))
        self.assertIsNone(price_interval(record("glm-5.3", read=1000000), prices))

    def test_zero_token_unknown_models_cost_zero_and_stay_counted(self):
        self.assertEqual(price_interval(record("<synthetic>"), load_prices()), (0.0, 0.0))
        self.assertEqual(price_interval(record("<synthetic>", aggregate=True), load_prices()), (0.0, 0.0))

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
