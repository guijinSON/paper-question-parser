#!/usr/bin/env python3
"""Build prioritized open-problem target CSVs.

This is a cheap preflight pass for the expensive Codex parser.  It keeps the
original source identity, but prefers direct full-text targets when they are
obvious, especially for zbMATH rows where the browser page is often blocked.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = [
    "outputs/shards/open-problems-shard-0.csv",
    "outputs/shards/open-problems-shard-1.csv",
]

OUTPUT_COLUMNS = [
    "source",
    "source_id",
    "title",
    "url",
    "year",
    "phrase",
    "extra",
    "original_url",
    "target_url",
    "target_kind",
    "tier",
    "priority_reason",
    "resolver_status",
    "resolver_detail",
    "resolver_candidates",
]

RUNNER_COLUMNS = ["source", "source_id", "title", "url", "year", "phrase", "extra"]

ARXIV_ABS_RE = re.compile(r"https?://arxiv\.org/abs/([^?#\s|]+)", re.I)
ARXIV_PDF_RE = re.compile(r"https?://arxiv\.org/pdf/([^?#\s|]+?)(?:\.pdf)?(?:[?#][^\s|]*)?$", re.I)
ZBMATH_ID_RE = re.compile(r"(?:zbmath\.org/)?(\d{4,})$")


@dataclass
class ResolvedTarget:
    original_url: str
    target_url: str
    target_kind: str
    tier: str
    priority_reason: str
    resolver_status: str
    resolver_detail: str
    resolver_candidates: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", default=[], help="Input CSV. Repeatable.")
    parser.add_argument("--parse-dir", default="outputs/parse-paper")
    parser.add_argument("--output-dir", default="outputs/priority-targets")
    parser.add_argument("--sample-per-source", type=int, default=2)
    parser.add_argument("--zbmath-workers", type=int, default=12)
    parser.add_argument("--zbmath-timeout", type=float, default=12.0)
    parser.add_argument("--zbmath-api", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-zbmath-api", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--include-completed", action="store_true")
    return parser.parse_args()


def read_completed_urls(parse_dir: Path) -> set[str]:
    completed: set[str] = set()
    if not parse_dir.exists():
        return completed
    required = {"accepted", "needs_review", "trace"}
    for path in parse_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict) or not required.issubset(payload):
            continue
        source = payload.get("source")
        if not isinstance(source, dict):
            continue
        url = (source.get("url") or "").strip()
        if url:
            completed.add(url)
    return completed


def read_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = [name for name in RUNNER_COLUMNS if name not in (reader.fieldnames or [])]
            if missing:
                raise SystemExit(f"{path}: missing required columns: {', '.join(missing)}")
            for row in reader:
                clean = {name: clean_csv_field(row.get(name) or "") for name in RUNNER_COLUMNS}
                url = clean["url"]
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                rows.append(clean)
    return rows


def clean_csv_field(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\r", " ").replace("\n", " ").replace("\t", " ")).strip()


def split_extra_links(extra: str) -> list[str]:
    extra = extra.strip()
    if not extra or extra.lower() in {"nan", "links=nan"}:
        return []

    values: list[str] = []
    for chunk in re.split(r"\s*\|\s*", extra):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            _, value = chunk.split("=", 1)
            value = value.strip()
        else:
            value = chunk
        if value and value.lower() != "nan" and value.startswith(("http://", "https://")):
            values.append(value)
    return values


def normalize_arxiv_pdf(url: str) -> str | None:
    url = url.strip()
    m = ARXIV_ABS_RE.search(url)
    if m:
        arxiv_id = m.group(1).removesuffix(".pdf")
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    m = ARXIV_PDF_RE.search(url)
    if m:
        arxiv_id = m.group(1).removesuffix(".pdf")
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    return None


def is_pdf_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()
    return path.endswith(".pdf") or "/pdf/" in path or path.endswith("/pdf")


def is_doi_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host in {"doi.org", "dx.doi.org"} or host.endswith(".doi.org")


def classify_candidate_url(url: str) -> tuple[str, str] | None:
    arxiv_pdf = normalize_arxiv_pdf(url)
    if arxiv_pdf:
        return arxiv_pdf, "arxiv_pdf"
    if is_pdf_url(url):
        return url, "direct_pdf"
    if is_doi_url(url):
        return url, "doi"
    return None


def row_hash(row: dict[str, str]) -> str:
    key = "\t".join(row.get(name, "") for name in ("source", "source_id", "title", "url"))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def extract_zbmath_id(row: dict[str, str]) -> str | None:
    for value in (row.get("source_id", ""), row.get("url", "")):
        value = value.strip().rstrip("/")
        m = ZBMATH_ID_RE.search(value)
        if m:
            return m.group(1)
    return None


def load_zbmath_cache(path: Path) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return cache
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            doc_id = str(payload.get("id") or "")
            if doc_id:
                cache[doc_id] = payload
    return cache


def fetch_zbmath_doc(doc_id: str, timeout: float) -> dict[str, Any]:
    url = f"https://api.zbmath.org/v1/document/{urllib.parse.quote(doc_id)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "paper-question-parser-priority-resolver/1.0",
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        payload = json.loads(raw.decode("utf-8"))
        return {
            "id": doc_id,
            "ok": True,
            "elapsed": round(time.monotonic() - started, 3),
            "payload": payload,
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {
            "id": doc_id,
            "ok": False,
            "elapsed": round(time.monotonic() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def extract_links_from_zbmath_payload(record: dict[str, Any]) -> list[str]:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    links = result.get("links")
    out: list[str] = []
    if isinstance(links, list):
        for item in links:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            if url.startswith(("http://", "https://")):
                out.append(url)
    return out


def best_from_candidates(candidates: list[str]) -> tuple[str, str] | None:
    typed: list[tuple[str, str]] = []
    for candidate in candidates:
        classified = classify_candidate_url(candidate)
        if classified:
            typed.append(classified)

    for target_url, kind in typed:
        if kind == "arxiv_pdf":
            return target_url, kind
    for target_url, kind in typed:
        if kind == "direct_pdf":
            return target_url, kind
    for target_url, kind in typed:
        if kind == "doi":
            return target_url, kind
    return None


def resolve_zbmath(
    row: dict[str, str],
    api_records: dict[str, dict[str, Any]],
) -> ResolvedTarget:
    original_url = row["url"]
    candidates = split_extra_links(row.get("extra", ""))
    doc_id = extract_zbmath_id(row)
    api_status = "not_queried"
    api_detail = ""

    if doc_id and doc_id in api_records:
        record = api_records[doc_id]
        api_status = "api_ok" if record.get("ok") else "api_error"
        api_detail = record.get("error", "")
        candidates.extend(extract_links_from_zbmath_payload(record))

    # Preserve order while removing duplicates.
    candidates = list(dict.fromkeys(candidates))
    best = best_from_candidates(candidates)
    if best:
        target_url, kind = best
        if kind in {"arxiv_pdf", "direct_pdf"}:
            return ResolvedTarget(
                original_url=original_url,
                target_url=target_url,
                target_kind=kind,
                tier="priority",
                priority_reason=f"zbmath resolved to {kind}",
                resolver_status=api_status,
                resolver_detail=api_detail,
                resolver_candidates=candidates,
            )
        return ResolvedTarget(
            original_url=original_url,
            target_url=target_url,
            target_kind=kind,
            tier="second_tier",
            priority_reason="zbmath resolved only to DOI/landing page",
            resolver_status=api_status,
            resolver_detail=api_detail,
            resolver_candidates=candidates,
        )

    status = api_status
    if candidates:
        status = f"{api_status}_no_full_text_candidate"
    return ResolvedTarget(
        original_url=original_url,
        target_url=original_url,
        target_kind="zbmath_metadata",
        tier="second_tier",
        priority_reason="zbmath had no arxiv/pdf candidate",
        resolver_status=status,
        resolver_detail=api_detail,
        resolver_candidates=candidates,
    )


def resolve_non_zbmath(row: dict[str, str]) -> ResolvedTarget:
    source = row["source"].lower()
    original_url = row["url"]
    candidates = [original_url] + split_extra_links(row.get("extra", ""))
    candidates = list(dict.fromkeys(candidates))
    best = best_from_candidates(candidates)
    if best:
        target_url, kind = best
        if kind in {"arxiv_pdf", "direct_pdf"}:
            return ResolvedTarget(
                original_url=original_url,
                target_url=target_url,
                target_kind=kind,
                tier="priority",
                priority_reason=f"{source} has direct {kind}",
                resolver_status="heuristic",
                resolver_detail="",
                resolver_candidates=candidates,
            )
        return ResolvedTarget(
            original_url=original_url,
            target_url=target_url,
            target_kind=kind,
            tier="second_tier",
            priority_reason=f"{source} is DOI/landing-page first",
            resolver_status="heuristic",
            resolver_detail="",
            resolver_candidates=candidates,
        )

    if source in {"mathoverflow", "aim"}:
        return ResolvedTarget(
            original_url=original_url,
            target_url=original_url,
            target_kind=f"{source}_html",
            tier="priority",
            priority_reason=f"{source} page likely contains problem text directly",
            resolver_status="heuristic",
            resolver_detail="",
            resolver_candidates=candidates,
        )

    if source == "hal":
        target = original_url.rstrip("/") + "/document"
        return ResolvedTarget(
            original_url=original_url,
            target_url=target,
            target_kind="hal_document",
            tier="priority",
            priority_reason="HAL document endpoint is often direct full text",
            resolver_status="heuristic",
            resolver_detail="",
            resolver_candidates=[target] + candidates,
        )

    if source == "core" and "arxiv.org" in original_url.lower():
        target = normalize_arxiv_pdf(original_url) or original_url
        return ResolvedTarget(
            original_url=original_url,
            target_url=target,
            target_kind="arxiv_pdf" if target != original_url else "arxiv",
            tier="priority",
            priority_reason="CORE row points to arXiv",
            resolver_status="heuristic",
            resolver_detail="",
            resolver_candidates=candidates,
        )

    return ResolvedTarget(
        original_url=original_url,
        target_url=original_url,
        target_kind=f"{source}_landing",
        tier="second_tier",
        priority_reason=f"{source} lacks direct full-text hint",
        resolver_status="heuristic",
        resolver_detail="",
        resolver_candidates=candidates,
    )


def enrich_row(row: dict[str, str], resolved: ResolvedTarget) -> dict[str, str]:
    out = {name: row.get(name, "") for name in RUNNER_COLUMNS}
    out.update(
        {
            "original_url": resolved.original_url,
            "target_url": resolved.target_url,
            "target_kind": resolved.target_kind,
            "tier": resolved.tier,
            "priority_reason": resolved.priority_reason,
            "resolver_status": resolved.resolver_status,
            "resolver_detail": resolved.resolver_detail,
            "resolver_candidates": json.dumps(resolved.resolver_candidates, ensure_ascii=False),
        }
    )
    return out


def runner_row(enriched: dict[str, str]) -> dict[str, str]:
    row = {name: enriched.get(name, "") for name in RUNNER_COLUMNS}
    original = enriched.get("original_url") or row["url"]
    target = enriched.get("target_url") or row["url"]
    row["url"] = target
    extra = row.get("extra", "")
    provenance = f"original_url={original} | target_kind={enriched.get('target_kind', '')}"
    row["extra"] = f"{extra} | {provenance}" if extra else provenance
    return row


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def choose_samples(rows: list[dict[str, str]], per_source: int) -> list[dict[str, str]]:
    if per_source <= 0:
        return []
    buckets: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        source = row.get("source", "")
        buckets.setdefault(source, []).append(row)

    samples: list[dict[str, str]] = []
    for source in sorted(buckets):
        ranked = sorted(
            buckets[source],
            key=lambda row: (
                0 if row.get("tier") == "priority" else 1,
                row.get("target_kind", ""),
                row_hash(row),
            ),
        )
        samples.extend(ranked[:per_source])
    return samples


def fetch_needed_zbmath_records(
    rows: list[dict[str, str]],
    cache_path: Path,
    workers: int,
    timeout: float,
    max_fetches: int,
    enabled: bool,
) -> dict[str, dict[str, Any]]:
    cache = load_zbmath_cache(cache_path)
    if not enabled:
        return cache

    needed: list[str] = []
    for row in rows:
        if row.get("source", "").lower() != "zbmath":
            continue
        doc_id = extract_zbmath_id(row)
        if doc_id and doc_id not in cache:
            needed.append(doc_id)
    needed = sorted(set(needed), key=int)
    if max_fetches:
        needed = needed[:max_fetches]
    if not needed:
        return cache

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    with cache_path.open("a", encoding="utf-8") as cache_handle:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(fetch_zbmath_doc, doc_id, timeout): doc_id for doc_id in needed}
            for future in as_completed(futures):
                record = future.result()
                doc_id = str(record.get("id") or futures[future])
                cache[doc_id] = record
                cache_handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                cache_handle.flush()
                completed += 1
                if completed % 250 == 0 or completed == len(needed):
                    print(f"zbmath api: {completed}/{len(needed)}", file=sys.stderr)
    return cache


def main() -> int:
    args = parse_args()
    input_paths = [Path(p) for p in (args.input or DEFAULT_INPUTS)]
    output_dir = Path(args.output_dir)
    rows = read_rows(input_paths)
    completed = set() if args.include_completed else read_completed_urls(Path(args.parse_dir))
    pending = [row for row in rows if row["url"] not in completed]

    cache_path = output_dir / "zbmath-api-cache.jsonl"
    zbmath_records = fetch_needed_zbmath_records(
        pending,
        cache_path=cache_path,
        workers=args.zbmath_workers,
        timeout=args.zbmath_timeout,
        max_fetches=args.max_zbmath_api,
        enabled=args.zbmath_api,
    )

    enriched: list[dict[str, str]] = []
    for row in pending:
        if row["source"].lower() == "zbmath":
            resolved = resolve_zbmath(row, zbmath_records)
        else:
            resolved = resolve_non_zbmath(row)
        enriched.append(enrich_row(row, resolved))

    priority = [row for row in enriched if row["tier"] == "priority"]
    second_tier = [row for row in enriched if row["tier"] != "priority"]
    priority_runner = [runner_row(row) for row in priority]
    second_tier_runner = [runner_row(row) for row in second_tier]

    write_csv(output_dir / "open-problems-priority-targets.csv", priority, OUTPUT_COLUMNS)
    write_csv(output_dir / "open-problems-second-tier-targets.csv", second_tier, OUTPUT_COLUMNS)
    write_csv(output_dir / "run-open-problems-priority.csv", priority_runner, RUNNER_COLUMNS)
    write_csv(output_dir / "run-open-problems-second-tier.csv", second_tier_runner, RUNNER_COLUMNS)

    samples = choose_samples(enriched, args.sample_per_source)
    write_csv(output_dir / "codex-source-samples.csv", samples, OUTPUT_COLUMNS)
    write_csv(output_dir / "run-codex-source-samples.csv", [runner_row(row) for row in samples], RUNNER_COLUMNS)

    by_source: dict[str, list[dict[str, str]]] = {}
    for row in samples:
        by_source.setdefault(row["source"], []).append(row)
    samples_dir = output_dir / "samples-by-source"
    runner_samples_dir = output_dir / "runner-samples-by-source"
    samples_dir.mkdir(parents=True, exist_ok=True)
    runner_samples_dir.mkdir(parents=True, exist_ok=True)
    for source, source_rows in by_source.items():
        safe_source = re.sub(r"[^A-Za-z0-9_.-]+", "_", source) or "missing"
        write_csv(samples_dir / f"{safe_source}.csv", source_rows, OUTPUT_COLUMNS)
        write_csv(
            runner_samples_dir / f"{safe_source}.csv",
            [runner_row(row) for row in source_rows],
            RUNNER_COLUMNS,
        )

    skipped_completed_rows = len(rows) - len(pending)
    report = {
        "input_rows": len(rows),
        "completed_url_index_size": len(completed),
        "skipped_completed_rows": skipped_completed_rows,
        "pending_rows": len(pending),
        "priority_rows": len(priority),
        "second_tier_rows": len(second_tier),
        "sample_rows": len(samples),
        "priority_by_source": {},
        "second_tier_by_source": {},
        "target_kind_counts": {},
    }
    for row in priority:
        report["priority_by_source"][row["source"]] = report["priority_by_source"].get(row["source"], 0) + 1
    for row in second_tier:
        report["second_tier_by_source"][row["source"]] = report["second_tier_by_source"].get(row["source"], 0) + 1
    for row in enriched:
        report["target_kind_counts"][row["target_kind"]] = report["target_kind_counts"].get(row["target_kind"], 0) + 1

    (output_dir / "priority-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
