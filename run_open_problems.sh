#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root.
# Reads source URLs from outputs/open-problems-0418-all.csv.
OPEN_PROBLEMS_CSV_FILE="${OPEN_PROBLEMS_CSV_FILE:-outputs/open-problems-0418-all.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/parse-paper}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
DRY_RUN="${DRY_RUN:-0}"
MAX_ROWS="${MAX_ROWS:-}"
MAX_RUNS="${MAX_RUNS:-}"

CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_MODEL="${CODEX_MODEL:-}"
CODEX_PROFILE="${CODEX_PROFILE:-}"
CODEX_SANDBOX="${CODEX_SANDBOX:-workspace-write}"
CODEX_APPROVAL="${CODEX_APPROVAL:-}"
CODEX_SEARCH="${CODEX_SEARCH:-1}"
PAPER_QUESTION_PARSER_SKILL="${PAPER_QUESTION_PARSER_SKILL:-.opencode/skills/paper-question-parser/SKILL.md}"

if [[ "$CODEX_SANDBOX" == "seatbelt" ]]; then
  CODEX_SANDBOX="workspace-write"
fi

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_${ERROR_TIMESTAMP}.log"
COMPLETED_URLS_FILE=""

if [[ ! -f "$OPEN_PROBLEMS_CSV_FILE" ]]; then
  echo "Missing open problems CSV file: $OPEN_PROBLEMS_CSV_FILE" >&2
  exit 1
fi

if [[ ! -f "$PAPER_QUESTION_PARSER_SKILL" ]]; then
  echo "Missing paper-question-parser skill file: $PAPER_QUESTION_PARSER_SKILL" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR"
mkdir -p "$OUTPUT_DIR"

if [[ "$SKIP_EXISTING" == "1" ]]; then
  COMPLETED_URLS_FILE="$(mktemp "${TMPDIR:-/tmp}/open-problems-completed.XXXXXX")"
  trap '[[ -z "${COMPLETED_URLS_FILE:-}" ]] || rm -f "$COMPLETED_URLS_FILE"' EXIT

  python3 - "$OUTPUT_DIR" > "$COMPLETED_URLS_FILE" <<'PY'
import json
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
required_keys = {"accepted", "needs_review", "trace"}

for output_path in sorted(output_dir.glob("*.json")):
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        continue

    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        continue

    source = payload.get("source")
    if not isinstance(source, dict):
        continue

    source_url = (source.get("url") or "").strip()
    if source_url:
        print(source_url)
PY
  echo "indexed $(wc -l < "$COMPLETED_URLS_FILE" | tr -d ' ') completed source URLs from $OUTPUT_DIR" >&2
fi

has_completed_source_url() {
  local source_url="$1"

  [[ "$SKIP_EXISTING" == "1" ]] || return 1
  [[ -n "$COMPLETED_URLS_FILE" ]] || return 1
  grep -Fxq -- "$source_url" "$COMPLETED_URLS_FILE"
}

run_paper_question_parser_with_codex() {
  local source_url="$1"
  local -a codex_cmd=("$CODEX_BIN")

  if [[ "$CODEX_SEARCH" != "0" ]]; then
    codex_cmd+=(--search)
  fi

  codex_cmd+=(exec --cd "$PWD" --sandbox "$CODEX_SANDBOX")

  if [[ -n "$CODEX_APPROVAL" ]]; then
    if "$CODEX_BIN" exec --help 2>&1 | grep -q -- '--ask-for-approval'; then
      codex_cmd+=(--ask-for-approval "$CODEX_APPROVAL")
    else
      echo "warning: $CODEX_BIN exec does not support --ask-for-approval; ignoring CODEX_APPROVAL=$CODEX_APPROVAL" >&2
    fi
  fi

  if [[ -n "$CODEX_MODEL" ]]; then
    codex_cmd+=(--model "$CODEX_MODEL")
  fi

  if [[ -n "$CODEX_PROFILE" ]]; then
    codex_cmd+=(--profile "$CODEX_PROFILE")
  fi

  codex_cmd+=(-)

  {
    printf 'You are running the paper-question-parser workflow under Codex CLI.\n'
    printf 'Treat the ARGUMENTS value below exactly as the skill-specific $ARGUMENTS input.\n'
    printf 'Execute the skill contract end-to-end, including required local persistence.\n'
    printf 'Do not ask follow-up questions; if the input cannot be processed, emit the skill-defined failure JSON.\n\n'
    printf '<skill_content name="paper-question-parser">\n'
    cat "$PAPER_QUESTION_PARSER_SKILL"
    printf '\n</skill_content>\n\n'
    printf 'ARGUMENTS:\n%s\n' "$source_url"
  } | "${codex_cmd[@]}"
}

rows_seen=0
skipped_existing=0
runs_started=0

while IFS=$'\t' read -r line_number source title source_url; do
  [[ -z "$source_url" ]] && continue
  rows_seen=$((rows_seen + 1))

  if [[ -n "$MAX_ROWS" && "$rows_seen" -gt "$MAX_ROWS" ]]; then
    rows_seen=$((rows_seen - 1))
    echo "max rows reached: $MAX_ROWS" >&2
    break
  fi

  if has_completed_source_url "$source_url"; then
    skipped_existing=$((skipped_existing + 1))
    echo "skipping completed line $line_number: $source | $title | $source_url" >&2
    continue
  fi

  if [[ -n "$MAX_RUNS" && "$runs_started" -ge "$MAX_RUNS" ]]; then
    echo "max runs reached: $MAX_RUNS" >&2
    break
  fi

  echo "running line $line_number: $source | $title | $source_url" >&2
  runs_started=$((runs_started + 1))

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "dry-run: would run codex for line $line_number: $source_url" >&2
    continue
  fi

  if ! run_paper_question_parser_with_codex "$source_url" </dev/null; then
    echo "error occurred: $source | $title | $source_url" >> "$ERROR_LOG_FILE"
    continue
  fi
done < <(
  python3 - "$OPEN_PROBLEMS_CSV_FILE" <<'PY'
import csv
import signal
import sys
from pathlib import Path

signal.signal(signal.SIGPIPE, signal.SIG_DFL)

csv_path = Path(sys.argv[1])

with csv_path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames or []
    missing = [name for name in ("source", "title", "url") if name not in fieldnames]
    if missing:
        raise SystemExit(f"Missing required CSV columns: {', '.join(missing)}")

    for line_number, row in enumerate(reader, start=2):
        source = (row.get("source") or "").strip().replace("\t", " ").replace("\n", " ")
        title = (row.get("title") or "").strip().replace("\t", " ").replace("\n", " ")
        url = (row.get("url") or "").strip()
        if not url:
            continue
        print(f"{line_number}\t{source}\t{title}\t{url}")
PY
)

echo "summary: rows_seen=$rows_seen skipped_existing=$skipped_existing runs_started=$runs_started dry_run=$DRY_RUN" >&2
