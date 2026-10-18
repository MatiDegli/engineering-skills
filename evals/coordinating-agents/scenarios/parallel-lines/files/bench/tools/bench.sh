#!/bin/sh
# Run the benchmark for a front: log the start, then run the workload.
echo "bench started $(date -u +%Y-%m-%dT%H:%MZ)" >> ../shared/bench.log
sleep 2
