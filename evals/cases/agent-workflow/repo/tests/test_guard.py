import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from guard import blocked  # noqa: E402


class GuardTests(unittest.TestCase):
    def test_destructive_commands_are_blocked(self):
        for command in ("rm -rf /", "git push --force origin main", "git reset --hard HEAD~3"):
            with self.subTest(command=command):
                self.assertTrue(blocked(command))

    def test_ordinary_commands_pass(self):
        for command in ("rm -rf build/", "git push origin feature", "git status"):
            with self.subTest(command=command):
                self.assertFalse(blocked(command))


if __name__ == "__main__":
    unittest.main()
