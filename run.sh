#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root.
# Put target arXiv links in TARGETS_FILE
TARGETS_FILE="targets"

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_${ERROR_TIMESTAMP}.log"

if [[ ! -f "$TARGETS_FILE" ]]; then
  echo "Missing targets file: $TARGETS_FILE" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR"

while IFS= read -r arxiv_link || [[ -n "$arxiv_link" ]]; do
  [[ -z "$arxiv_link" ]] && continue
  if ! oh-my-opencode run "/paper-question-parser $arxiv_link"; then
    echo "error occurred: $arxiv_link" >> "$ERROR_LOG_FILE"
    continue
  fi
done < "$TARGETS_FILE"
