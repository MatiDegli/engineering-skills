# pluginhost

Finds plugins in a directory and runs them, from Python or the command line. A plugin is a Python
file with a `run(context)` function. The library uses only the Python standard library and is
published on PyPI. Ines Rao, Tobias Wu, and Amara Okafor maintain it.

Versions before 1.0 may change the interface in any release; the CHANGELOG lists each change.

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
`pluginhost.toml`. Exit status 2 means there is no such plugin.

## Configuration

```toml
plugin_dir = "plugins"   # where the plugin files are
```

Release flags, which `pluginhost/flags.py` lists with their owner and expiry date, go under a
`[flags]` table while a change rolls out.

## Python

```python
from pathlib import Path
from pluginhost import discover, read, run

plugins = discover(read(Path("pluginhost.toml")))
run(plugins["audit"], {})
```

## Validation

```bash
python3 tools/check_docstrings.py && python3 -m unittest discover -s tests -v
```

The first command fails when a public function, method, or class has no docstring. The violations
that predate the rule are listed in `tools/docstring-baseline.json` with their reason, owner, and
removal condition. The command also fails when a listed symbol gains a docstring, so the baseline
only shrinks. Adding an entry is a decision of its own and goes in a separate pull request. CI runs
the same command on every push and pull request.

## Releasing

Any maintainer can release. Raise `version` in `pyproject.toml` and add the CHANGELOG entry in a
pull request that another maintainer approves. After it merges, tag `vX.Y.Z` on `main`, build with
`python3 -m build`, and upload with `python3 -m twine upload dist/*`.
