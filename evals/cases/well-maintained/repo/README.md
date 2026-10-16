# slugkit

Converts titles into URL slugs for an internal publishing tool. It uses only the Python standard
library and has no third-party dependencies.

## Requirements

Python 3.12 on Linux, pinned in `.python-version`. There is nothing to install: clone the
repository and run the commands below from its root. The publishing tool runs
`python3 -m slugkit` the same way, from a checkout of this repository at a reviewed commit; nothing
is packaged or published.

## Usage

```bash
python3 -m slugkit "Hello, World!"
```

Prints `hello-world`. Compatibility characters are first replaced by their standard forms, so ﬁ
becomes fi and full-width letters become ASCII letters; a slug can therefore be longer than its
title. Letters that Unicode decomposes into an ASCII letter and accents, such as é or ñ, become that
letter. Other letters are dropped, including ø, ß, ł, đ, æ, and œ, and Cyrillic or Greek letters.
Titles longer than 200 characters, and titles left without ASCII letters or digits, exit with
status 2 and a message.

Put `--` before a title that starts with `-`; otherwise it is read as an option:

```bash
python3 -m slugkit -- "-30%"
```

## Validation

```bash
python3 -m unittest discover -s tests -p "*.py" -v
```

Discovery skips modules whose names are not Python identifiers and directories that are not
packages, so test modules live directly in `tests/` with identifier names. `tests/test_layout.py`
fails when a file or directory there breaks that rule. CI runs the same command on every push and
pull request.
