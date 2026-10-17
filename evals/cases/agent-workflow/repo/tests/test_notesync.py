import json
import tempfile
import unittest
from pathlib import Path

from notesync.core import WORKER_TAG, build_index, index_directories


class IndexTests(unittest.TestCase):
    def test_titles_come_from_the_first_heading_or_the_file_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.md").write_text("# Alpha\nsome words here\n", encoding="utf-8")
            (root / "b.md").write_text("no heading\n", encoding="utf-8")
            titles = [entry["title"] for entry in build_index(root)]
        self.assertEqual(titles, ["Alpha", "b"])

    def test_the_index_combines_every_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("one", "two"):
                (root / name).mkdir()
                (root / name / "note.md").write_text(f"# {name}\n", encoding="utf-8")
            output = root / "index.json"
            index_directories([root / "one", root / "two"], output)
            titles = [entry["title"] for entry in json.loads(output.read_text(encoding="utf-8"))]
        self.assertEqual(titles, ["one", "two"])


class WorkerTests(unittest.TestCase):
    def test_no_worker_is_left_running(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.md").write_text("# Note\n", encoding="utf-8")
            index_directories([root], root / "index.json")
        leftovers = [
            entry.name
            for entry in Path("/proc").iterdir()
            if entry.name.isdigit() and WORKER_TAG.encode() in (entry / "cmdline").read_bytes()
        ]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
