#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


CSV_FIELDS = [
    "global_index",
    "source_json",
    "paper_id",
    "paper_title",
    "paper_link",
    "question_link",
    "question_id",
    "parser_is_solved",
    "context_brief",
    "original_question",
    "self_contained_problem",
    "macro_subject",
    "category_tag",
    "open_status",
    "status_search_result",
    "status_evidence",
    "status_evidence_urls",
    "confidence",
    "validation_warnings",
    "model",
    "effort",
    "elapsed_s",
    "checkpoint_path",
]

CLAUDE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "self_contained_problem": {
            "type": "string",
            "description": "A polished, self-contained mathematical problem statement with all needed definitions and setup.",
        },
        "macro_subject": {
            "type": "string",
            "description": "Broad mathematical subject area, for example Algebra, Topology, Analysis, Geometry, Number Theory, Combinatorics, Probability, Mathematical Physics, PDEs and Dynamical Systems, Logic and Foundations, Applied Mathematics, Theoretical Computer Science, Statistics and Machine Learning, or Other.",
        },
        "category_tag": {
            "type": "string",
            "description": "A short, specific tag such as Hessian nilpotent polynomials, random-cluster models, Banach space operators, or arithmetic functions.",
        },
        "open_status": {
            "type": "string",
            "enum": ["open", "partially_solved", "solved", "unknown"],
        },
        "status_search_result": {
            "type": "string",
            "description": "One short paragraph summarizing whether the problem appears still open, solved, partially solved, or unknown from the search.",
        },
        "status_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "snippet": {"type": "string"},
                    "claim": {"type": "string"},
                },
                "required": ["title", "url", "snippet", "claim"],
            },
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
    },
    "required": [
        "self_contained_problem",
        "macro_subject",
        "category_tag",
        "open_status",
        "status_search_result",
        "status_evidence",
        "confidence",
    ],
}

SYSTEM_PROMPT = """\
You are a mathematics research assistant preparing a dataset of research problems.

You will receive one parsed question from a paper. Produce one clean JSON object.

Primary task:
- Rewrite the question into a well-designed, self-contained mathematical problem.
- Include all definitions, notation, ambient objects, quantifiers, and setup needed to understand the problem.
- The problem statement must not mention the original paper, article, source, arXiv, authors, sections, pages, extracted text, or evidence.
- Preserve the mathematical intent of the parsed question. Do not broaden it.

Classification task:
- Assign a broad macro_subject.
- Assign a concise smaller category_tag.

Status-check task:
- Use web search when available to check whether the problem appears still open, partially solved, solved, or unknown.
- Prefer recent and authoritative sources: arXiv papers, journal papers, MathSciNet/ZBMath style pages, project/problem pages, authors' pages, and survey updates.
- Do not claim solved or open unless the search evidence supports it.
- If you cannot verify the current status, use open_status="unknown".
- Keep status_search_result short, factual, and source-grounded.

Return only valid JSON matching the supplied schema.
"""


