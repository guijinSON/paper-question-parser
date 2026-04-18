#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise AssertionError(message)


def assert_type(value, expected_type, message: str) -> None:
    if not isinstance(value, expected_type):
        fail(message)


def validate_evidence_list(evidence_list, where: str) -> None:
    assert_type(evidence_list, list, f"{where}: evidence must be a list")
    if not evidence_list:
        fail(f"{where}: evidence must not be empty")
    for idx, evidence in enumerate(evidence_list):
        assert_type(evidence, dict, f"{where}: evidence[{idx}] must be an object")
        page = evidence.get("page")
        if not isinstance(page, (int, str)):
            fail(f"{where}: evidence[{idx}].page must be an int or string")
        quote = evidence.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            fail(f"{where}: evidence[{idx}].quote must be a non-empty string")


def validate_source_metadata(source: dict, path: Path) -> None:
    where = f"{path.name}: source"
    assert_type(source, dict, f"{where} must be an object")
    url = source.get("url")
    if not isinstance(url, str) or not url.strip():
        fail(f"{where}.url must be a non-empty string")
    resolved_locator = source.get("resolved_locator")
    if not isinstance(resolved_locator, str):
        fail(f"{where}.resolved_locator must be a string")
    title = source.get("title")
    if not isinstance(title, str) or not title.strip():
        fail(f"{where}.title must be a non-empty string")
    title_origin = source.get("title_origin")
    if title_origin is not None and title_origin not in {"source_text", "resolver_metadata", "ai_extracted", "filename"}:
        fail(
            f"{where}.title_origin must be one of "
            f"source_text, resolver_metadata, ai_extracted, filename"
        )


def validate_accepted_item(item: dict, idx: int, path: Path) -> None:
    where = f"{path.name}: accepted[{idx}]"
    assert_type(item, dict, f"{where} must be an object")
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        fail(f"{where}.id must be a non-empty string")
    question_text = item.get("question_text")
    if not isinstance(question_text, str) or not question_text.strip():
        fail(f"{where}.question_text must be a non-empty string")
    context_brief = item.get("context_brief")
    if not isinstance(context_brief, str) or not context_brief.strip():
        fail(f"{where}.context_brief must be a non-empty string")
    meta = item.get("meta")
    assert_type(meta, dict, f"{where}.meta must be an object")
    is_solved = meta.get("is_solved")
    if not isinstance(is_solved, bool):
        fail(f"{where}.meta.is_solved must be a boolean")
    validate_evidence_list(item.get("evidence"), where)


def validate_needs_review_item(item: dict, idx: int, path: Path) -> None:
    where = f"{path.name}: needs_review[{idx}]"
    assert_type(item, dict, f"{where} must be an object")
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        fail(f"{where}.id must be a non-empty string")
    reason = item.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        fail(f"{where}.reason must be a non-empty string")
    question_text_raw = item.get("question_text_raw")
    if not isinstance(question_text_raw, str):
        fail(f"{where}.question_text_raw must be a string")
    validate_evidence_list(item.get("evidence"), where)


def validate_trace_item(item: dict, idx: int, path: Path) -> None:
    where = f"{path.name}: trace[{idx}]"
    assert_type(item, dict, f"{where} must be an object")
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        fail(f"{where}.id must be a non-empty string")
    stage = item.get("stage")
    if not isinstance(stage, str) or not stage.strip():
        fail(f"{where}.stage must be a non-empty string")
    notes = item.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        fail(f"{where}.notes must be a non-empty string")
    evidence_refs = item.get("evidence_refs")
    assert_type(evidence_refs, list, f"{where}.evidence_refs must be a list")
    for ref_idx, evidence_ref in enumerate(evidence_refs):
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            fail(f"{where}.evidence_refs[{ref_idx}] must be a non-empty string")


def validate_file(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.name}: invalid JSON: {exc}")

    assert_type(payload, dict, f"{path.name}: top-level value must be an object")
    source = payload.get("source")
    accepted = payload.get("accepted")
    needs_review = payload.get("needs_review")
    trace = payload.get("trace")
    if source is not None:
        validate_source_metadata(source, path)
    assert_type(accepted, list, f"{path.name}: accepted must be a list")
    assert_type(needs_review, list, f"{path.name}: needs_review must be a list")
    assert_type(trace, list, f"{path.name}: trace must be a list")

    for idx, item in enumerate(accepted):
        validate_accepted_item(item, idx, path)
    for idx, item in enumerate(needs_review):
        validate_needs_review_item(item, idx, path)
    for idx, item in enumerate(trace):
        validate_trace_item(item, idx, path)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: validate_parse_paper_outputs.py <file> [<file> ...]", file=sys.stderr)
        return 2

    paths = [Path(arg) for arg in argv[1:]]
    for path in paths:
        validate_file(path)
        print(f"OK {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
