#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from trace_error_truncator import (
    call_codex_first_error_truncation,
    extract_json_object,
    split_trace_segments,
)


DEFAULT_INPUT = Path(
    "reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("outputs/trace_behavior_inserter_qwen3_30b_filtered")
SKILL_DIR = Path("codex_skills/trace-behavior-inserter")
CONTINUE_SCRIPT = SKILL_DIR / "scripts/continue_reasoning_openrouter.py"


BEHAVIOR_INSERTION_PROMPT = """\
You are repairing one mathematical or technical reasoning trace.

Read the problem and the ordered trace segments. Choose the earliest point where
one natural trace behavior should be inserted to improve the future reasoning.

Allowed behaviors:
correction, counterexample_search, branch_split, answer_mode_switch,
dead_end_detection, lemma_decomposition, deep_trace_audit, idea_bank, bold_try,
none.

Rules:
- Return exactly one behavior insertion, not a final answer.
- The inserted segment must be first-person reasoning voice, as if the original
  reasoner paused and adjusted course.
- Existing insertion segments are already part of the repaired trace. Do not
  select an earlier segment if its problem is already directly addressed by a
  following insertion. Look for the earliest still-unrepaired issue or strategic
  need in the current trace.
- Do not mention tools, JSON, instructions, developer messages, token targets,
  generation process, or hidden control.
- For open problems, do not stop merely at "this is open"; prefer idea_bank
  before bold_try, and after dead ends pivot to materially different routes.
- Avoid unverified citations, author-date claims, theorem numbers, paper names,
  or claimed counterexamples.
- Truncate through and including the trigger segment.

Output only one JSON object:
{{
  "behavior": "correction | counterexample_search | branch_split | answer_mode_switch | dead_end_detection | lemma_decomposition | deep_trace_audit | idea_bank | bold_try | none",
  "trigger_segment_index": 0,
  "trigger_summary": "...",
  "truncated_segments": ["..."],
  "inserted_segment": "..."
}}

If no insertion is useful, use behavior "none", trigger_segment_index null,
truncated_segments as the full input segments, and inserted_segment "".

Problem:
{problem}

Trace segments:
{segments_json}
"""


FINAL_SOLUTION_PROMPT = """\
Write the final answer for the original problem using the repaired reasoning
trajectory below.

Requirements:
- If the problem is solved, give the most rigorous proof possible.
- If it is not solved or is open in the relevant generality, give a rigorous
  research-status answer: summarize the attempted proof/counterexample paths,
  explain exactly where each failed, and identify the remaining proof
  obligations.
- Do not use artifact-meta language such as "the trace", "the run",
  "the continuation", "the model", "the repaired reasoning", or "the JSON".
- Do not invent citations or named literature details.
- Answer in polished final-answer style.

Original problem:
{problem}

Repaired reasoning:
{reasoning}
"""


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


def state_reasoning_text(state: dict[str, Any]) -> str:
    return "\n\n".join(
        str(entry.get("text", "")).strip()
        for entry in state.get("interleaved_trace", [])
        if str(entry.get("text", "")).strip()
    )


def segment_interleaved_trace(
    state: dict[str, Any],
) -> tuple[list[str], list[tuple[int, int]]]:
    segments: list[str] = []
    mapping: list[tuple[int, int]] = []
    for entry_index, entry in enumerate(state.get("interleaved_trace", [])):
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        entry_segments = split_trace_segments(text)
        for local_index, segment in enumerate(entry_segments):
            segments.append(segment)
            mapping.append((entry_index, local_index))
    return segments, mapping


def truncate_interleaved_trace_at_segment(
    state: dict[str, Any],
    *,
    trigger_segment_index: int,
) -> list[dict[str, Any]]:
    segments, mapping = segment_interleaved_trace(state)
    if trigger_segment_index < 0 or trigger_segment_index >= len(mapping):
        raise ValueError("trigger_segment_index is out of range")

    trigger_entry_index, trigger_local_index = mapping[trigger_segment_index]
    kept_entries: list[dict[str, Any]] = []
    for entry_index, entry in enumerate(state.get("interleaved_trace", [])):
        if entry_index > trigger_entry_index:
            break
        copied = dict(entry)
        if entry_index == trigger_entry_index:
            entry_segments = split_trace_segments(str(entry.get("text", "")).strip())
            copied["text"] = "\n\n".join(entry_segments[: trigger_local_index + 1])
            copied["truncated"] = True
        kept_entries.append(copied)
    return kept_entries


def call_codex_json(
    prompt: str,
    *,
    codex_bin: str,
    model: str,
    reasoning_effort: str | None,
    cwd: Path,
    sandbox: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    cmd = [codex_bin, "exec", "--cd", str(cwd)]
    if sandbox:
        cmd.extend(["--sandbox", sandbox])
    if model:
        cmd.extend(["--model", model])
    if reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    cmd.append("-")
    completed = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "codex exec failed with exit code "
            f"{completed.returncode}\nSTDERR:\n{completed.stderr.strip()}"
        )
    return extract_json_object(completed.stdout)


def call_codex_text(
    prompt: str,
    *,
    codex_bin: str,
    model: str,
    reasoning_effort: str | None,
    cwd: Path,
    sandbox: str,
    timeout_seconds: int,
) -> str:
    cmd = [codex_bin, "exec", "--cd", str(cwd)]
    if sandbox:
        cmd.extend(["--sandbox", sandbox])
    if model:
        cmd.extend(["--model", model])
    if reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    cmd.append("-")
    completed = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "codex exec failed with exit code "
            f"{completed.returncode}\nSTDERR:\n{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def apply_behavior_insertion(
    state: dict[str, Any],
    *,
    round_number: int,
    codex_bin: str,
    model: str,
    reasoning_effort: str | None,
    cwd: Path,
    sandbox: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    segments, _mapping = segment_interleaved_trace(state)
    payload = call_codex_json(
        BEHAVIOR_INSERTION_PROMPT.format(
            problem=state["prompt"],
            segments_json=json.dumps(segments, ensure_ascii=False, indent=2),
        ),
        codex_bin=codex_bin,
        model=model,
        reasoning_effort=reasoning_effort,
        cwd=cwd,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
    )

    behavior = str(payload.get("behavior", "none")).strip()
    idx = payload.get("trigger_segment_index")
    if behavior == "none" or idx is None:
        state["rounds"].append(
            {
                "round": round_number,
                "behavior": "none",
                "trigger_segment_index": None,
                "trigger_summary": str(payload.get("trigger_summary", "")),
                "inserted_segment": "",
            }
        )
        return state
    if not isinstance(idx, int) or idx < 0 or idx >= len(segments):
        raise ValueError("behavior insertion returned invalid trigger_segment_index")

    inserted_segment = str(payload.get("inserted_segment", "")).strip()
    if not inserted_segment:
        raise ValueError("behavior insertion returned empty inserted_segment")

    state["interleaved_trace"] = truncate_interleaved_trace_at_segment(
        state,
        trigger_segment_index=idx,
    )
    state["interleaved_trace"].append(
        {
            "type": "insertion",
            "round": round_number,
            "behavior": behavior,
            "text": inserted_segment,
        }
    )
    state["source_trace_truncated"] = True
    state["status"] = "running"
    state["rounds"].append(
        {
            "round": round_number,
            "behavior": behavior,
            "trigger_segment_index": idx,
            "trigger_summary": str(payload.get("trigger_summary", "")),
            "inserted_segment": inserted_segment,
        }
    )
    if behavior == "correction":
        state.setdefault("avoid_claims", []).append(str(payload.get("trigger_summary", "")))
    state.setdefault("fix_memory", []).append(
        f"Round {round_number} inserted {behavior}: {payload.get('trigger_summary', '')}"
    )
    return state


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


def run_continuation(
    state_path: Path,
    *,
    args: argparse.Namespace,
) -> None:
    cmd = [
        sys.executable,
        str(CONTINUE_SCRIPT),
        "--state-json",
        str(state_path),
        "--model",
        args.continuation_model,
        "--provider",
        args.continuation_provider,
        "--max-tokens",
        str(args.continuation_tokens),
        "--temperature",
        str(args.continuation_temperature),
        "--retries",
        str(args.openrouter_retries),
    ]
    completed = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=args.openrouter_timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "continuation failed with exit code "
            f"{completed.returncode}\nSTDERR:\n{completed.stderr.strip()}\n"
            f"STDOUT:\n{completed.stdout.strip()}"
        )


