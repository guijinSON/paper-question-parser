#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

TMUX_BIN="${TMUX_BIN:-/opt/homebrew/bin/tmux}"
SHARDS="${SHARDS:-2}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/shards}"
CHECKPOINT_ROOT="${CHECKPOINT_ROOT:-outputs/shards/checkpoints}"
TIMEOUT="${TIMEOUT:-900}"
RETRIES="${RETRIES:-0}"

mkdir -p logs "$OUTPUT_DIR" "$CHECKPOINT_ROOT"

for shard_index in $(seq 0 "$((SHARDS - 1))"); do
    session="self_contained_problem_shard_${shard_index}"
    output_csv="$OUTPUT_DIR/self-contained-math-problems.shard-${shard_index}-of-${SHARDS}.csv"
    checkpoint_dir="$CHECKPOINT_ROOT/shard-${shard_index}-of-${SHARDS}"
    error_log="logs/self-contained-problem-errors.shard-${shard_index}.jsonl"
    run_log="logs/self-contained-problem-run.shard-${shard_index}.log"

    if "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
        echo "$session already running"
        continue
    fi

    "$TMUX_BIN" new-session -d -s "$session" \
        "cd '$PWD' && python3 -u build_self_contained_problem_csv.py --shard-count '$SHARDS' --shard-index '$shard_index' --output-csv '$output_csv' --checkpoint-dir '$checkpoint_dir' --error-log '$error_log' --timeout '$TIMEOUT' --retries '$RETRIES' >> '$run_log' 2>&1"
    echo "started $session"
done

"$TMUX_BIN" ls | grep self_contained_problem_shard || true
