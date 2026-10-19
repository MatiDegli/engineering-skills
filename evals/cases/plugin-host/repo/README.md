# pluginhost

Finds plugins in a directory and runs them, from Python or the command line. A plugin is a Python
file with a `run(context)` function. The library uses only the Python standard library and is
published on PyPI. Ines Rao, Tobias Wu, and Amara Okafor maintain it.

## Install

```bash
python3 -m pip install pluginhost
```

It needs Python 3.11 or newer.

## Command line

```bash
pluginhost list          # one plugin name per line
pluginhost list --json   # the names as a JSON array
pluginhost run NAME      # run one plugin and print its result
```

`--config FILE`, given before the command, names the configuration file; the default is
`pluginhost.toml`. Exit status 1 means the plugin failed, and 2 means there is no such plugin.

## Configuration

```toml
plugin_dir = "plugins"   # where the plugin files are
hooks = ["audit"]        # plugins that run before every `pluginhost run`
```

## Python

```python
from pathlib import Path
from pluginhost import discover, read

plugins = discover(read(Path("pluginhost.toml")))
plugins["audit"].run({})
```

## Validation

```bash
python3 -m unittest discover -s tests -v
```

CI runs the same command on every push and pull request.

## Releasing

Any maintainer can release. Raise `version` in `pyproject.toml` and add the CHANGELOG entry in a
pull request that another maintainer approves. After it merges, tag `vX.Y.Z` on `main`, build with
`python3 -m build`, and upload with `python3 -m twine upload dist/*`.
