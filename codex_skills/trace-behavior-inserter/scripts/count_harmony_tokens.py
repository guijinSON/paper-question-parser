#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_encoding():
    try:
        from openai_harmony import HarmonyEncodingName, load_harmony_encoding
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: openai_harmony. Install it in the Python environment "
            "used to run this token counter."
        ) from exc
    return load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)


def count_tokens(text: str) -> int:
    encoding = load_encoding()
    return len(encoding.encode(text))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count Harmony GPT-OSS tokens in one or more text files or a consolidated trace-loop JSON.",
    )
    parser.add_argument("files", type=Path, nargs="*")
    parser.add_argument(
        "--state-json",
        type=Path,
        help="Count the reconstructed reasoning text from interleaved_trace[*].text.",
    )
    parser.add_argument("--max-length", type=int)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def state_reasoning_text(path: Path) -> str:
    state = json.loads(path.read_text(encoding="utf-8"))
    return "\n\n".join(
        str(entry.get("text", "")).strip()
        for entry in state.get("interleaved_trace", [])
        if str(entry.get("text", "")).strip()
    )


def main() -> int:
    args = parse_args()
    per_file = []
    total = 0
    if args.state_json:
        text = state_reasoning_text(args.state_json)
        count = count_tokens(text)
        total += count
        per_file.append({"path": str(args.state_json), "tokens": count, "source": "state_json"})
    if not args.state_json and not args.files:
        raise SystemExit("Pass at least one file or --state-json.")
    for path in args.files:
        text = path.read_text(encoding="utf-8")
        count = count_tokens(text)
        total += count
        per_file.append({"path": str(path), "tokens": count})

    payload = {
        "total_tokens": total,
        "max_length": args.max_length,
        "over_threshold": args.max_length is not None and total >= args.max_length,
        "files": per_file,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"total_tokens={total}")
        if args.max_length is not None:
            print(f"max_length={args.max_length}")
            print(f"over_threshold={str(payload['over_threshold']).lower()}")
        for item in per_file:
            print(f"{item['tokens']}\t{item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
