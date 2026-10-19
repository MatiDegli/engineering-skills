import tempfile
import unittest
from pathlib import Path

from tools.check_docstrings import check

UNDOCUMENTED = "def public():\n    pass\n"
DOCUMENTED = 'def public():\n    """Do the work."""\n'
LISTED = {"pluginhost/module.py": ["public"]}


class DocstringBaselineTests(unittest.TestCase):
    def package(self, source):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "pluginhost").mkdir()
        (root / "pluginhost" / "module.py").write_text(source)
        return root

    def test_a_documented_package_passes_with_an_empty_baseline(self):
        self.assertEqual(check(self.package(DOCUMENTED), {}), [])

    def test_a_violation_that_is_not_in_the_baseline_fails(self):
        self.assertEqual(check(self.package(UNDOCUMENTED), {}), ["new violation: pluginhost/module.py::public"])

    def test_a_violation_in_the_baseline_passes(self):
        self.assertEqual(check(self.package(UNDOCUMENTED), LISTED), [])

    def test_a_fixed_violation_must_leave_the_baseline(self):
        self.assertEqual(
            check(self.package(DOCUMENTED), LISTED),
            ["fixed, delete it from the baseline: pluginhost/module.py::public"],
        )

    def test_a_method_is_its_own_entry_and_private_names_are_skipped(self):
        source = 'class Thing:\n    """A thing."""\n\n    def act(self):\n        pass\n\n    def _hidden(self):\n        pass\n'
        self.assertEqual(check(self.package(source), {}), ["new violation: pluginhost/module.py::Thing.act"])

    def test_a_new_file_is_checked_too(self):
        root = self.package(DOCUMENTED)
        (root / "pluginhost" / "extra.py").write_text(UNDOCUMENTED)
        self.assertEqual(check(root, {}), ["new violation: pluginhost/extra.py::public"])


if __name__ == "__main__":
    unittest.main()
