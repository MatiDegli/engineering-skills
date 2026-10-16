# slugkit

Converts titles into URL slugs for an internal publishing tool. It uses only the Python standard
library and has no third-party dependencies.

## Requirements

Python 3.12 on Linux, pinned in `.python-version`.

## Usage

```bash
python -m slugkit "Hello, World!"
```

Prints `hello-world`. Empty titles, titles without letters or digits, and titles longer than 200
characters exit with status 2 and a message.

## Validation

```bash
python -m unittest discover -s tests -v
```

CI runs the same command on every push and pull request.
