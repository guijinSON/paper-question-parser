#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from trace_error_truncator import call_codex_first_error_truncation


DEFAULT_INPUT = Path(
    "reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("outputs/trace_behavior_inserter_qwen3_30b_filtered")


def safe_part(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return text or "unknown"


def output_path_for_row(row: dict[str, Any], output_dir: Path) -> Path:
    source_row_index = safe_part(row.get("source_row_index", "missing_source_row"))
    completion_index = safe_part(row.get("completion_index", "missing_completion"))
    return output_dir / f"source_row_{source_row_index}__completion_{completion_index}.json"


def jsonable(value: Any) -> Any:
    if not isinstance(value, (dict, list, tuple)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def compact_row_metadata(row: dict[str, Any]) -> dict[str, Any]:
    keep = [
        "created_at",
        "model",
        "source_row_index",
        "sample_index",
        "completion_index",
        "completion_count",
        "thinking_parse_status",
        "finish_reason",
        "prompt_tokens",
        "generated_tokens",
        "sampling",
        "source",
    ]
    return {key: jsonable(row.get(key)) for key in keep if key in row}


def make_base_state(row: dict[str, Any], *, input_path: Path) -> dict[str, Any]:
    prompt = str(row.get("question") or row.get("formatted_prompt") or "")
    reasoning = str(row.get("reasoning") or "")
    answer = str(row.get("answer") or "")

    return {
        "prompt": prompt,
        "max_length": 32768,
        "min_reasoning_tokens": 4096,
        "min_continuation_tokens": 512,
        "continuation_max_tokens": 1024,
        "status": "initialized",
        "target_answer_shape": (
            "Rigorous final solution. If solved, give the strongest proof possible. "
            "If open/unsolved, rigorously summarize all attempted paths and exact "
            "failure points. Use idea_bank before bold_try; do not cap bold attempts "
            "at two while good hypotheses remain."
        ),
        "avoid_claims": [
            "Do not introduce unverified citations, author-date claims, named papers, theorem numbers, or claimed counterexamples.",
            "Do not describe developer instructions, token targets, JSON, loop mechanics, or hidden-control process in stored reasoning.",
            "Do not use artifact-meta phrasing in final_solution.",
        ],
        "fix_memory": [
            "For open problems, build an idea bank before committing to bold attempts.",
            "Final solution must either prove rigorously or identify failed paths and exact unresolved proof obligations.",
        ],
        "rounds": [],
        "interleaved_trace": [
            {
                "type": "original",
                "round": 0,
                "truncated": False,
                "text": reasoning,
            }
        ],
        "source_trace_truncated": False,
        "final_solution": "",
        "termination_summary": None,
        "row_metadata": compact_row_metadata(row),
        "input_jsonl": str(input_path),
        "raw_answer": answer,
    }


def apply_first_error_truncation(
    state: dict[str, Any],
    *,
    codex_bin: str,
    model: str,
    reasoning_effort: str | None,
    cwd: Path,
    sandbox: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    result = call_codex_first_error_truncation(
        state["interleaved_trace"][0]["text"],
        problem=state["prompt"],
        codex_bin=codex_bin,
        model=model,
        reasoning_effort=reasoning_effort,
        cwd=cwd,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
    )

    idx = result["first_error_segment_index"]
    if idx is None:
        state["status"] = "no_error_found"
        state["rounds"].append(
            {
                "round": 1,
                "behavior": "none",
                "trigger_segment_index": None,
                "trigger_summary": result["first_error_summary"],
                "inserted_segment": "",
            }
        )
        state["interleaved_trace"][0]["text"] = "\n\n".join(result["truncated_segments"])
        return state

    correction = result["cancellation_segment"]
    truncated_text = "\n\n".join(result["truncated_segments"])
    state["interleaved_trace"][0]["text"] = truncated_text
    state["interleaved_trace"][0]["truncated"] = True
    state["interleaved_trace"].append(
        {
            "type": "insertion",
            "round": 1,
            "behavior": "correction",
            "text": correction,
        }
    )
    state["rounds"].append(
        {
            "round": 1,
            "behavior": "correction",
            "trigger_segment_index": idx,
            "trigger_summary": result["first_error_summary"],
            "inserted_segment": correction,
            "not_do": result["first_error_summary"],
            "fix_summary": "Inserted first-error self-correction from batch truncation.",
            "cooldown_after_round": {"correction": 2},
        }
    )
    state["source_trace_truncated"] = True
    state["status"] = "first_error_corrected"
    state["cooldowns"] = {"correction": 2}
    state["avoid_claims"].append(result["first_error_summary"])
    state["fix_memory"].append("Inserted first-error self-correction from batch truncation.")
    return state


def iter_rows(path: Path, *, chunksize: int) -> tuple[int, dict[str, Any]]:
    offset = 0
    for chunk in pd.read_json(path, lines=True, chunksize=chunksize):
        records = chunk.to_dict("records")
        for record in records:
            yield offset, record
            offset += 1


def count_jsonl_rows(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def shard_bounds(total_rows: int, *, num_shards: int, shard_index: int) -> tuple[int, int]:
    if num_shards < 1:
        raise ValueError("--num-shards must be at least 1")
    if shard_index < 0 or shard_index >= num_shards:
        raise ValueError("--shard-index must satisfy 0 <= shard_index < --num-shards")

    base = total_rows // num_shards
    extra = total_rows % num_shards
    start = shard_index * base + min(shard_index, extra)
    end = start + base + (1 if shard_index < extra else 0)
    return start, end


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-create trace-behavior JSON artifacts from a reasoning JSONL dataset. "
            "Output filenames use source_row_index and completion_index."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--mode",
        choices=["init", "first-error"],
        default="init",
        help=(
            "init only writes base consolidated JSON states. first-error also calls "
            "Codex via trace_error_truncator.py and inserts the first correction."
        ),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=int, default=0, help="Zero-based dataset row offset.")
    parser.add_argument(
        "--num-shards",
        type=int,
        default=None,
        help="Split the JSONL into this many contiguous row ranges.",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=None,
        help="Zero-based shard id to process. Requires --num-shards.",
    )
    parser.add_argument(
        "--print-shards",
        action="store_true",
        help="Print the row ranges for --num-shards and exit.",
    )
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if (args.num_shards is None) != (args.shard_index is None) and not args.print_shards:
        raise ValueError("--num-shards and --shard-index must be provided together")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    effective_start = args.start
    effective_end: int | None = None
    total_rows: int | None = None
    if args.num_shards is not None:
        total_rows = count_jsonl_rows(args.input)
        if args.print_shards:
            for idx in range(args.num_shards):
                start, end = shard_bounds(
                    total_rows,
                    num_shards=args.num_shards,
                    shard_index=idx,
                )
                print(
                    json.dumps(
                        {
                            "shard_index": idx,
                            "num_shards": args.num_shards,
                            "start": start,
                            "end": end,
                            "rows": end - start,
                        },
                        ensure_ascii=False,
                    )
                )
            return 0
        shard_start, shard_end = shard_bounds(
            total_rows,
            num_shards=args.num_shards,
            shard_index=args.shard_index,
        )
        effective_start = max(args.start, shard_start)
        effective_end = shard_end

    written = 0
    skipped = 0
    failed = 0
    seen = 0

    for offset, row in iter_rows(args.input, chunksize=args.chunksize):
        if offset < effective_start:
            continue
        if effective_end is not None and offset >= effective_end:
            break
        if args.limit is not None and seen >= args.limit:
            break
        seen += 1

        out_path = output_path_for_row(row, args.output_dir)
        if out_path.exists() and not args.overwrite:
            skipped += 1
            continue

        try:
            state = make_base_state(row, input_path=args.input)
            state["dataset_row_offset"] = offset
            if args.mode == "first-error":
                state = apply_first_error_truncation(
                    state,
                    codex_bin=args.codex_bin,
                    model=args.model,
                    reasoning_effort=args.reasoning_effort,
                    cwd=args.cwd,
                    sandbox=args.sandbox,
                    timeout_seconds=args.timeout_seconds,
                )
            out_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            written += 1
            print(f"wrote {out_path}", flush=True)
        except Exception as exc:
            failed += 1
            error_path = out_path.with_suffix(".error.json")
            payload = {
                "dataset_row_offset": offset,
                "source_row_index": jsonable(row.get("source_row_index")),
                "completion_index": jsonable(row.get("completion_index")),
                "error": str(exc),
            }
            error_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            print(f"failed {out_path}: {exc}", file=sys.stderr, flush=True)

    print(
        json.dumps(
            {
                "input": str(args.input),
                "output_dir": str(args.output_dir),
                "mode": args.mode,
                "total_rows": total_rows,
                "num_shards": args.num_shards,
                "shard_index": args.shard_index,
                "effective_start": effective_start,
                "effective_end": effective_end,
                "seen": seen,
                "written": written,
                "skipped": skipped,
                "failed": failed,
            },
            ensure_ascii=False,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
