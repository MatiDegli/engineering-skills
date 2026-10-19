"""Find plugins in a directory and run them."""

from pluginhost.loader import Plugin, PluginError, discover
from pluginhost.settings import Settings, read

__all__ = ["Plugin", "PluginError", "Settings", "discover", "read"]
