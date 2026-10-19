"""Find plugin files and run them."""

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from pluginhost.settings import Settings


class PluginError(Exception):
    """A plugin could not be imported or failed while running."""


@dataclass
class Plugin:
    name: str
    path: Path
    _module: ModuleType | None = field(default=None, init=False, repr=False)

    def load(self) -> ModuleType:
        """Import the plugin file on first use and return its module."""
        if self._module is None:
            spec = importlib.util.spec_from_file_location(f"pluginhost_plugins.{self.name}", self.path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as error:
                raise PluginError(f"{self.name} failed to load: {error}") from error
            self._module = module
        return self._module

    def run(self, context: dict) -> object:
        """Call the plugin's `run(context)` function and return its result."""
        module = self.load()
        try:
            return module.run(context)
        except Exception as error:
            raise PluginError(f"{self.name} failed: {error}") from error


def discover(settings: Settings) -> dict[str, Plugin]:
    """Return the plugin files of `settings.plugin_dir` by name."""
    plugins = {path.stem: Plugin(path.stem, path) for path in sorted(settings.plugin_dir.glob("*.py"))}
    if not settings.lazy_load:
        for plugin in plugins.values():
            plugin.load()
    return plugins
