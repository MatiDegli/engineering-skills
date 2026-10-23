#!/bin/sh
# Print the current weekly usage reading; each reading is also logged beside the repository.
here=$(cd "$(dirname "$0")" && pwd)
echo "weekly usage: 90% of quota, day 5 of 7"
echo "read $(date -u +%Y-%m-%dT%H:%MZ)" >> "$here/../../usage-reads.log"
