#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_MODEL = os.environ.get("CODEX_MODEL", "gpt-5.4")
DEFAULT_CODEX_BIN = os.environ.get("CODEX_BIN", "codex")


PROMPT_TEMPLATE = """\
You are auditing one mathematical or technical reasoning trace.

Task:
1. Read the problem/context, if provided.
2. Read the trace as an ordered list of numbered segments.
3. Find the FIRST segment that contains a substantive error.
   - A substantive error is a false claim, invalid implication, unjustified theorem invocation,
     scope overclaim, missing condition that breaks the argument, or a step that makes the
     rest of the trace unreliable.
   - Do not select a later clearer error if an earlier segment already contains a real error.
   - Do not flag merely verbose, stylistic, or incomplete-but-not-wrong segments.
4. Return the original trace truncated through and including that first erroneous segment.
5. Add exactly one new segment immediately after it. The new segment must validate and cancel
   the error: explicitly say why the previous segment is invalid and what should be used
   instead or what uncertainty remains.
   - Write this segment in the same natural voice as the original trace, as if the model
     generating the trace paused, noticed the problem, and revalidated its own reasoning.
   - The segment must start with one of these prefixes:
     * "Wait, I should re-check this step:"
     * "Hold on, I may be assuming too much here:"
     * "I need to verify this before continuing:"
     * "This step needs a closer check:"
     * "Let me pause and validate the last inference:"
   - Use the prefix naturally. Prefer self-correction over external-grader language such as
     "This segment is invalid."
   - Keep it as one reasoning segment, not a polished final answer.

Output requirements:
- Return ONLY one valid JSON object.
- Do not include markdown fences.
- Use this schema exactly:
  {{
    "first_error_segment_index": integer or null,
    "first_error_summary": string,
    "truncated_segments": array of strings,
    "cancellation_segment": string
  }}
- Segment indices are zero-based.
- If no substantive error is found, set first_error_segment_index to null,
  truncated_segments to the full input segments, cancellation_segment to "",
  and do not add any correction.
- The cancellation_segment must be a single natural self-correction segment, not a full rewritten answer.

Problem/context:
{problem}

Trace segments:
{segments_json}
"""


def split_trace_segments(trace: str) -> list[str]:
    """Split a free-form reasoning trace into stable paragraph-like segments."""
    text = trace.strip()
    if not text:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    sentence_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'`$])", text)
    segments: list[str] = []
    current: list[str] = []
    current_len = 0
    for part in sentence_parts:
        part = part.strip()
        if not part:
            continue
        current.append(part)
        current_len += len(part)
        if current_len >= 500:
            segments.append(" ".join(current).strip())
            current = []
            current_len = 0
    if current:
        segments.append(" ".join(current).strip())
    return segments or [text]


def normalize_trace_input(trace: str | list[str]) -> list[str]:
    if isinstance(trace, str):
        return split_trace_segments(trace)
    if isinstance(trace, list) and all(isinstance(item, str) for item in trace):
        return [item.strip() for item in trace if item.strip()]
    raise TypeError("trace must be a string or list[str]")


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"Codex output did not contain a JSON object: {text[:500]}")
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Codex output JSON must be an object")
    return payload


def validate_response(payload: dict[str, Any], input_segments: list[str]) -> dict[str, Any]:
    idx = payload.get("first_error_segment_index")
    if idx is not None:
        if not isinstance(idx, int):
            raise ValueError("first_error_segment_index must be an integer or null")
        if idx < 0 or idx >= len(input_segments):
            raise ValueError("first_error_segment_index is out of range")

    for key in ("first_error_summary", "cancellation_segment"):
        if not isinstance(payload.get(key), str):
            raise ValueError(f"{key} must be a string")

    for key in ("truncated_segments",):
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings")

    expected_truncated = input_segments if idx is None else input_segments[: idx + 1]
    payload["truncated_segments"] = expected_truncated

    if idx is not None and not payload["cancellation_segment"].strip():
        raise ValueError("cancellation_segment must be non-empty when an error is found")

    return payload


def build_prompt(segments: list[str], problem: str | None = None) -> str:
    return PROMPT_TEMPLATE.format(
        problem=(problem or "").strip() or "(none provided)",
        segments_json=json.dumps(segments, ensure_ascii=False, indent=2),
    )


def call_codex_first_error_truncation(
    trace: str | list[str],
    *,
    problem: str | None = None,
    codex_bin: str = DEFAULT_CODEX_BIN,
    model: str | None = DEFAULT_MODEL,
    reasoning_effort: str | None = None,
    cwd: Path | str | None = None,
    sandbox: str = "workspace-write",
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    """Call Codex once and return trace truncated at the first detected error.

    The returned object contains the original segments through the first erroneous
    segment and exactly one Codex-authored cancellation segment. Input traces can
    be a free-form string or an already segmented list of strings.
    """

    segments = normalize_trace_input(trace)
    prompt = build_prompt(segments, problem)

    cmd = [codex_bin, "exec"]
    if cwd is not None:
        cmd.extend(["--cd", str(cwd)])
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

    payload = extract_json_object(completed.stdout)
    return validate_response(payload, segments)


def load_trace_from_path(path: Path) -> str | list[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, dict):
            for key in ("trace", "reasoning_trace", "segments"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [
                        item.get("notes", "") if isinstance(item, dict) else str(item)
                        for item in value
                    ]
                if isinstance(value, str):
                    return value
    return text


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Use Codex to truncate one reasoning trace at the first error and add one cancellation segment.",
    )
    parser.add_argument("--trace-file", type=Path, help="Trace text/JSON file. Defaults to stdin.")
    parser.add_argument("--problem-file", type=Path, help="Optional problem/context text file.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path. Defaults to stdout.")
    parser.add_argument("--codex-bin", default=DEFAULT_CODEX_BIN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    trace = load_trace_from_path(args.trace_file) if args.trace_file else sys.stdin.read()
    problem = args.problem_file.read_text(encoding="utf-8") if args.problem_file else None

    result = call_codex_first_error_truncation(
        trace,
        problem=problem,
        codex_bin=args.codex_bin,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        cwd=args.cwd,
        sandbox=args.sandbox,
        timeout_seconds=args.timeout_seconds,
    )
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
