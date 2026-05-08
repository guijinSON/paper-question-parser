#!/usr/bin/env bash
set -euo pipefail

INPUT_JSON="outputs/parse-paper-questions.json"
OPENCODE_AGENT="${OPENCODE_AGENT:-Sisyphus (Ultraworker)}"
OPENCODE_BIN="${OPENCODE_BIN:-opencode}"
START_INDEX=""
END_INDEX=""
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: ./run_refiner.sh --start-index <start> --end-index <end> [--dry-run]

Reads outputs/parse-paper-questions.json and runs /paper-question-refiner for
items in the half-open range [start, end).

Skip behavior:
- skips items with an existing success marker in logs/refiner-runner/checkpoints/
- also skips when the current outputs/runs/<arxiv>--context-only.json exactly
  matches the same arXiv ID + question text and is a successful artifact

Examples:
  ./run_refiner.sh --start-index 0 --end-index 500
  ./run_refiner.sh --start-index 500 --end-index 1000
  ./run_refiner.sh --start-index 1000 --end-index 1500
  ./run_refiner.sh --start-index 0 --end-index 10 --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-index)
      START_INDEX="${2:-}"
      shift 2
      ;;
    --end-index)
      END_INDEX="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$START_INDEX" || -z "$END_INDEX" ]]; then
  echo "Both --start-index and --end-index are required." >&2
  usage >&2
  exit 1
fi

if ! [[ "$START_INDEX" =~ ^[0-9]+$ && "$END_INDEX" =~ ^[0-9]+$ ]]; then
  echo "start/end indexes must be non-negative integers." >&2
  exit 1
fi

if [[ ! -f "$INPUT_JSON" ]]; then
  echo "Missing input JSON: $INPUT_JSON" >&2
  exit 1
fi

TOTAL_COUNT="$(python3 - <<'PY' "$INPUT_JSON"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding='utf-8'))
if not isinstance(data, list):
    raise SystemExit('Input JSON must be a top-level array.')
print(len(data))
PY
)"

if (( START_INDEX >= END_INDEX )); then
  echo "Require start-index < end-index." >&2
  exit 1
fi

if (( END_INDEX > TOTAL_COUNT )); then
  echo "end-index ${END_INDEX} exceeds dataset size ${TOTAL_COUNT}." >&2
  exit 1
fi

RANGE_LABEL="${START_INDEX}-${END_INDEX}"
LOG_ROOT="logs/refiner-runner"
CHECKPOINT_DIR="${LOG_ROOT}/checkpoints"
RUN_LOG_DIR="${LOG_ROOT}/runs"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
ERROR_LOG_FILE="${RUN_LOG_DIR}/error_refiner_${RANGE_LABEL}_${TIMESTAMP}.log"
SUMMARY_LOG_FILE="${RUN_LOG_DIR}/summary_refiner_${RANGE_LABEL}_${TIMESTAMP}.log"

mkdir -p "$CHECKPOINT_DIR" "$RUN_LOG_DIR"

processed=0
skipped=0
succeeded=0
failed=0
would_run=0

echo "Running refiner for range [${START_INDEX}, ${END_INDEX}) out of ${TOTAL_COUNT} questions."
echo "Checkpoints: ${CHECKPOINT_DIR}"
echo "Errors: ${ERROR_LOG_FILE}"

_items_tmp=$(mktemp)
python3 - "$INPUT_JSON" "$START_INDEX" "$END_INDEX" > "$_items_tmp" <<'PY'
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
start = int(sys.argv[2])
end = int(sys.argv[3])
data = json.loads(path.read_text(encoding='utf-8'))

def slugify(value: str) -> str:
    lowered = value.lower()
    slug = re.sub(r'[^a-z0-9._-]+', '-', lowered)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or 'item'

for index in range(start, end):
    item = data[index]
    arxiv_id = item['arxiv_id']
    question_id = item.get('question_id') or f'q_{index:05d}'
    question_text = item['question_text']
    marker_name = f"{index:05d}__{slugify(arxiv_id)}__{slugify(question_id)}"
    print(json.dumps({
        'index': index,
        'arxiv_id': arxiv_id,
        'question_id': question_id,
        'question_text': question_text,
        'marker_name': marker_name,
        'payload': json.dumps({
            'question': question_text,
            'arxiv_id': arxiv_id,
        }, ensure_ascii=False),
    }, ensure_ascii=False))
