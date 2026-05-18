#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a structured termination summary when reasoning reaches max length.",
    )
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--reasoning-file", type=Path)
    parser.add_argument(
        "--state-json",
        type=Path,
        help=(
            "Consolidated trace-loop JSON. When provided, prompt and reasoning are "
            "read from the JSON, then status and termination_summary are written "
            "back into the same file."
        ),
    )
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--max-length", type=int, required=True)
    parser.add_argument("--current-length", type=int, required=True)
    return parser.parse_args()


def state_reasoning_text(state: dict) -> str:
    return "\n\n".join(
        str(entry.get("text", "")).strip()
        for entry in state.get("interleaved_trace", [])
        if str(entry.get("text", "")).strip()
    )


def rough_tail(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def rough_progress_summary(reasoning: str) -> str:
    paragraphs = [part.strip() for part in reasoning.split("\n\n") if part.strip()]
    if not paragraphs:
        return "No substantive reasoning was recorded before the threshold was reached."
    head = paragraphs[:3]
    tail = paragraphs[-3:] if len(paragraphs) > 3 else []
    pieces = []
    pieces.append("Early trajectory: " + " / ".join(p[:300] for p in head))
    if tail:
        pieces.append("Latest trajectory: " + " / ".join(p[:300] for p in tail))
    return "\n".join(pieces)


def main() -> int:
    args = parse_args()
    if args.state_json:
        state = json.loads(args.state_json.read_text(encoding="utf-8"))
        prompt = str(state.get("prompt", "")).strip()
        reasoning = state_reasoning_text(state).strip()
    else:
        state = None
        if not args.prompt_file or not args.reasoning_file:
            raise SystemExit(
                "Pass either --state-json or both --prompt-file and --reasoning-file."
            )
        prompt = args.prompt_file.read_text(encoding="utf-8").strip()
        reasoning = args.reasoning_file.read_text(encoding="utf-8").strip()
    payload = {
        "status": "terminated_max_length",
        "max_length": args.max_length,
        "current_length": args.current_length,
        "prompt": prompt,
        "summary": (
            "Reasoning was terminated because the configured maximum token length "
            "was reached before a final answer was produced."
        ),
        "progress_summary": rough_progress_summary(reasoning),
        "why_no_final_answer": (
            "The trajectory still required additional reasoning or verification when "
            "the length threshold was reached, so producing a final answer would risk "
            "overclaiming beyond the completed trace."
        ),
        "reasoning_tail": rough_tail(reasoning),
    }
    if state is not None:
        state["status"] = "length_cut"
        state["termination_summary"] = payload
        state["max_length"] = args.max_length
        args.state_json.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif args.output_file:
        output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(output, encoding="utf-8")
    else:
        output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
