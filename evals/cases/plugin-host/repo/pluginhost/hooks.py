"""Run the hook plugins that the configuration lists."""

from pathlib import Path

from pluginhost import config_loader
from pluginhost.loader import Plugin, PluginError


def run_before(config_path: Path, plugins: dict[str, Plugin], context: dict) -> None:
    """Run each plugin listed under `hooks` in the configuration file, in order."""
    for name in config_loader.load(config_path).get("hooks", []):
        if name not in plugins:
            raise PluginError(f"hook {name} is not a plugin")
        plugins[name].run(context)
