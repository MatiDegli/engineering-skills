#!/bin/sh
# Stops notesync workers left behind by an interrupted index run.
pkill -f notesync-worker || true
