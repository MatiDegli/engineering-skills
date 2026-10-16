# slugkit

Converts titles into URL slugs for an internal publishing tool. It uses only the Python standard
library and has no third-party dependencies.

## Requirements

Python 3.12 on Linux, pinned in `.python-version`.

## Usage

```bash
python3 -m slugkit "Hello, World!"
```

Prints `hello-world`. Accented Latin letters become their ASCII base letter; letters without an ASCII
transliteration, such as Cyrillic or Greek, are dropped. Titles longer than 200 characters, and
titles left without ASCII letters or digits, exit with status 2 and a message.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

CI runs the same command on every push and pull request.
