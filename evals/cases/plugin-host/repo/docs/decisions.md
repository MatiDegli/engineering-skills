# Decisions

Each decision records its date, what was decided, the alternatives, and the consequences.

## 1. Plugins are plain Python files (2025-09-12)

A plugin is one file with a `run(context)` function. Alternatives: classes registered through
entry points, which need packaging for every plugin, and a subprocess protocol, which needs a wire
format. Consequence: plugins run in the host's process and can break it.

## 2. No third-party dependencies (2025-09-12)

The library uses only the standard library, so installing it adds nothing to a consumer's
environment. Consequence: configuration is TOML, read with `tomllib`.

## 3. Read settings with `settings.read()` and retire `config_loader` (2026-03-10)

`config_loader.load()` returns whatever the TOML file holds, so every caller repeats the defaults
and the type checks, and a wrong type fails in the middle of a run. `settings.read()` returns one
immutable `Settings` with the defaults applied and the types checked when the file is read.

Decision: new code reads settings with `settings.read()`, and `config_loader` is retired. Callers
move over as they are changed.

Alternatives: keep the dictionary and validate in each caller, which let the checks drift apart,
and adopt a settings library, which decision 2 rules out. Consequence: `Settings` gains a field
whenever a caller needs a new key.
