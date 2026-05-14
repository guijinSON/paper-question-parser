#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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
    log_error,
    run_claude,
    validate_artifact,
    write_checkpoint,
)


DEFAULT_MANIFEST = Path("outputs/unprocessed-self-contained-questions-20260514.jsonl")
DEFAULT_OUTPUT_CSV = Path("outputs/shards/self-contained-math-problems.unprocessed-20260514.csv")
DEFAULT_CHECKPOINT_DIR = Path("outputs/self-contained-unprocessed-20260514-checkpoints")
DEFAULT_ERROR_LOG = Path("logs/self-contained-problem-errors.unprocessed-20260514.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process a frozen manifest of unprocessed self-contained problem records sequentially.",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--error-log", type=Path, default=DEFAULT_ERROR_LOG)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-offset", type=int, default=0)
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


def manifest_item_to_record(item: dict) -> QuestionRecord:
    return QuestionRecord(
        global_index=int(item["global_index"]),
        source_json=Path(item["source_json"]),
        paper_id=str(item["paper_id"]),
        paper_title=str(item["paper_title"]),
        paper_link=str(item["paper_link"]),
        question_link=str(item["question_link"]),
        question_id=str(item["question_id"]),
        parser_is_solved=str(item["parser_is_solved"]),
        context_brief=str(item["context_brief"]),
        original_question=str(item["original_question"]),
        evidence=item.get("evidence") if isinstance(item.get("evidence"), list) else [],
    )


def load_records(manifest: Path, start_offset: int, limit: int | None) -> list[QuestionRecord]:
    if not manifest.exists():
        raise SystemExit(f"Manifest not found: {manifest}")
    if start_offset < 0:
        raise SystemExit("--start-offset must be non-negative")
    if limit is not None and limit < 0:
        raise SystemExit("--limit must be non-negative")

    records: list[QuestionRecord] = []
    with manifest.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle):
            if line_number < start_offset or not line.strip():
                continue
            records.append(manifest_item_to_record(json.loads(line)))
            if limit is not None and len(records) >= limit:
                break
    return records


def main() -> None:
    cli_args = parse_args()
    runtime_args = build_runtime_args(cli_args)
    records = load_records(cli_args.manifest, cli_args.start_offset, cli_args.limit)
    print(f"Loaded {len(records)} frozen unprocessed questions from {cli_args.manifest}.")

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
