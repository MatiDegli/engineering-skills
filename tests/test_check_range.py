"""Check that every commit of a range is checked on its own tree, without history."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_range import check_commit, commits
from tools.evals import git_environment

CHECK = """import pathlib, subprocess, sys
history = subprocess.run(["git", "rev-parse", "HEAD~1"], capture_output=True).returncode == 0
broken = pathlib.Path("broken").exists()
print("FAILED" if broken or not history and pathlib.Path("needs-history").exists() else "OK")
sys.exit(1 if broken or not history and pathlib.Path("needs-history").exists() else 0)
"""


class CheckRangeTests(unittest.TestCase):
    def test_each_commit_is_checked_alone_and_without_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid"}
            identity |= {"GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

            def git(*arguments):
                subprocess.run(
                    ["git", *arguments], cwd=root, env=git_environment(**identity),
                    capture_output=True, check=True,
                )

            git("init", "-q", "-b", "main")
            (root / "tools").mkdir()
            (root / "tools" / "check.py").write_text(CHECK)
            steps = [("base", None), ("broken", "broken"), ("fixed", None), ("history", "needs-history")]
            for message, path in steps:
                if message == "fixed":
                    (root / "broken").unlink()
                elif path:
                    (root / path).write_text("x\n")
                git("add", "-A")
                git("commit", "-q", "-m", message)
            results = [check_commit(root, commit)[0] for commit in commits(root, "HEAD")]
        self.assertEqual(results, [0, 1, 0, 1])


if __name__ == "__main__":
    unittest.main()
