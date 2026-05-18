#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path


SOURCE = Path("reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl")
PART_DIR = Path(
    "reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl.parts"
)
PART_BYTES = 90 * 1024 * 1024


def main() -> int:
    PART_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total_bytes = 0
    part_paths: list[Path] = []

    with SOURCE.open("rb") as src:
        part_index = 0
        while True:
            chunk = src.read(PART_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            total_bytes += len(chunk)
            part_path = PART_DIR / f"part-{part_index:04d}.bin"
            part_path.write_bytes(chunk)
            part_paths.append(part_path)
            part_index += 1

    manifest = {
        "source": str(SOURCE),
        "part_dir": str(PART_DIR),
        "part_bytes": PART_BYTES,
        "total_bytes": total_bytes,
        "sha256": digest.hexdigest(),
        "parts": [
            {"path": str(path), "bytes": path.stat().st_size}
            for path in part_paths
        ],
    }
    (PART_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
