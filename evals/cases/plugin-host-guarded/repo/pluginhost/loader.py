"""Find plugin files and run them."""

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from pluginhost import flags
from pluginhost.settings import Settings


@dataclass
class Plugin:
    """A plugin file, imported the first time it is used."""

    name: str
    path: Path
    _module: ModuleType | None = field(default=None, init=False, repr=False)

    def load(self):
        if self._module is None:
            spec = importlib.util.spec_from_file_location(f"pluginhost_plugins.{self.name}", self.path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._module = module
        return self._module


def discover(settings: Settings) -> dict[str, Plugin]:
    plugins = {}
    for path in sorted(settings.plugin_dir.glob("*.py")):
        if path.name.startswith("_") and flags.enabled("skip_private_files", settings.flags):
            continue
        plugins[path.stem] = Plugin(path.stem, path)
    return plugins


def run(plugin: Plugin, context: dict) -> object:
    """Run a plugin with `context` and return its result."""
    try:
        return plugin.load().run(context)
    except Exception:
        return None
