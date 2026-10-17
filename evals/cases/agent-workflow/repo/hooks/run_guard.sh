#!/bin/sh
# Pre-command hook for the agents' tool: exit status 2 blocks the command.
python3 "$(dirname "$0")/guard.py" "$@" || exit 2
