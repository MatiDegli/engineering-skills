"""Delete the scratch directories that tasklog runs leave in /tmp."""

import shutil
import sys
import time
from pathlib import Path

PATTERN = "tasklog-*"
MAX_AGE_SECONDS = 24 * 60 * 60


def clean(root=Path("/tmp"), now=None):
    """Remove the directories under root that match PATTERN and are older than a day; return them."""
    now = time.time() if now is None else now
    removed = []
    for path in sorted(root.glob(PATTERN)):
        if path.is_dir() and now - path.stat().st_mtime > MAX_AGE_SECONDS:
            shutil.rmtree(path)
            removed.append(path)
    return removed


if __name__ == "__main__":
    for removed in clean():
        print(f"removed {removed}")
    sys.exit(0)
