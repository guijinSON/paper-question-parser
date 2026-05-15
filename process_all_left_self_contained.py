#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from argparse import Namespace
from pathlib import Path

from build_self_contained_problem_csv import (
    QuestionRecord,
    append_csv_row,
    checkpoint_path,
    csv_row,
    existing_checkpoint_path,
    load_question_records,
    log_error,
    run_claude,
    validate_artifact,
    write_checkpoint,
)


DEFAULT_OUTPUT_CSV = Path("outputs/shards/self-contained-math-problems.leftover.csv")
DEFAULT_CHECKPOINT_DIR = Path("outputs/self-contained-leftover-checkpoints")
DEFAULT_ERROR_LOG = Path("logs/self-contained-problem-errors.leftover.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequentially process all self-contained questions missing from existing CSV outputs.",
    )
    parser.add_argument("--input-dir", type=Path, default=Path("outputs/parse-paper"))
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--error-log", type=Path, default=DEFAULT_ERROR_LOG)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def build_runtime_args(args: argparse.Namespace) -> Namespace:
    return Namespace(
        claude_bin=os.environ.get("CLAUDE_BIN", "claude"),
        model=os.environ.get("SELF_CONTAINED_MODEL", "opus"),
        effort=os.environ.get("SELF_CONTAINED_EFFORT", "medium"),
        tools=os.environ.get("SELF_CONTAINED_TOOLS", "WebSearch,WebFetch"),
        permission_mode=os.environ.get("SELF_CONTAINED_PERMISSION_MODE", "auto"),
        timeout=int(os.environ.get("SELF_CONTAINED_TIMEOUT", "900")),
        retries=int(os.environ.get("SELF_CONTAINED_RETRIES", "0")),
        max_budget_usd=os.environ.get("SELF_CONTAINED_MAX_BUDGET_USD"),
        no_session_persistence=os.environ.get("SELF_CONTAINED_NO_SESSION_PERSISTENCE") == "1",
        fsync=os.environ.get("SELF_CONTAINED_FSYNC") == "1",
        output_csv=args.output_csv,
        checkpoint_dir=args.checkpoint_dir,
        error_log=args.error_log,
    )


def row_key_from_csv(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("source_json", ""),
        row.get("question_id", ""),
        hashlib.sha1(row.get("original_question", "").encode("utf-8")).hexdigest(),
    )


def row_key_from_record(record: QuestionRecord) -> tuple[str, str, str]:
    return (
        record.source_json.as_posix(),
        record.question_id,
        hashlib.sha1(record.original_question.encode("utf-8")).hexdigest(),
    )


def existing_self_contained_csvs(output_csv: Path) -> list[Path]:
    paths = sorted(
        [p for p in Path("outputs").glob("self-contained-math-problems*.csv")]
        + [p for p in Path("outputs/shards").glob("self-contained-math-problems*.csv")]
    )
    return [p for p in paths if p.suffix == ".csv" and p != output_csv]


def load_processed_keys(output_csv: Path) -> set[tuple[str, str, str]]:
    processed: set[tuple[str, str, str]] = set()
    for csv_path in existing_self_contained_csvs(output_csv):
        try:
            with csv_path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    processed.add(row_key_from_csv(row))
        except Exception:
            continue
    return processed


def select_leftover_records(args: argparse.Namespace) -> list[QuestionRecord]:
    if args.start_offset < 0:
        raise SystemExit("--start-offset must be non-negative")
    if args.limit is not None and args.limit < 0:
        raise SystemExit("--limit must be non-negative")

    processed = load_processed_keys(args.output_csv)
    records = load_question_records(args.input_dir, args.error_log, None)
    leftovers = [record for record in records if row_key_from_record(record) not in processed]
    total_leftovers = len(leftovers)
    leftovers = leftovers[args.start_offset :]
    if args.limit is not None:
        leftovers = leftovers[: args.limit]
    print(
        f"Found {len(records)} accepted questions, {len(processed)} existing processed keys, "
        f"{total_leftovers} total leftovers, {len(leftovers)} selected leftovers."
    )
    return leftovers


def main() -> None:
    cli_args = parse_args()
    runtime_args = build_runtime_args(cli_args)
    records = select_leftover_records(cli_args)

    processed = 0
    skipped = 0
    failed = 0
    for offset, record in enumerate(records, start=1):
        ckp_path = checkpoint_path(runtime_args.checkpoint_dir, record)
        label = f"[{offset}/{len(records)} idx={record.global_index} {record.paper_id} {record.question_id}]"

        if existing_checkpoint_path(runtime_args.checkpoint_dir, record) is not None:
            print(f"{label} skip checkpoint")
            skipped += 1
            continue

        print(f"{label} start")
        try:
            artifact, elapsed_s, raw_stdout = run_claude(record, runtime_args)
            warnings = validate_artifact(artifact)
            checkpoint_payload = {
                "record": {
                    "global_index": record.global_index,
                    "source_json": str(record.source_json),
                    "paper_id": record.paper_id,
                    "paper_title": record.paper_title,
                    "paper_link": record.paper_link,
                    "question_link": record.question_link,
                    "question_id": record.question_id,
                    "parser_is_solved": record.parser_is_solved,
                    "context_brief": record.context_brief,
                    "original_question": record.original_question,
                    "evidence": record.evidence,
                },
                "artifact": artifact,
                "model": runtime_args.model,
                "effort": runtime_args.effort,
                "elapsed_s": round(elapsed_s, 2),
                "validation_warnings": warnings,
                "raw_claude_stdout": raw_stdout,
            }
            write_checkpoint(ckp_path, checkpoint_payload, runtime_args.fsync)
            row = csv_row(record, artifact, runtime_args, elapsed_s, ckp_path, warnings)
            append_csv_row(runtime_args.output_csv, row, runtime_args.fsync)
            print(f"{label} ok elapsed_s={elapsed_s:.1f} warnings={len(warnings)}")
            processed += 1
        except Exception as exc:
            failed += 1
            log_error(
                runtime_args.error_log,
                {
                    "event": "question_failed",
                    "global_index": record.global_index,
                    "source_json": str(record.source_json),
                    "paper_id": record.paper_id,
                    "question_id": record.question_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            print(f"{label} failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    print(
        f"Done. processed={processed} skipped={skipped} failed={failed} "
        f"csv={runtime_args.output_csv} checkpoints={runtime_args.checkpoint_dir}"
    )


if __name__ == "__main__":
    main()