@dataclass(frozen=True)
class QuestionRecord:
    global_index: int
    source_json: Path
    paper_id: str
    paper_title: str
    paper_link: str
    question_link: str
    question_id: str
    parser_is_solved: str
    context_brief: str
    original_question: str
    evidence: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read outputs/parse-paper/*.json, send accepted questions to Claude Code, "
            "and append self-contained problem records to a CSV."
        ),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("outputs/parse-paper"),
        help="Directory containing per-paper parser JSON files.",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=None,
        help="Process exactly one parser JSON file instead of scanning --input-dir.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/self-contained-math-problems.csv"),
        help="CSV file to append results to.",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=Path("outputs/self-contained-math-problem-checkpoints"),
        help="Directory for one JSON checkpoint per processed question.",
    )
    parser.add_argument(
        "--error-log",
        type=Path,
        default=Path("logs/self-contained-problem-errors.jsonl"),
        help="JSONL log for invalid parser files, Claude failures, and parse errors.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start at this global accepted-question index.",
    )
    parser.add_argument(
        "--end-index",
        type=int,
        default=None,
        help="Stop before this global accepted-question index.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most this many accepted questions after applying start/end.",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="Split records into this many global-index shards.",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="Process only records whose global index belongs to this zero-based shard.",
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip questions that already have a checkpoint.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned records without calling Claude or writing CSV rows.",
    )
    parser.add_argument(
        "--claude-bin",
        default="claude",
        help="Claude Code executable.",
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude Code model passed to --model. The opus alias resolves to claude-opus-4-7 in current Claude Code.",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "xhigh", "max"],
        help="Claude Code effort level.",
    )
    parser.add_argument(
        "--tools",
        default="WebSearch,WebFetch",
        help='Claude Code tools list. Use "default" for all tools, or "" to omit --tools.',
    )
    parser.add_argument(
        "--permission-mode",
        default="auto",
        choices=["acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan"],
        help="Claude Code permission mode for non-interactive runs.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Seconds to wait for each Claude call.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Retry count after a failed Claude call or invalid JSON response.",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=str,
        default=None,
        help="Optional per-call Claude Code --max-budget-usd value.",
    )
    parser.add_argument(
        "--no-session-persistence",
        action="store_true",
        help="Pass --no-session-persistence through to Claude Code.",
    )
    parser.add_argument(
        "--fsync",
        action="store_true",
        help="Call os.fsync after each CSV row and checkpoint write.",
    )
    return parser.parse_args()


def log_error(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    slug = re.sub(r"[^a-z0-9._-]+", "-", lowered)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "item"


def normalize_arxiv_id_from_stem(stem: str) -> str | None:
    modern = stem.replace("_", ".")
    if re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", modern):
        return modern

    legacy = re.fullmatch(r"([a-z][a-z-]*)[-_](\d{7}(v\d+)?)", stem)
    if legacy:
        return f"{legacy.group(1)}/{legacy.group(2)}"

    return None


def derived_paper_link(source_json: Path, payload: dict[str, Any]) -> str:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    for key in ("url", "resolved_locator"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    arxiv_id = normalize_arxiv_id_from_stem(source_json.stem)
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"

    return ""


def derived_paper_id(source_json: Path) -> str:
    return normalize_arxiv_id_from_stem(source_json.stem) or source_json.stem


def first_evidence_page(evidence: list[dict[str, Any]]) -> str:
    for item in evidence:
        page = item.get("page")
        if page is None:
            continue
        return str(page)
    return ""


def question_link(paper_link: str, paper_id: str, evidence: list[dict[str, Any]]) -> str:
    page = first_evidence_page(evidence)
    if not page:
        return paper_link

    page_match = re.search(r"\d+", page)
    if not page_match:
        return paper_link

    page_number = page_match.group(0)
    if paper_link.startswith("https://arxiv.org/abs/") and "/" in paper_id:
        return f"https://arxiv.org/pdf/{paper_id}#page={page_number}"
    if paper_link.startswith("https://arxiv.org/abs/"):
        return f"https://arxiv.org/pdf/{paper_id}.pdf#page={page_number}"
    if paper_link.endswith(".pdf") or ".pdf?" in paper_link:
        return f"{paper_link}#page={page_number}"
    return paper_link


def load_question_records(
    input_dir: Path,
    error_log: Path,
    input_file: Path | None = None,
) -> list[QuestionRecord]:
    records: list[QuestionRecord] = []
    global_index = 0
    source_json_paths = [input_file] if input_file is not None else sorted(input_dir.glob("*.json"))

    for source_json in source_json_paths:
        if source_json is None:
            continue
        try:
            payload = json.loads(source_json.read_text(encoding="utf-8"))
        except Exception as exc:
            log_error(
                error_log,
                {
                    "event": "invalid_parser_json",
                    "source_json": str(source_json),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            continue

        if not isinstance(payload, dict):
            log_error(
                error_log,
                {
                    "event": "invalid_parser_payload",
                    "source_json": str(source_json),
                    "error": "Top-level parser payload is not an object.",
                },
            )
            continue

        source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        paper_id = derived_paper_id(source_json)
        paper_title = str(source.get("title") or "")
        paper_link = derived_paper_link(source_json, payload)

        accepted = payload.get("accepted") or []
        if not isinstance(accepted, list):
            log_error(
                error_log,
                {
                    "event": "invalid_accepted_array",
                    "source_json": str(source_json),
                    "error": "accepted is not a list.",
                },
            )
            continue

        for question in accepted:
            if not isinstance(question, dict):
                continue
            evidence = question.get("evidence") or []
            if not isinstance(evidence, list):
                evidence = []
            meta = question.get("meta") if isinstance(question.get("meta"), dict) else {}
            question_id = str(question.get("id") or f"q_{global_index:05d}")
            original_question = str(question.get("question_text") or "").strip()
            if not original_question:
                log_error(
                    error_log,
                    {
                        "event": "missing_question_text",
                        "source_json": str(source_json),
                        "question_id": question_id,
                    },
                )
                continue

            records.append(
                QuestionRecord(
                    global_index=global_index,
                    source_json=source_json,
                    paper_id=paper_id,
                    paper_title=paper_title,
                    paper_link=paper_link,
                    question_link=question_link(paper_link, paper_id, evidence),
                    question_id=question_id,
                    parser_is_solved=json.dumps(meta.get("is_solved"), ensure_ascii=False),
                    context_brief=str(question.get("context_brief") or ""),
                    original_question=original_question,
                    evidence=evidence,
                )
            )
            global_index += 1

    return records


def checkpoint_path(checkpoint_dir: Path, record: QuestionRecord) -> Path:
    digest_input = f"{record.source_json}|{record.question_id}|{record.original_question}"
    digest = hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:12]
    name = (
        f"{record.global_index:06d}__"
        f"{slugify(record.paper_id.replace('/', '-'))}__"
        f"{slugify(record.question_id)}__{digest}.json"
    )
    return checkpoint_dir / name


def compact_evidence(evidence: list[dict[str, Any]], max_items: int = 4) -> list[dict[str, str]]:
    compacted: list[dict[str, str]] = []
    for item in evidence[:max_items]:
        if not isinstance(item, dict):
            continue
        compacted.append(
            {
                "page": str(item.get("page") or ""),
                "quote": str(item.get("quote") or "")[:1200],
            }
        )
    return compacted


def build_prompt(record: QuestionRecord) -> str:
    payload = {
        "paper_id": record.paper_id,
        "paper_title": record.paper_title,
        "paper_link": record.paper_link,
        "question_link": record.question_link,
        "question_id": record.question_id,
        "context_brief": record.context_brief,
        "parsed_question": record.original_question,
        "parser_meta_is_solved": record.parser_is_solved,
        "evidence_from_original_source": compact_evidence(record.evidence),
    }
    return (
        "Transform this parsed mathematical question into one dataset row.\n\n"
        "Important constraints for self_contained_problem:\n"
        "- It must be written as a standalone mathematical problem.\n"
        "- It must include all definitions and setup needed by a reader who has not seen the source.\n"
        "- It must not mention the source paper, the original paper, an article, arXiv, authors, sections, pages, evidence, or extracted text.\n"
        "- It should be a problem statement, not an essay or literature review.\n\n"
        "For open_status and status_search_result, search the web if available and summarize only what is supported.\n"
        "If evidence is inconclusive, use open_status=\"unknown\".\n\n"
        "Input JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def claude_command(args: argparse.Namespace, prompt: str) -> list[str]:
    cmd = [
        args.claude_bin,
        "-p",
        "--model",
        args.model,
        "--effort",
        args.effort,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(CLAUDE_JSON_SCHEMA, ensure_ascii=False),
        "--permission-mode",
        args.permission_mode,
        "--system-prompt",
        SYSTEM_PROMPT,
    ]
    if args.no_session_persistence:
        cmd.append("--no-session-persistence")
    if args.tools != "":
        cmd.extend(["--tools", args.tools])
    if args.max_budget_usd:
        cmd.extend(["--max-budget-usd", args.max_budget_usd])
    cmd.append("--")
    cmd.append(prompt)
    return cmd


def extract_text_from_claude_stdout(stdout: str) -> str:
    cleaned = stdout.strip()
    if not cleaned:
        return ""

    try:
        wrapper = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned

    if isinstance(wrapper, dict):
        structured_output = wrapper.get("structured_output")
        if isinstance(structured_output, dict):
            return json.dumps(structured_output, ensure_ascii=False)
        for key in ("result", "content", "text", "output"):
            value = wrapper.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False)
        if isinstance(wrapper.get("message"), dict):
            content = wrapper["message"].get("content")
            if isinstance(content, str):
                return content
        return json.dumps(wrapper, ensure_ascii=False)

    return cleaned


def parse_model_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def run_claude(record: QuestionRecord, args: argparse.Namespace) -> tuple[dict[str, Any], float, str]:
    prompt = build_prompt(record)
    cmd = claude_command(args, prompt)
    errors: list[str] = []

    for attempt in range(args.retries + 1):
        started = time.time()
        try:
            proc = subprocess.run(
                cmd,
                text=True,
                capture_output=True,
                timeout=args.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"attempt {attempt + 1}: timed out after {args.timeout}s")
            continue
        elapsed = time.time() - started

        if proc.returncode != 0:
            errors.append(
                f"attempt {attempt + 1}: returncode={proc.returncode}; "
                f"stderr={proc.stderr.strip()[:2000]}; stdout={proc.stdout.strip()[:2000]}"
            )
            continue

        response_text = extract_text_from_claude_stdout(proc.stdout)
        try:
            parsed = parse_model_json(response_text)
        except Exception as exc:
            errors.append(
                f"attempt {attempt + 1}: invalid JSON response ({type(exc).__name__}: {exc}); "
                f"stdout={proc.stdout.strip()[:2000]}"
            )
            continue

        if not isinstance(parsed, dict):
            errors.append(f"attempt {attempt + 1}: model JSON is not an object")
            continue

        return parsed, elapsed, proc.stdout

    raise RuntimeError("Claude call failed. " + " | ".join(errors))


def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    problem = str(artifact.get("self_contained_problem") or "")
    banned = [
        "original paper",
        "this paper",
        "the paper",
        "article",
        "arxiv",
        "source text",
        "extracted",
    ]
    lower_problem = problem.lower()
    for phrase in banned:
        if phrase in lower_problem:
            warnings.append(f"self_contained_problem_mentions_{phrase.replace(' ', '_')}")
    if len(problem) < 80:
        warnings.append("self_contained_problem_seems_short")
    if artifact.get("open_status") not in {"open", "partially_solved", "solved", "unknown"}:
        warnings.append("invalid_open_status")
    return warnings


def evidence_urls(artifact: dict[str, Any]) -> str:
    evidence = artifact.get("status_evidence")
    if not isinstance(evidence, list):
        return ""
    urls = []
    for item in evidence:
        if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"].strip():
            urls.append(item["url"].strip())
    return " ".join(urls)


def csv_row(
    record: QuestionRecord,
    artifact: dict[str, Any],
    args: argparse.Namespace,
    elapsed_s: float,
    ckp_path: Path,
    warnings: list[str],
) -> dict[str, Any]:
    return {
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
        "self_contained_problem": artifact.get("self_contained_problem", ""),
        "macro_subject": artifact.get("macro_subject", ""),
        "category_tag": artifact.get("category_tag", ""),
        "open_status": artifact.get("open_status", ""),
        "status_search_result": artifact.get("status_search_result", ""),
        "status_evidence": json.dumps(artifact.get("status_evidence", []), ensure_ascii=False),
        "status_evidence_urls": evidence_urls(artifact),
        "confidence": artifact.get("confidence", ""),
        "validation_warnings": ";".join(warnings),
        "model": args.model,
        "effort": args.effort,
        "elapsed_s": round(elapsed_s, 2),
        "checkpoint_path": str(ckp_path),
    }


def append_csv_row(path: Path, row: dict[str, Any], fsync: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = None
    try:
        if fcntl is not None:
            lock_handle = path.with_suffix(path.suffix + ".lock").open("w", encoding="utf-8")
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        needs_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            if needs_header:
                writer.writeheader()
            writer.writerow(row)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
    finally:
        if lock_handle is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()


def write_checkpoint(path: Path, payload: dict[str, Any], fsync: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        if fsync:
            os.fsync(handle.fileno())


def selected_records(records: list[QuestionRecord], args: argparse.Namespace) -> list[QuestionRecord]:
    if args.start_index < 0:
        raise SystemExit("--start-index must be non-negative")
    if args.end_index is not None and args.end_index < args.start_index:
        raise SystemExit("--end-index must be greater than or equal to --start-index")
    if args.limit is not None and args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    if args.shard_count < 1:
        raise SystemExit("--shard-count must be at least 1")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise SystemExit("--shard-index must be between 0 and --shard-count - 1")

    selected = [
        record
        for record in records
        if record.global_index >= args.start_index
        and (args.end_index is None or record.global_index < args.end_index)
        and record.global_index % args.shard_count == args.shard_index
    ]
    if args.limit is not None:
        selected = selected[: args.limit]
    return selected


def main() -> None:
    args = parse_args()
    if args.input_file is not None and not args.input_file.exists():
        raise SystemExit(f"Input file not found: {args.input_file}")
    if args.input_file is None and not args.input_dir.exists():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    records = selected_records(
        load_question_records(args.input_dir, args.error_log, args.input_file),
        args,
    )
    print(f"Loaded {len(records)} accepted questions to process.")
    if args.dry_run:
        for record in records:
            print(
                json.dumps(
                    {
                        "global_index": record.global_index,
                        "source_json": str(record.source_json),
                        "paper_id": record.paper_id,
                        "paper_link": record.paper_link,
                        "question_link": record.question_link,
                        "question_id": record.question_id,
                        "original_question": record.original_question,
                    },
                    ensure_ascii=False,
                )
            )
        return

    processed = 0
    skipped = 0
    failed = 0

    for offset, record in enumerate(records, start=1):
        ckp_path = checkpoint_path(args.checkpoint_dir, record)
        label = f"[{offset}/{len(records)} idx={record.global_index} {record.paper_id} {record.question_id}]"

        if args.skip_existing and ckp_path.exists():
            print(f"{label} skip checkpoint")
            skipped += 1
            continue

        print(f"{label} start")
        try:
            artifact, elapsed_s, raw_stdout = run_claude(record, args)
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
                "model": args.model,
                "effort": args.effort,
                "elapsed_s": round(elapsed_s, 2),
                "validation_warnings": warnings,
                "raw_claude_stdout": raw_stdout,
            }
            write_checkpoint(ckp_path, checkpoint_payload, args.fsync)
            row = csv_row(record, artifact, args, elapsed_s, ckp_path, warnings)
            append_csv_row(args.output_csv, row, args.fsync)
            print(f"{label} ok elapsed_s={elapsed_s:.1f} warnings={len(warnings)}")
            processed += 1
        except Exception as exc:
            failed += 1
            log_error(
                args.error_log,
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
        f"csv={args.output_csv} checkpoints={args.checkpoint_dir}"
    )


if __name__ == "__main__":
    main()
