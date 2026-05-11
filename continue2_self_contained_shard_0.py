#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


SHARD_COUNT = 2
SHARD_INDEX = 0
MERGED_CSV = Path("outputs/self-contained-math-problems.merged.csv")
CHECKPOINT_DIR = Path("outputs/self-contained-continue2-checkpoints")
OUTPUT_CSV = Path("outputs/shards/self-contained-math-problems.continue2-shard-0-of-2.csv")
ERROR_LOG = Path("logs/self-contained-problem-errors.continue2-shard-0.jsonl")


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    slug = re.sub(r"[^a-z0-9._-]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "item"


def build_merged_checkpoint_markers() -> int:
    if not MERGED_CSV.exists():
        raise SystemExit(f"Merged CSV not found: {MERGED_CSV}")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    with MERGED_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            digest_input = f"{row['source_json']}|{row['question_id']}|{row['original_question']}"
            digest = hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:12]
            paper_slug = slugify(row["paper_id"].replace("/", "-"))
            question_slug = slugify(row["question_id"])
            marker = CHECKPOINT_DIR / (
                f"{int(row['global_index']):06d}__{paper_slug}__{question_slug}__{digest}.json"
            )
            if not marker.exists():
                marker.write_text(
                    json.dumps({"merged_csv_done_marker": True}, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            count += 1
    return count


def main() -> None:
    marker_count = build_merged_checkpoint_markers()
    print(f"Prepared {marker_count} merged-row checkpoint markers in {CHECKPOINT_DIR}")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3",
        "-u",
        "build_self_contained_problem_csv.py",
        "--shard-count",
        str(SHARD_COUNT),
        "--shard-index",
        str(SHARD_INDEX),
        "--output-csv",
        str(OUTPUT_CSV),
        "--checkpoint-dir",
        str(CHECKPOINT_DIR),
        "--error-log",
        str(ERROR_LOG),
        "--timeout",
        os.environ.get("SELF_CONTAINED_TIMEOUT", "900"),
        "--retries",
        os.environ.get("SELF_CONTAINED_RETRIES", "0"),
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
