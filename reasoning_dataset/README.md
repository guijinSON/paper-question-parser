# Reasoning Dataset Source

The source dataset used by `batch_trace_behavior_inserter.py` is:

```text
qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl
```

The complete JSONL is too large to store as one normal GitHub blob, so it is
checked in as contiguous byte chunks under:

```text
qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl.parts/
```

Reassemble it from the repository root with:

```bash
python reasoning_dataset/reassemble_filtered_without_dedup.py
```

The batch runner expects the reassembled file at:

```text
reasoning_dataset/qwen3-30b-a3b-250511-2249.filtered_without_dedup.jsonl
```
