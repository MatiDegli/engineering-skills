#!/usr/bin/env bash
# Validate all local workflows with verified upstream binaries; no global installation.
set -euo pipefail

if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo 'Workflow validation requires Linux x86_64 (WSL2 or the Ubuntu CI runner).' >&2
  exit 1
fi

workflow_script=$(realpath -- "${BASH_SOURCE[0]}")
cd -- "$(dirname -- "$workflow_script")/.."
if [[ -L .github || -L .github/workflows ]]; then
  echo 'Workflow directories must not be symlinks.' >&2
  exit 1
fi
shopt -s nullglob
workflows=(.github/workflows/*.yml .github/workflows/*.yaml)
if (( ${#workflows[@]} == 0 )); then
  echo 'No workflows found.' >&2
  exit 1
fi
for workflow in "${workflows[@]}"; do
  if [[ ! -f $workflow || -L $workflow ]]; then
    echo "Expected a regular workflow file: $workflow" >&2
    exit 1
  fi
done

workflow_tmp=$(mktemp -d)
trap 'rm -rf -- "$workflow_tmp"' EXIT

download() {
  local url=$1 destination=$2 digest=$3
  curl -q --fail --silent --show-error --location --proto '=https' \
    --connect-timeout 10 --max-time 60 --max-filesize 16777216 \
    "$url" --output "$destination"
  if ! printf '%s  %s\n' "$digest" "$destination" | sha256sum --check --status; then
    echo "Checksum mismatch: ${destination##*/}" >&2
    return 1
  fi
}

# Reviewed official release assets; update versions and digests together.
actionlint_version=1.7.12
shellcheck_version=0.11.0
download "https://github.com/rhysd/actionlint/releases/download/v${actionlint_version}/actionlint_${actionlint_version}_linux_amd64.tar.gz" \
  "$workflow_tmp/actionlint.tar.gz" 8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
download "https://github.com/koalaman/shellcheck/releases/download/v${shellcheck_version}/shellcheck-v${shellcheck_version}.linux.x86_64.tar.xz" \
  "$workflow_tmp/shellcheck.tar.xz" 8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198
# Read only the named executables; archive paths never become filesystem destinations.
tar -xzOf "$workflow_tmp/actionlint.tar.gz" actionlint > "$workflow_tmp/actionlint"
tar -xJOf "$workflow_tmp/shellcheck.tar.xz" "shellcheck-v${shellcheck_version}/shellcheck" > "$workflow_tmp/shellcheck"
chmod 700 "$workflow_tmp/actionlint" "$workflow_tmp/shellcheck"
timeout 60 "$workflow_tmp/shellcheck" --norc "$workflow_script"
export SHELLCHECK_OPTS=--norc
timeout 60 "$workflow_tmp/actionlint" -shellcheck="$workflow_tmp/shellcheck" -pyflakes= -- "${workflows[@]}"
echo 'Workflow syntax, expressions and embedded shell: OK'
