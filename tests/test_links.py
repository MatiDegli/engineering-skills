"""Exercise HTTP results against an owned local server; no external network required."""

import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from tools.check_links import check_url, external_links
from tools.validate_repo import ROOT


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = {
            "/ok": 200,
            "/redirect": 302,
            "/missing": 404,
            "/gone": 410,
            "/denied": 403,
            "/limited": 429,
            "/unavailable": 503,
        }.get(self.path, 404)
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "/ok")
        self.end_headers()

    def log_message(self, *args):
        pass


class ExternalLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if cls.thread.is_alive():
            raise RuntimeError("Local test server did not stop")

    def test_redirects_errors_and_rate_limits_have_distinct_outcomes(self):
        for path, state in (
            ("ok", "OK"),
            ("redirect", "OK"),
            ("missing", "BROKEN"),
            ("gone", "BROKEN"),
            ("denied", "UNVERIFIED"),
            ("limited", "UNVERIFIED"),
            ("unavailable", "UNVERIFIED"),
        ):
            with self.subTest(path=path):
                self.assertEqual(check_url(f"{self.base}/{path}")[0], state)

    def test_timeout_is_not_a_success(self):
        with patch("tools.check_links.urlopen", side_effect=TimeoutError("slow")):
            self.assertEqual(check_url(self.base)[0], "UNVERIFIED")

    def test_inventory_deduplicates_fragments_and_ignores_code_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(
                f"[one]({self.base}/ok#first) [two]({self.base}/ok#second)\n"
                f"```md\n[example]({self.base}/missing)\n```\n"
                f"`[inline]({self.base}/denied)`\n"
            )
            self.assertEqual(external_links(root), {f"{self.base}/ok": {"README.md"}})

    def test_cli_fails_for_broken_and_unverified_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            for name in ("check_links.py", "validate_repo.py"):
                (root / "tools" / name).write_bytes(
                    (ROOT / "tools" / name).read_bytes()
                )
            for path, code in (("ok", 0), ("missing", 1), ("denied", 1)):
                (root / "README.md").write_text(f"[link]({self.base}/{path})\n")
                result = subprocess.run(
                    [sys.executable, "-m", "tools.check_links"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
