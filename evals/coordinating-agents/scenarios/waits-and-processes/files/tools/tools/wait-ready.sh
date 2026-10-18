#!/bin/sh
# Wait until a gate finishes; prints ready.
while pgrep -f "$1" > /dev/null; do sleep 5; done; echo ready
