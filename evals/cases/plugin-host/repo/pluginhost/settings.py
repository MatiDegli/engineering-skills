"""Settings for the host, read from a TOML file."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    plugin_dir: Path
    lazy_load: bool = True


def read(path: Path) -> Settings:
    """Return the settings in `path`, or the defaults when the file does not exist."""
    values = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    plugin_dir = values.get("plugin_dir", "plugins")
    lazy_load = values.get("lazy_load", True)
    if not isinstance(plugin_dir, str):
        raise ValueError("plugin_dir must be a string")
    if not isinstance(lazy_load, bool):
        raise ValueError("lazy_load must be true or false")
    return Settings(plugin_dir=Path(plugin_dir), lazy_load=lazy_load)
