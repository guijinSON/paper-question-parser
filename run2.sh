#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root.
# Put target arXiv links in TARGETS_FILE
TARGETS_FILE="targets2"

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_${ERROR_TIMESTAMP}.log"

if [[ ! -f "$TARGETS_FILE" ]]; then
  echo "Missing targets file: $TARGETS_FILE" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR"

exec 3< "$TARGETS_FILE"
while IFS= read -r arxiv_link <&3 || [[ -n "$arxiv_link" ]]; do
  [[ -z "$arxiv_link" ]] && continue
  if ! opencode run "@RUN_ME.md $arxiv_link" </dev/null; then
    echo "error occurred: $arxiv_link" >> "$ERROR_LOG_FILE"
    continue
  fi
done
exec 3<&-
