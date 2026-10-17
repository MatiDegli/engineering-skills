"""Index Markdown notes, with one worker process per directory."""

import json
import subprocess
import sys
from pathlib import Path

WORKER_TAG = "notesync-worker"


def note_entry(path: Path) -> dict:
    """Return the path, title, and word count of one note."""
    text = path.read_text(encoding="utf-8")
    heading = next((line for line in text.splitlines() if line.startswith("# ")), "")
    return {"path": path.as_posix(), "title": heading[2:].strip() or path.stem, "words": len(text.split())}


def build_index(root: Path) -> list[dict]:
    """Index every Markdown file under root, sorted by path."""
    return [note_entry(path) for path in sorted(root.rglob("*.md"))]


def index_directories(directories: list[Path], output: Path) -> None:
    """Index each directory in its own worker and write the combined index."""
    workers = [
        subprocess.Popen(
            [sys.executable, "-m", "notesync", "worker", str(directory), WORKER_TAG],
            stdout=subprocess.PIPE,
        )
        for directory in directories
    ]
    entries = []
    for worker in workers:
        out, _ = worker.communicate(timeout=60)
        entries += json.loads(out)
    output.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
