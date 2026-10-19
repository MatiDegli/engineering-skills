# Changelog

All notable changes to pluginhost. Before 1.0, any release may change the interface.

## 0.9.2 - 2026-10-06

### Fixed

- `pluginhost run` no longer prints `None` for a plugin that returns nothing.

## 0.9.1 - 2026-09-15

### Added

- The `skip_private_files` release flag: files whose names start with an underscore are not
  treated as plugins. It is off by default while it rolls out; its owner and expiry date are in
  `pluginhost/flags.py`.

## 0.9.0 - 2026-08-11

### Added

- `pluginhost list --json` prints the plugin names as a JSON array.

### Removed

- The `--format` option of `pluginhost list`. Use `--json` instead.

## 0.8.0 - 2026-06-23

### Added

- A docstring is required for every public function, method, and class. The older ones are listed
  in `tools/docstring-baseline.json`, which CI keeps from growing.

## 0.7.0 - 2026-04-14

### Added

- `pluginhost list --format {text,json}` chooses how the plugin names are printed.
