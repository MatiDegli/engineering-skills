"""Check that the ledger counts each response once and weights each kind of token."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.claude_ledger import rounds, shares, transcripts


def response(identifier, model, **usage):
    return {"type": "assistant", "message": {"id": identifier, "model": model, "usage": usage}}


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


if __name__ == "__main__":
    unittest.main()
