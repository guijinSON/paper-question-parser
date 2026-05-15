#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    slug = re.sub(r"[^a-z0-9._-]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "item"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy outputs/google_problems JSON files into parse-paper-compatible "
            "JSON files under outputs/parse-paper."
        ),
    )
    parser.add_argument("--input-dir", type=Path, default=Path("outputs/google_problems"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/parse-paper"))
    parser.add_argument("--prefix", default="google__")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def valid_accepted_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    accepted = payload.get("accepted")
    if not isinstance(accepted, list):
        return []

    valid: list[dict[str, Any]] = []
    for item in accepted:
        if not isinstance(item, dict):
            continue
        if not str(item.get("question_text") or "").strip():
            continue
        valid.append(item)
    return valid


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped_existing = 0
    skipped_invalid = 0
    question_count = 0

    for source_path in sorted(args.input_dir.glob("*.json")):
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception:
            skipped_invalid += 1
            continue

        if not isinstance(payload, dict):
            skipped_invalid += 1
            continue

        accepted = valid_accepted_questions(payload)
        if not accepted:
            skipped_invalid += 1
            continue

        converted_payload = {
            "source": payload.get("source") if isinstance(payload.get("source"), dict) else {},
            "accepted": accepted,
            "needs_review": payload.get("needs_review") if isinstance(payload.get("needs_review"), list) else [],
            "trace": payload.get("trace") if isinstance(payload.get("trace"), list) else [],
            "conversion": {
                "from": str(source_path),
                "kind": "google_problems_to_parse_paper",
            },
        }

        target_name = f"{args.prefix}{slugify(source_path.stem)}.json"
        target_path = args.output_dir / target_name
        if target_path.exists() and not args.overwrite:
            skipped_existing += 1
            continue

        target_path.write_text(
            json.dumps(converted_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        converted += 1
        question_count += len(accepted)

    print(
        f"converted_files={converted} questions={question_count} "
        f"skipped_existing={skipped_existing} skipped_invalid={skipped_invalid}"
    )


if __name__ == "__main__":
    main()
