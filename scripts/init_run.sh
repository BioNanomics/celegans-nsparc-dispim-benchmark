#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/or/relative/private/run-folder" >&2
  exit 2
fi
out="$1"
mkdir -p "$out"
if compgen -G "$out/*.csv" > /dev/null; then
  echo "Existing CSVs found; refusing to overwrite $out" >&2
  exit 1
fi
cp data/templates/*.csv "$out/"
echo "Created empty protocol CSVs in $out (keep outside public Git)."
