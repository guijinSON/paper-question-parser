#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate method overlap between a generated trajectory and descendant method metadata."
    )
    parser.add_argument("trajectory", type=Path, help="Path to trajectory markdown output.")
    parser.add_argument("descendants", type=Path, help="Path to descendant method metadata JSON.")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_method_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("<TOOL>SYNTHESIZE_DIRECTION | METHOD:"):
            body = line.split("METHOD:", 1)[1]
            method = body.split("|", 1)[0].strip()
            if method:
                candidates.append(method)
    return candidates


def confidence_for_ratio(ratio: float) -> str:
    if ratio >= 0.75:
        return "high"
    if ratio >= 0.25:
        return "medium"
    return "low"


def evaluate(trajectory_text: str, descendants_payload: dict) -> dict:
    candidates = extract_method_candidates(trajectory_text)
    lowered_candidates = [candidate.lower() for candidate in candidates]
    methods = descendants_payload.get("descendant_methods", [])
    matched_methods = []
    reasons = []

    for method in methods:
        phrases = method.get("match_phrases", [])
        matched_phrases = [phrase for phrase in phrases if any(phrase.lower() in candidate for candidate in lowered_candidates)]
        if matched_phrases:
            matched_methods.append(
                {
                    "method_id": method["method_id"],
                    "label": method["label"],
                    "matched_phrases": matched_phrases,
                }
            )

    ratio = (len(matched_methods) / len(methods)) if methods else 0.0
    if matched_methods:
        reasons.append("SYNTHESIZE_DIRECTION method text contains descendant method phrases.")
    else:
        reasons.append("No descendant method phrases were detected inside SYNTHESIZE_DIRECTION method text.")

    return {
        "schema_version": "1.0",
        "method_candidates": candidates,
        "matched_descendant_methods": matched_methods,
        "overlap_ratio": round(ratio, 3),
        "confidence": confidence_for_ratio(ratio),
        "reasons": reasons,
    }


def main() -> int:
    args = parse_args()
    trajectory_path = args.trajectory.resolve()
    descendants_path = args.descendants.resolve()

    if not trajectory_path.is_file():
        raise SystemExit(f"trajectory file not found: {trajectory_path}")
    if not descendants_path.is_file():
        raise SystemExit(f"descendants file not found: {descendants_path}")

    trajectory_text = trajectory_path.read_text(encoding="utf-8")
    descendants_payload = load_json(descendants_path)
    report = evaluate(trajectory_text, descendants_payload)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
