# Changelog

All notable changes to pluginhost. Versions follow semantic versioning.

## 1.5.0 - 2026-07-14

### Added

- Hooks: the plugins listed under `hooks` in the configuration file run before every
  `pluginhost run`.

## 1.4.0 - 2026-05-19

### Added

- `pluginhost list --json` prints the plugin names as a JSON array.

### Removed

- The `--format` option of `pluginhost list`. Use `--json` instead.

## 1.3.0 - 2026-04-02

### Changed

- Plugins load lazily for everyone, on first use. The rollout that began in 1.2.0 is complete, and
  no regression was reported against it.
- The loader and the command line read their settings with `settings.read()`, which applies the
  defaults and checks the types once (decision 3 in `docs/decisions.md`).

## 1.2.0 - 2026-02-24

### Added

- Lazy plugin loading: a plugin is imported when it first runs. It is behind the `lazy_load`
  setting, off by default, while it rolls out.

## 1.1.0 - 2026-01-13

### Added

- `pluginhost list --format {text,json}` chooses how the plugin names are printed.

## 1.0.0 - 2025-11-18

First stable release.
