"""Read the configuration file as a dictionary."""

import tomllib
from pathlib import Path


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)
