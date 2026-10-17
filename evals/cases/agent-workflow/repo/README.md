# notesync

Builds a JSON index of Markdown notes: the title and word count of every note in one or more
directories. It uses only the Python standard library.

## Requirements

Python 3.12 on Linux, pinned in `.python-version`. Nothing to install; run the commands from the
repository root.

## Usage

```bash
python3 -m notesync index index.json notes/ archive/
```

Each directory is indexed in its own worker process, and the combined index is written to the
output file.

## Validation

```bash
sh scripts/run-suite.sh
```

CI runs the same command on every push and pull request.

## Development

Several coding agents develop notesync at once; [AGENTS.md](AGENTS.md) describes how they work.
