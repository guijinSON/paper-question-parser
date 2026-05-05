#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root.
# Reads source URLs from outputs/open-problems-0418-all.csv.
OPEN_PROBLEMS_CSV_FILE="${OPEN_PROBLEMS_CSV_FILE:-outputs/open-problems-0418-all.csv}"
OPENCODE_AGENT="${OPENCODE_AGENT:-}"

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_${ERROR_TIMESTAMP}.log"

if [[ ! -f "$OPEN_PROBLEMS_CSV_FILE" ]]; then
  echo "Missing open problems CSV file: $OPEN_PROBLEMS_CSV_FILE" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR"

while IFS=$'\t' read -r source title source_url <&3; do
  [[ -z "$source_url" ]] && continue
  echo "running: $source | $title | $source_url" >&2
  opencode_cmd=(opencode run)
  if [[ -n "$OPENCODE_AGENT" ]]; then
    opencode_cmd+=(--agent "$OPENCODE_AGENT")
  fi
  if ! "${opencode_cmd[@]}" "/paper-question-parser $source_url" </dev/null 3<&-; then
    echo "error occurred: $source | $title | $source_url" >> "$ERROR_LOG_FILE"
    continue
  fi
done 3< <(
  python3 - "$OPEN_PROBLEMS_CSV_FILE" <<'PY'
import csv
import sys
from pathlib import Path

csv_path = Path(sys.argv[1])

with csv_path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames or []
    missing = [name for name in ("source", "title", "url") if name not in fieldnames]
    if missing:
        raise SystemExit(f"Missing required CSV columns: {', '.join(missing)}")

    for row in reader:
        source = (row.get("source") or "").strip().replace("\t", " ").replace("\n", " ")
        title = (row.get("title") or "").strip().replace("\t", " ").replace("\n", " ")
        url = (row.get("url") or "").strip()
        if not url:
            continue
        print(f"{source}\t{title}\t{url}")
PY
)
