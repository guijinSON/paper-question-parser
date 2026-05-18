#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path


MANIFEST = Path(
    "reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl.parts/manifest.json"
)
OUTPUT = Path("reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    total_bytes = 0

    with OUTPUT.open("wb") as out:
        for part in manifest["parts"]:
            path = Path(part["path"])
            chunk = path.read_bytes()
            if len(chunk) != part["bytes"]:
                raise ValueError(f"Part size mismatch for {path}")
            digest.update(chunk)
            total_bytes += len(chunk)
            out.write(chunk)

    if total_bytes != manifest["total_bytes"]:
        raise ValueError("Reassembled byte count does not match manifest")
    if digest.hexdigest() != manifest["sha256"]:
        raise ValueError("Reassembled sha256 does not match manifest")

    print(f"wrote {OUTPUT} ({total_bytes} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
