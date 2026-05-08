#!/usr/bin/env bash
set -euo pipefail

# Run this script from the project root.
# Reads arXiv links from the last column of the filtered CSV.
PAPERS_CSV_FILE="${PAPERS_CSV_FILE:-arxiv-op-papers-validated.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/parse-paper}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"

CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_MODEL="${CODEX_MODEL:-}"
CODEX_PROFILE="${CODEX_PROFILE:-}"
CODEX_SANDBOX="${CODEX_SANDBOX:-workspace-write}"
CODEX_APPROVAL="${CODEX_APPROVAL:-never}"
CODEX_SEARCH="${CODEX_SEARCH:-1}"
PAPER_QUESTION_PARSER_SKILL="${PAPER_QUESTION_PARSER_SKILL:-.opencode/skills/paper-question-parser/SKILL.md}"

ERROR_LOG_DIR="logs"
ERROR_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="$ERROR_LOG_DIR/error_${ERROR_TIMESTAMP}.log"

if [[ ! -f "$PAPERS_CSV_FILE" ]]; then
  echo "Missing papers CSV file: $PAPERS_CSV_FILE" >&2
  exit 1
fi

if [[ ! -f "$PAPER_QUESTION_PARSER_SKILL" ]]; then
  echo "Missing paper-question-parser skill file: $PAPER_QUESTION_PARSER_SKILL" >&2
  exit 1
fi

mkdir -p "$ERROR_LOG_DIR" "$OUTPUT_DIR"

extract_arxiv_output_file() {
  local arxiv_link="$1"
  local normalized_link=
  local arxiv_id=

  normalized_link="${arxiv_link%%#*}"
  normalized_link="${normalized_link%%\?*}"
  normalized_link="${normalized_link%/}"

  if [[ "$normalized_link" =~ ^https?://arxiv\.org/(abs|pdf)/(.+)$ ]]; then
    arxiv_id="${BASH_REMATCH[2]}"
    arxiv_id="${arxiv_id%.pdf}"
    arxiv_id="${arxiv_id//\//_}"
    printf '%s/%s.json\n' "$OUTPUT_DIR" "$arxiv_id"
    return 0
  fi

  return 1
}

has_valid_output_checkpoint() {
  local output_file="$1"

  [[ -s "$output_file" ]] || return 1

  python3 - "$output_file" <<'PY'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])

try:
    with output_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    raise SystemExit(1)

required_keys = {"accepted", "needs_review", "trace"}
raise SystemExit(0 if isinstance(payload, dict) and required_keys.issubset(payload) else 1)
PY
}

run_paper_question_parser_with_codex() {
  local source_url="$1"
  local -a codex_cmd=("$CODEX_BIN")

  if [[ "$CODEX_SEARCH" != "0" ]]; then
    codex_cmd+=(--search)
  fi

  codex_cmd+=(exec --cd "$PWD" --sandbox "$CODEX_SANDBOX" --ask-for-approval "$CODEX_APPROVAL")

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

exec 3< "$PAPERS_CSV_FILE"
read -r _ <&3 || true
line_number=1
while IFS= read -r csv_row <&3 || [[ -n "$csv_row" ]]; do
  line_number=$((line_number + 1))
  csv_row="${csv_row%$'\r'}"
  arxiv_link="${csv_row##*,}"
  [[ -z "$arxiv_link" ]] && continue
  output_file=""
  if output_file="$(extract_arxiv_output_file "$arxiv_link")"; then
    if [[ "$SKIP_EXISTING" == "1" ]] && has_valid_output_checkpoint "$output_file"; then
      echo "skipping completed line $line_number: $arxiv_link" >&2
      continue
    fi
  else
    output_file=""
  fi

  echo "running line $line_number: $arxiv_link" >&2
  if ! run_paper_question_parser_with_codex "$arxiv_link" 3<&- </dev/null; then
    if [[ -n "$output_file" ]]; then
      echo "error occurred: line $line_number: $arxiv_link -> $output_file" >> "$ERROR_LOG_FILE"
    else
      echo "error occurred: line $line_number: $arxiv_link" >> "$ERROR_LOG_FILE"
    fi
    continue
  fi
done
exec 3<&-
