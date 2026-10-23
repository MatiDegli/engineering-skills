#!/bin/sh
# Start a round on a tier: launch-round.sh JOB TIER. Each launch is recorded in launches/JOB.txt.
case "$1" in
    experiment|validation) ;;
    *) echo "launch-round: unknown round '$1' (rounds: experiment, validation)" >&2; exit 2 ;;
esac
case "$2" in
    tier-small|tier-large) ;;
    *) echo "launch-round: unknown tier '$2' (tiers: tier-small, tier-large)" >&2; exit 2 ;;
esac
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/../../launches"
echo "launched $1 on $2 at $(date -u +%Y-%m-%dT%H:%MZ)" >> "$here/../../launches/$1.txt"
echo "round $1 queued on $2"
