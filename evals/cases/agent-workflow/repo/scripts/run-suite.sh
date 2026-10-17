#!/bin/sh
# Runs the full validation: every test module in tests/.
set -eu
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -p "test_*.py" -v