def write_final_solution(
    state: dict[str, Any],
    *,
    codex_bin: str,
    model: str,
    reasoning_effort: str | None,
    cwd: Path,
    sandbox: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    final_solution = call_codex_text(
        FINAL_SOLUTION_PROMPT.format(
            problem=state["prompt"],
            reasoning=state_reasoning_text(state),
        ),
        codex_bin=codex_bin,
        model=model,
        reasoning_effort=reasoning_effort,
        cwd=cwd,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
    )
    state["final_solution"] = final_solution
    state["status"] = "solved"
    state["termination_summary"] = "full-loop completed with final_solution"
    return state


def apply_full_loop(
    state: dict[str, Any],
    *,
    out_path: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    state["status"] = "running"
    state["min_continuation_tokens"] = args.min_continuation_tokens
    state["continuation_max_tokens"] = args.continuation_tokens
    for round_number in range(1, args.full_loop_rounds + 1):
        if state.get("status") == "solved" or state.get("final_solution"):
            break
        state = apply_behavior_insertion(
            state,
            round_number=round_number,
            codex_bin=args.codex_bin,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            cwd=args.cwd,
            sandbox=args.sandbox,
            timeout_seconds=args.timeout_seconds,
        )
        out_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        run_continuation(out_path, args=args)
        state = json.loads(out_path.read_text(encoding="utf-8"))
        if state.get("status") == "solved" or state.get("final_solution"):
            return state

    state = write_final_solution(
        state,
        codex_bin=args.codex_bin,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        cwd=args.cwd,
        sandbox=args.sandbox,
        timeout_seconds=args.timeout_seconds,
    )
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
        choices=["init", "first-error", "full-loop"],
        default="init",
        help=(
            "init writes base consolidated JSON states. first-error calls Codex "
            "once and inserts the first correction. full-loop runs bounded "
            "behavior insertion, continuation, and final-solution generation."
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
    parser.add_argument("--full-loop-rounds", type=int, default=2)
    parser.add_argument("--continuation-model", default="openai/gpt-oss-120b")
    parser.add_argument("--continuation-provider", default="deepinfra/bf16")
    parser.add_argument("--continuation-tokens", type=int, default=1024)
    parser.add_argument("--continuation-temperature", type=float, default=1.0)
    parser.add_argument("--min-continuation-tokens", type=int, default=512)
    parser.add_argument("--openrouter-retries", type=int, default=3)
    parser.add_argument("--openrouter-timeout-seconds", type=int, default=300)
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
            elif args.mode == "full-loop":
                state = apply_full_loop(state, out_path=out_path, args=args)
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
