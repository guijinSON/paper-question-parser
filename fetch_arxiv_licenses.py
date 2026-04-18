#!/usr/bin/env python3
"""Fetch arXiv license info by scraping abs pages for all unique paper IDs."""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

import aiohttp

OUTPUT_PATH = Path("outputs/arxiv-licenses.json")
CONCURRENCY = 10
DELAY_BETWEEN = 0.3


def sanitized_id_to_api_id(arxiv_id: str) -> str:
    m = re.match(r"^(\d{4})[_](\d{4,5})$", arxiv_id)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    m = re.match(r"^(.+?)[-_](\d{5,7})$", arxiv_id)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return arxiv_id


def arxiv_id_to_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{sanitized_id_to_api_id(arxiv_id)}"


LICENSE_RE = re.compile(
    r'<a[^>]*href="(https?://[^"]*(?:creativecommons\.org|arxiv\.org/licenses)[^"]*)"[^>]*>.*?view\s+license',
    re.IGNORECASE | re.DOTALL,
)


async def fetch_one(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    arxiv_id: str,
    idx: int,
    total: int,
) -> tuple[str, dict]:
    url = arxiv_id_to_url(arxiv_id)
    async with sem:
        await asyncio.sleep(DELAY_BETWEEN)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                html = await resp.text()
        except Exception as exc:
            print(f"[{idx+1}/{total}] FAIL  {arxiv_id}  {type(exc).__name__}: {exc}")
            return arxiv_id, {"arxiv_url": url, "license_url": None, "error": str(exc)}

    m = LICENSE_RE.search(html)
    license_url = m.group(1) if m else None

    title_m = re.search(r"<title>\s*\[.*?\]\s*(.*?)\s*</title>", html, re.DOTALL)
    title = re.sub(r"\s+", " ", title_m.group(1).strip()) if title_m else None

    print(f"[{idx+1}/{total}] OK    {arxiv_id}  ->  {license_url}")
    return arxiv_id, {
        "arxiv_url": url,
        "title": title,
        "license_url": license_url,
    }


async def main() -> None:
    refined_dir = Path("outputs/parse-paper-fast-refined")
    seen_ids: set[str] = set()
    for f in refined_dir.glob("*.json"):
        data = json.loads(f.read_text())
        aid = data.get("arxiv_id")
        if aid:
            seen_ids.add(aid)

    unique_ids = sorted(seen_ids)
    print(f"Unique arXiv IDs: {len(unique_ids)}")

    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_one(session, sem, aid, i, len(unique_ids))
            for i, aid in enumerate(unique_ids)
        ]
        results = await asyncio.gather(*tasks)

    output: dict[str, dict] = {}
    for arxiv_id, info in results:
        output[arxiv_id] = info

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")

    found = sum(1 for v in output.values() if v.get("license_url"))
    print(f"\nDone. {found}/{len(unique_ids)} licenses found.")
    print(f"Saved to {OUTPUT_PATH}")

    licenses: dict[str, int] = {}
    for info in output.values():
        url = info.get("license_url") or "unknown"
        licenses[url] = licenses.get(url, 0) + 1
    print("\nLicense distribution:")
    for url, count in sorted(licenses.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {url}")


if __name__ == "__main__":
    asyncio.run(main())
