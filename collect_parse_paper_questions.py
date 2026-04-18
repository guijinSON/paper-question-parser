#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect accepted question_text entries from outputs/parse-paper JSON files "
            "and report aggregate statistics."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("outputs/parse-paper"),
        help="Directory containing parse-paper JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/parse-paper-questions.json"),
        help="Output JSON file for collected accepted questions.",
    )
    parser.add_argument(
        "--stats-output",
        type=Path,
        default=Path("outputs/parse-paper-questions.stats.json"),
        help="Output JSON file for aggregate statistics.",
    )
    return parser.parse_args()


def load_json(file_path: Path) -> dict:
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def summarize_lengths(texts: list[str]) -> dict:
    if not texts:
        return {
            "min_characters": 0,
            "max_characters": 0,
            "mean_characters": 0,
            "median_characters": 0,
            "min_words": 0,
            "max_words": 0,
            "mean_words": 0,
            "median_words": 0,
        }

    char_lengths = [len(text) for text in texts]
    word_lengths = [len(text.split()) for text in texts]
    return {
        "min_characters": min(char_lengths),
        "max_characters": max(char_lengths),
        "mean_characters": round(mean(char_lengths), 2),
        "median_characters": median(char_lengths),
        "min_words": min(word_lengths),
        "max_words": max(word_lengths),
        "mean_words": round(mean(word_lengths), 2),
        "median_words": median(word_lengths),
    }


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir
    output_path = args.output
    stats_output_path = args.stats_output

    if not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in: {input_dir}")

    collected_questions: list[dict] = []
    files_with_accepted_questions = 0
    files_with_needs_review = 0
    files_with_zero_accepted = 0
    accepted_count_by_file: dict[str, int] = {}
    needs_review_count_by_file: dict[str, int] = {}
    solved_counter: Counter[str] = Counter()
    invalid_files: list[dict[str, str]] = []

    for file_path in json_files:
        try:
            payload = load_json(file_path)
        except json.JSONDecodeError as error:
            invalid_files.append({"file": file_path.name, "reason": f"invalid_json: {error.msg}"})
            continue

        accepted_items = payload.get("accepted")
        needs_review_items = payload.get("needs_review")
        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}

        if not isinstance(accepted_items, list):
            invalid_files.append({"file": file_path.name, "reason": "missing_or_invalid_accepted_array"})
            continue

        if not isinstance(needs_review_items, list):
            invalid_files.append({"file": file_path.name, "reason": "missing_or_invalid_needs_review_array"})
            continue

        arxiv_id = file_path.stem
        source_title = source.get("title")
        source_url = source.get("url")
        accepted_count_by_file[file_path.name] = len(accepted_items)
        needs_review_count_by_file[file_path.name] = len(needs_review_items)

        if accepted_items:
            files_with_accepted_questions += 1
        else:
            files_with_zero_accepted += 1

        if needs_review_items:
            files_with_needs_review += 1

        for item in accepted_items:
            question_text = item.get("question_text")
            if not isinstance(question_text, str) or not question_text.strip():
                invalid_files.append(
                    {"file": file_path.name, "reason": f"accepted_item_missing_question_text:{item.get('id', 'unknown')}"}
                )
                continue

            is_solved = bool(item.get("meta", {}).get("is_solved", False))
            solved_counter["solved" if is_solved else "open"] += 1

            collected_questions.append(
                {
                    "arxiv_id": arxiv_id,
                    "source_file": file_path.name,
                    "source_title": source_title,
                    "source_url": source_url,
                    "question_id": item.get("id"),
                    "question_text": question_text,
                    "context_brief": item.get("context_brief"),
                    "is_solved": is_solved,
                }
            )

    question_texts = [item["question_text"] for item in collected_questions]
    per_file_counts = list(accepted_count_by_file.values())
    files_without_questions = [name for name, count in accepted_count_by_file.items() if count == 0]
    top_files = sorted(
        accepted_count_by_file.items(),
        key=lambda entry: (-entry[1], entry[0]),
    )[:10]

    stats = {
        "input_directory": str(input_dir),
        "total_files_seen": len(json_files),
        "valid_files": len(accepted_count_by_file),
        "invalid_files": invalid_files,
        "files_with_accepted_questions": files_with_accepted_questions,
        "files_with_zero_accepted": files_with_zero_accepted,
        "files_with_needs_review": files_with_needs_review,
        "total_collected_questions": len(collected_questions),
        "question_status_counts": {
            "open": solved_counter["open"],
            "solved": solved_counter["solved"],
        },
        "accepted_questions_per_file": {
            "min": min(per_file_counts) if per_file_counts else 0,
            "max": max(per_file_counts) if per_file_counts else 0,
            "mean": round(mean(per_file_counts), 2) if per_file_counts else 0,
            "median": median(per_file_counts) if per_file_counts else 0,
        },
        "question_text_lengths": summarize_lengths(question_texts),
        "top_files_by_accepted_questions": [
            {"source_file": file_name, "arxiv_id": Path(file_name).stem, "accepted_questions": count}
            for file_name, count in top_files
        ],
        "files_without_accepted_questions": files_without_questions,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    stats_output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(collected_questions, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    with stats_output_path.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Collected {len(collected_questions)} accepted questions from {len(accepted_count_by_file)} files.")
    print(f"Files with accepted questions: {files_with_accepted_questions}")
    print(f"Files with zero accepted questions: {files_with_zero_accepted}")
    print(f"Files with needs_review entries: {files_with_needs_review}")
    print(f"Open questions: {solved_counter['open']}")
    print(f"Solved questions: {solved_counter['solved']}")
    print(f"Wrote collected questions to {output_path}")
    print(f"Wrote stats to {stats_output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
