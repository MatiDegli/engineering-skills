#!/bin/sh
# Run the benchmark for a front: PASSES passes of the workload (default 1), ten seconds apart,
# then log the run when it ends.
front=${1:-cli}
passes=${2:-1}
pass=0
while [ "$pass" -lt "$passes" ]; do
  [ "$pass" -gt 0 ] && sleep 10
  python3 tasklog.py --help > /dev/null
  pass=$((pass + 1))
done
echo "bench finished $(date -u +%Y-%m-%dT%H:%MZ) $front" >> ../shared/bench.log
