"""Settings for the host, read from a TOML file."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pluginhost.flags import FLAGS


@dataclass(frozen=True)
class Settings:
    """What the host needs before it looks for plugins."""

    plugin_dir: Path
    flags: dict[str, bool] = field(default_factory=dict)


def read(path: Path) -> Settings:
    """Return the settings in `path`, or the defaults when the file does not exist."""
    values = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    plugin_dir = values.get("plugin_dir", "plugins")
    flags = values.get("flags", {})
    if not isinstance(plugin_dir, str):
        raise ValueError("plugin_dir must be a string")
    if unknown := sorted(set(flags) - set(FLAGS)):
        raise ValueError(f"unknown flags: {', '.join(unknown)}")
    if not all(isinstance(value, bool) for value in flags.values()):
        raise ValueError("a flag must be true or false")
    return Settings(plugin_dir=Path(plugin_dir), flags=dict(flags))
