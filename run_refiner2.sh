#!/usr/bin/env bash
set -euo pipefail

TARGETS_FILE="targets_refiner2"

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_refiner_${ERROR_TIMESTAMP}.log"

if [[ ! -f "$TARGETS_FILE" ]]; then
  echo "Missing targets file: $TARGETS_FILE" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR"

exec 3< "$TARGETS_FILE"
while IFS= read -r payload <&3 || [[ -n "$payload" ]]; do
  [[ -z "$payload" ]] && continue
  if ! opencode run "@RUN_ME.md /paper-question-refiner $payload" </dev/null; then
    echo "error occurred: $payload" >> "$ERROR_LOG_FILE"
    continue
  fi
done
exec 3<&-
