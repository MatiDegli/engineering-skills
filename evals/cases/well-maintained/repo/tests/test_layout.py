import re
import unittest
from pathlib import Path

TESTS = Path(__file__).parent
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class LayoutTests(unittest.TestCase):
    def test_every_test_module_is_discoverable(self):
        """Discovery silently skips non-identifier module names and non-package directories."""
        skipped = [
            path.name
            for path in TESTS.iterdir()
            if (path.is_dir() and path.name != "__pycache__")
            or (path.suffix == ".py" and not IDENTIFIER.fullmatch(path.stem))
        ]
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
