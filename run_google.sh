#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root.
# Reads URLs from the 'url' column of the google problems CSV.
PAPERS_CSV_FILE="${PAPERS_CSV_FILE:-google-op-papers-validated.csv}"
OPENCODE_AGENT="${OPENCODE_AGENT:-}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/google_problems}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
LATEST_FILE="outputs/latest.json"

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_${ERROR_TIMESTAMP}.log"

if [[ ! -f "$PAPERS_CSV_FILE" ]]; then
  echo "Missing papers CSV file: $PAPERS_CSV_FILE" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR"
mkdir -p "$OUTPUT_DIR"

# Derive a sanitized slug from any URL (PDF stem or host+path).
# Matches the skill's sanitization rule: / -> _, non-alphanumeric except - and . -> _.
derive_slug() {
  python3 - "$1" <<'PY'
import sys, re
from urllib.parse import urlparse, unquote

raw = sys.argv[1].split('#')[0].split('?')[0].rstrip('/')
parsed = urlparse(raw)
path = unquote(parsed.path)

if path.lower().endswith('.pdf'):
    slug = path.split('/')[-1][:-4]
else:
    slug = parsed.netloc + path

slug = slug.replace('/', '_')
slug = re.sub(r'[^a-zA-Z0-9\-\.]', '_', slug)
print(slug)
PY
}

has_valid_output_checkpoint() {
  local output_file="$1"
  [[ -s "$output_file" ]] || return 1
  python3 - "$output_file" <<'PY'
import json, sys
from pathlib import Path

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

required_keys = {"accepted", "needs_review", "trace"}
raise SystemExit(0 if isinstance(payload, dict) and required_keys.issubset(payload) else 1)
PY
}

while IFS=$'\t' read -r url <&3; do
  [[ -z "$url" ]] && continue

  slug="$(derive_slug "$url")"
  output_file="$OUTPUT_DIR/${slug}.json"

  if [[ "$SKIP_EXISTING" == "1" ]] && has_valid_output_checkpoint "$output_file"; then
    echo "skipping completed: $url" >&2
    continue
  fi

  echo "running: $url" >&2
  opencode_cmd=(opencode run)
  if [[ -n "$OPENCODE_AGENT" ]]; then
    opencode_cmd+=(--agent "$OPENCODE_AGENT")
  fi

  if ! "${opencode_cmd[@]}" "/paper-question-parser $url" </dev/null 3<&-; then
    echo "error occurred: $url -> $output_file" >> "$ERROR_LOG_FILE"
    continue
  fi

  # The skill always writes outputs/latest.json; copy it into our output dir.
  if [[ -s "$LATEST_FILE" ]]; then
    cp "$LATEST_FILE" "$output_file"
    echo "saved: $output_file" >&2
  else
    echo "warning: latest.json missing after run for $url" >&2
  fi
done 3< <(
  python3 - "$PAPERS_CSV_FILE" <<'PY'
import csv, sys
from pathlib import Path

with Path(sys.argv[1]).open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    if "url" not in (reader.fieldnames or []):
        raise SystemExit("Missing 'url' column in CSV")
    for row in reader:
        url = (row.get("url") or "").strip()
        if url:
            print(url)
PY
)
