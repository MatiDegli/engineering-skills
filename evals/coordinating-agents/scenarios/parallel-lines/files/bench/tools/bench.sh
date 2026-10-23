#!/bin/sh
# Run the benchmark for a front for SECONDS (default 2): one pass of the workload every ten
# seconds, then log the run when it ends.
front=${1:-cli}
elapsed=0
while [ "$elapsed" -lt "${2:-2}" ]; do
  [ $((elapsed % 10)) -eq 0 ] && python3 tasklog.py --help > /dev/null
  sleep 1
  elapsed=$((elapsed + 1))
done
echo "bench finished $(date -u +%Y-%m-%dT%H:%MZ) $front" >> ../shared/bench.log
