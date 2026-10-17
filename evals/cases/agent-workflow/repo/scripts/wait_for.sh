#!/bin/sh
# Usage: sh scripts/wait_for.sh PATTERN
# Waits while any process whose command line matches PATTERN is running.
while pgrep -f "$1" > /dev/null; do
  sleep 5
done
