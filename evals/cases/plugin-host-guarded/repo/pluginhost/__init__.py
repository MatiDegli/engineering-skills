"""Find plugins in a directory and run them."""

from pluginhost.loader import Plugin, discover, run
from pluginhost.settings import Settings, read

__all__ = ["Plugin", "Settings", "discover", "read", "run"]