PY

while IFS= read -r item_record; do
  [[ -z "$item_record" ]] && continue
  _fields_tmp=$(mktemp)
  python3 - "$item_record" > "$_fields_tmp" <<'PY'
import json
import sys

record = json.loads(sys.argv[1])
print(record['index'])
print(record['arxiv_id'])
print(record['question_id'])
print(record['marker_name'])
print(record['payload'])
PY
  item_fields=()
  while IFS= read -r _line; do
    item_fields+=("$_line")
  done < "$_fields_tmp"
  rm -f "$_fields_tmp"

  item_index="${item_fields[0]}"
  arxiv_id="${item_fields[1]}"
  question_id="${item_fields[2]}"
  marker_name="${item_fields[3]}"
  payload="${item_fields[4]}"

  processed=$((processed + 1))
  checkpoint_file="${CHECKPOINT_DIR}/${marker_name}.done"

  if [[ -s "$checkpoint_file" ]]; then
    echo "[skip checkpoint] idx=${item_index} arxiv=${arxiv_id} qid=${question_id}"
    skipped=$((skipped + 1))
    continue
  fi

  if python3 - <<'PY' "$item_record"
import json
import sys
from pathlib import Path

def sanitize_arxiv_id(value: str) -> str:
    return value.replace('/', '-').replace('_', '-').strip()

record = json.loads(sys.argv[1])
arxiv_id = record['arxiv_id']
question_text = record['question_text']
run_path = Path('outputs/runs') / f"{sanitize_arxiv_id(arxiv_id)}--context-only.json"

if not run_path.exists():
    raise SystemExit(1)

try:
    payload = json.loads(run_path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(1)

if isinstance(payload, list):
    if not payload:
        raise SystemExit(1)
    payload = payload[0]

if not isinstance(payload, dict):
    raise SystemExit(1)

input_block = payload.get('input', {})
persist = payload.get('persist', {})
verdict = payload.get('verdict', {})

ok = (
    input_block.get('arxiv_id') == arxiv_id and
    input_block.get('question') == question_text and
    payload.get('rewrite_kind') == 'context_only' and
    persist.get('saved') is True and
    verdict.get('status') != 'error'
)

raise SystemExit(0 if ok else 1)
PY
  then
    printf 'matched_existing_run\t%s\t%s\t%s\n' "$item_index" "$arxiv_id" "$question_id" > "$checkpoint_file"
    echo "[skip existing output] idx=${item_index} arxiv=${arxiv_id} qid=${question_id}"
    skipped=$((skipped + 1))
    continue
  fi

  echo "[run] idx=${item_index} arxiv=${arxiv_id} qid=${question_id}"

  if (( DRY_RUN == 1 )); then
    printf '[dry-run] %s\t%s\t%s\t%s\n' "$item_index" "$arxiv_id" "$question_id" "$payload"
    would_run=$((would_run + 1))
    continue
  fi

  if "$OPENCODE_BIN" run --agent "$OPENCODE_AGENT" "/paper-question-refiner $payload" </dev/null; then
    printf 'success\t%s\t%s\t%s\n' "$item_index" "$arxiv_id" "$question_id" > "$checkpoint_file"
    succeeded=$((succeeded + 1))
  else
    printf 'error occurred\tidx=%s\tarxiv=%s\tqid=%s\tpayload=%s\n' "$item_index" "$arxiv_id" "$question_id" "$payload" >> "$ERROR_LOG_FILE"
    failed=$((failed + 1))
    continue
  fi
done < "$_items_tmp"
rm -f "$_items_tmp"

{
  echo "range=${RANGE_LABEL}"
  echo "processed=${processed}"
  echo "skipped=${skipped}"
  echo "succeeded=${succeeded}"
  echo "failed=${failed}"
  echo "would_run=${would_run}"
  echo "dry_run=${DRY_RUN}"
} | tee "$SUMMARY_LOG_FILE"

if (( failed > 0 )); then
  echo "Some items failed. See ${ERROR_LOG_FILE}" >&2
fi
