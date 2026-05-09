#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

from build_self_contained_problem_csv import CSV_FIELDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge sharded self-contained math problem CSV files into one deduplicated CSV.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Shard CSV files to merge.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/self-contained-math-problems.merged.csv"),
        help="Merged CSV path.",
    )
    parser.add_argument(
        "--duplicate-policy",
        choices=["first", "last", "error"],
        default="first",
        help="How to handle duplicate question rows.",
    )
    return parser.parse_args()


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    question_hash = hashlib.sha1(row.get("original_question", "").encode("utf-8")).hexdigest()
    return (
        row.get("source_json", ""),
        row.get("question_id", ""),
        question_hash,
    )


def sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    try:
        global_index = int(row.get("global_index", ""))
    except ValueError:
        global_index = 10**18
    return (
        global_index,
        row.get("source_json", ""),
        row.get("question_id", ""),
    )


def main() -> None:
    args = parse_args()
    merged: dict[tuple[str, str, str], dict[str, str]] = {}
    source_by_key: dict[tuple[str, str, str], Path] = {}
    duplicate_count = 0

    for input_csv in args.inputs:
        if not input_csv.exists():
            raise SystemExit(f"Input CSV not found: {input_csv}")

        with input_csv.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing_fields = [field for field in CSV_FIELDS if field not in (reader.fieldnames or [])]
            if missing_fields:
                raise SystemExit(f"{input_csv} missing fields: {', '.join(missing_fields)}")

            for raw_row in reader:
                row = {field: raw_row.get(field, "") for field in CSV_FIELDS}
                key = row_key(row)
                if key in merged:
                    duplicate_count += 1
                    if args.duplicate_policy == "error":
                        raise SystemExit(
                            f"Duplicate row for {row.get('source_json')} {row.get('question_id')} "
                            f"in {input_csv}; first seen in {source_by_key[key]}"
                        )
                    if args.duplicate_policy == "last":
                        merged[key] = row
                        source_by_key[key] = input_csv
                else:
                    merged[key] = row
                    source_by_key[key] = input_csv

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(merged.values(), key=sort_key)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"merged_rows={len(rows)} duplicate_rows={duplicate_count} "
        f"output_csv={args.output_csv}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
