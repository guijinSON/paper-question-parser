#!/usr/bin/env python3
"""Aggregate reasoning keyword and deterministic counters by model."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from detect_halu_rules import count_reasoning_keywords


DEFAULT_INPUTS = (
    "eval_outputs/halu/problems-260514-openrouter.jsonl",
    "eval_outputs/halu/problems-260515-openrouter.jsonl",
)

BENCHMARK_ORDER = (
    "AIME",
    "HLE-Verified",
    "math_sciencebench",
    "open_problems",
)

AIME_SOURCES = {
    "HuggingFaceH4/aime_2024",
    "MathArena/aime_2025",
    "MathArena/aime_2026",
}

COUNTER_EXPLANATIONS = {
    "hedging": "The trace uses weak-confidence language such as maybe, perhaps, probably, unclear, not sure, or I think.",
    "self_correction": "The trace revises itself or flags a check, using markers like wait, actually, recheck, double check, or that cannot be.",
    "give_up": "The trace says it is stuck, out of time, at a dead end, or cannot solve before producing or approaching an answer.",
    "unproven_claim": "The trace makes assertive shortcuts such as clearly, obviously, by symmetry, it can be shown, must be, or should be.",
    "incomplete_derivation": "The trace explicitly skips or omits derivation, says it will not compute something, or says the computation is too long.",
    "formula_memory": "The trace relies on remembered formulas or admits not remembering an exact formula.",
    "source_reference": "The trace mentions source objects or databases such as paper, book, arxiv, doi, wikipedia, mathworld, oeis, stackexchange, or aops.",
    "unsupported": "The trace invokes remembered or known-result language without deriving it, such as known result, well-known, I recall, or I remember.",
    "truncated_no_answer": "Deterministic check: the output ended by length or truncation and no final-answer candidate was found.",
    "arithmetic_final_sum_check": "Deterministic check: simple final-sum arithmetic is inconsistent, such as m=100, n=13, then m+n=114.",
    "fraction_sum_check": "Deterministic check: a final fraction m/n is paired with an m+n claim that does not equal numerator plus denominator.",
}

COUNTER_EXAMPLES = {
    "hedging": ["maybe", "probably", "not sure"],
    "self_correction": ["wait", "actually", "double check"],
    "give_up": ["I'm stuck", "given the time", "too complex"],
    "unproven_claim": ["clearly", "obviously", "it can be shown"],
    "incomplete_derivation": ["skip the calculation", "not compute", "too long to compute"],
    "formula_memory": ["I don't remember", "from memory", "not sure of the formula"],
    "source_reference": ["paper", "book", "arxiv"],
    "unsupported": ["known result", "well-known", "I recall"],
    "truncated_no_answer": ["finish_reason=length", "no final-answer candidate"],
    "arithmetic_final_sum_check": ["m=100, n=13, m+n=114"],
    "fraction_sum_check": ["100/13, m+n=114"],
}


def iter_jsonl(paths: list[Path]):
    for path in paths:
        with path.open() as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                yield path, line_no, row


def model_name(row: dict[str, Any]) -> str:
    return row.get("provider_model") or row.get("openrouter_model") or row.get("model") or "unknown"


def benchmark_label(source: str | None) -> str:
    if source in AIME_SOURCES:
        return "AIME"
    if source == "skylenage-ai/HLE-Verified":
        return "HLE-Verified"
    if source in {"math_sciencebench", "open_problems"}:
        return source
    return source or "unknown"


def benchmark_sort_key(label: str) -> tuple[int, str]:
    try:
        return BENCHMARK_ORDER.index(label), label
    except ValueError:
        return 99, label


def benchmark_slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def short_model(name: str) -> str:
    aliases = {
        "deepseek/deepseek-r1": "deepseek-r1",
        "deepseek/deepseek-v4-pro-20260423": "deepseek-v4-pro",
        "moonshotai/kimi-k2": "kimi-k2",
        "moonshotai/kimi-k2.6-20260420": "kimi-k2.6",
    }
    if name in aliases:
        return aliases[name]
    if "/" in name:
        name = name.split("/", 1)[1]
    name = name.replace("-20260224", "").replace("-20260420", "")
    name = name.replace("-04-28", "").replace("-20260216", "").replace("-20260310", "")
    return name


def provider_label(name: str) -> str:
    provider = name.split("/", 1)[0] if "/" in name else "unknown"
    return {
        "deepseek": "DeepSeek",
        "qwen": "Qwen",
        "moonshotai": "Moonshot",
    }.get(provider, provider)


def model_size_b(name: str) -> int | None:
    match = re.search(r"(\d+)b(?:-|$)", name.lower())
    if not match:
        return None
    return int(match.group(1))


def model_sort_key(name: str) -> tuple[int, int, str, str]:
    provider = name.split("/", 1)[0] if "/" in name else "unknown"
    provider_rank = {
        "deepseek": 0,
        "qwen": 1,
        "moonshotai": 2,
    }.get(provider, 99)

    short = short_model(name)
    size = model_size_b(short)
    size_rank = size if size is not None else 10_000

    # Keep same-size Qwen variants adjacent while still distinguishing family.
    family_rank = "0" if "qwen3-" in short else "1" if "qwen3.5-" in short else "2"
    if provider == "deepseek":
        size_rank = 0 if "r1" in short else 1
    if provider == "moonshotai":
        size_rank = 0 if short == "kimi-k2" else 1

    return provider_rank, size_rank, family_rank, short


def ordered_models(rows_by_model: Counter[str]) -> list[str]:
    return sorted(rows_by_model, key=model_sort_key)


def comparison_cluster_label(name: str) -> str:
    provider = name.split("/", 1)[0] if "/" in name else "unknown"
    if provider == "deepseek":
        return "DeepSeek"
    if provider == "moonshotai":
        return "Moonshot"
    if provider != "qwen":
        return provider_label(name)

    size = model_size_b(short_model(name))
    if size is None:
        return "Qwen"
    if size <= 10:
        return "Qwen 8-9B"
    if size <= 16:
        return "Qwen 14B"
    if size <= 40:
        return "Qwen 27-35B"
    if size <= 160:
        return "Qwen 122B"
    if size <= 260:
        return "Qwen 235B"
    return "Qwen 397B"


def comparison_runs(models: list[str]) -> list[tuple[int, int, str]]:
    runs: list[tuple[int, int, str]] = []
    start = 0
    while start < len(models):
        label = comparison_cluster_label(models[start])
        end = start + 1
        while end < len(models) and comparison_cluster_label(models[end]) == label:
            end += 1
        runs.append((start, end, label))
        start = end
    return runs


def model_family_label(name: str) -> str:
    provider = name.split("/", 1)[0] if "/" in name else "unknown"
    short = short_model(name)
    if provider == "deepseek":
        return "ds"
    if provider == "moonshotai" or short.startswith("kimi-"):
        return "kimi"
    if short.startswith("qwen3.5-"):
        return "q3.5"
    if short.startswith("qwen3-"):
        return "q3"
    return provider_label(name)


def model_family_sort_key(name: str) -> tuple[int, int, str]:
    family = model_family_label(name)
    family_rank = {
        "ds": 0,
        "kimi": 1,
        "q3": 2,
        "q3.5": 3,
    }.get(family, 99)
    size = model_size_b(short_model(name))
    return family_rank, size if size is not None else 10_000, short_model(name)


def ordered_models_by_family(rows_by_model: Counter[str]) -> list[str]:
    return sorted(rows_by_model, key=model_family_sort_key)


def family_runs(models: list[str]) -> list[tuple[int, int, str]]:
    runs: list[tuple[int, int, str]] = []
    start = 0
    while start < len(models):
        label = model_family_label(models[start])
        end = start + 1
        while end < len(models) and model_family_label(models[end]) == label:
            end += 1
        runs.append((start, end, label))
        start = end
    return runs


def aggregate(paths: list[Path], tail_chars: int) -> tuple[dict[str, Any], list[str]]:
    rows_by_model: Counter[str] = Counter()
    analysis_chars_by_model: Counter[str] = Counter()
    reasoning_chars_by_model: Counter[str] = Counter()
    total_by_model_group: dict[str, Counter[str]] = defaultdict(Counter)
    hit_by_model_group: dict[str, Counter[str]] = defaultdict(Counter)
    source_by_model: dict[str, Counter[str]] = defaultdict(Counter)
    rows_by_model_benchmark: Counter[tuple[str, str]] = Counter()
    analysis_chars_by_model_benchmark: Counter[tuple[str, str]] = Counter()
    reasoning_chars_by_model_benchmark: Counter[tuple[str, str]] = Counter()
    total_by_model_benchmark_group: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    hit_by_model_benchmark_group: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    group_order: list[str] | None = None

    for _path, _line_no, row in iter_jsonl(paths):
        model = model_name(row)
        source = row.get("source") or "unknown"
        benchmark = benchmark_label(source)
        model_benchmark = (model, benchmark)
        source_by_model[model][source] += 1
        rows_by_model[model] += 1
        rows_by_model_benchmark[model_benchmark] += 1
        counted = count_reasoning_keywords(row, tail_chars=tail_chars)
        analysis_chars_by_model[model] += counted["analysis_len"]
        reasoning_chars_by_model[model] += counted["reasoning_len"]
        analysis_chars_by_model_benchmark[model_benchmark] += counted["analysis_len"]
        reasoning_chars_by_model_benchmark[model_benchmark] += counted["reasoning_len"]
        counts = dict(counted["keyword_counts"])
        counts.update(counted.get("deterministic_check_counts", {}))
        if group_order is None:
            group_order = list(counts)
        for group, count in counts.items():
            total_by_model_group[model][group] += count
            if count > 0:
                hit_by_model_group[model][group] += 1
            total_by_model_benchmark_group[model_benchmark][group] += count
            if count > 0:
                hit_by_model_benchmark_group[model_benchmark][group] += 1

    data = {
        "rows_by_model": rows_by_model,
        "analysis_chars_by_model": analysis_chars_by_model,
        "reasoning_chars_by_model": reasoning_chars_by_model,
        "total_by_model_group": total_by_model_group,
        "hit_by_model_group": hit_by_model_group,
        "source_by_model": source_by_model,
        "rows_by_model_benchmark": rows_by_model_benchmark,
        "analysis_chars_by_model_benchmark": analysis_chars_by_model_benchmark,
        "reasoning_chars_by_model_benchmark": reasoning_chars_by_model_benchmark,
        "total_by_model_benchmark_group": total_by_model_benchmark_group,
        "hit_by_model_benchmark_group": hit_by_model_benchmark_group,
    }
    return data, group_order or []


def available_benchmarks(data: dict[str, Any]) -> list[str]:
    labels = {benchmark for _model, benchmark in data["rows_by_model_benchmark"]}
    return sorted(labels, key=benchmark_sort_key)


def benchmark_metric_data(data: dict[str, Any], benchmark: str) -> dict[str, Any]:
    rows_by_model: Counter[str] = Counter()
    analysis_chars_by_model: Counter[str] = Counter()
    reasoning_chars_by_model: Counter[str] = Counter()
    total_by_model_group: dict[str, Counter[str]] = defaultdict(Counter)
    hit_by_model_group: dict[str, Counter[str]] = defaultdict(Counter)

    for (model, bench), rows in data["rows_by_model_benchmark"].items():
        if bench != benchmark:
            continue
        key = (model, bench)
        rows_by_model[model] = rows
        analysis_chars_by_model[model] = data["analysis_chars_by_model_benchmark"][key]
        reasoning_chars_by_model[model] = data["reasoning_chars_by_model_benchmark"][key]
        total_by_model_group[model] = data["total_by_model_benchmark_group"][key]
        hit_by_model_group[model] = data["hit_by_model_benchmark_group"][key]

    return {
        "rows_by_model": rows_by_model,
        "analysis_chars_by_model": analysis_chars_by_model,
        "reasoning_chars_by_model": reasoning_chars_by_model,
        "total_by_model_group": total_by_model_group,
        "hit_by_model_group": hit_by_model_group,
        "source_by_model": defaultdict(Counter),
    }


def write_long_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    rows_by_model: Counter[str] = data["rows_by_model"]
    analysis_chars: Counter[str] = data["analysis_chars_by_model"]
    totals = data["total_by_model_group"]
    hits = data["hit_by_model_group"]
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "provider_model",
            "provider",
            "short_model",
            "size_b",
            "rows",
            "analysis_chars",
            "keyword_group",
            "total_count",
            "row_hits",
            "row_hit_rate",
            "mean_count_per_row",
            "count_per_10k_analysis_chars",
        ])
        for model in ordered_models(rows_by_model):
            rows = rows_by_model[model]
            chars = analysis_chars[model]
            for group in groups:
                total = totals[model][group]
                hit = hits[model][group]
                writer.writerow([
                    model,
                    provider_label(model),
                    short_model(model),
                    model_size_b(short_model(model)) or "",
                    rows,
                    chars,
                    group,
                    total,
                    hit,
                    f"{hit / rows:.6f}" if rows else "0",
                    f"{total / rows:.6f}" if rows else "0",
                    f"{total / chars * 10000:.6f}" if chars else "0",
                ])


def write_wide_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    rows_by_model: Counter[str] = data["rows_by_model"]
    hits = data["hit_by_model_group"]
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["provider_model", "provider", "short_model", "size_b", "rows", *groups])
        for model in ordered_models(rows_by_model):
            rows = rows_by_model[model]
            writer.writerow([
                model,
                provider_label(model),
                short_model(model),
                model_size_b(short_model(model)) or "",
                rows,
                *[f"{hits[model][group] / rows:.6f}" if rows else "0" for group in groups],
            ])


def write_normalized_wide_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    rows_by_model: Counter[str] = data["rows_by_model"]
    analysis_chars: Counter[str] = data["analysis_chars_by_model"]
    totals = data["total_by_model_group"]
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["provider_model", "provider", "short_model", "size_b", "rows", "analysis_chars", *groups])
        for model in ordered_models(rows_by_model):
            chars = analysis_chars[model]
            writer.writerow([
                model,
                provider_label(model),
                short_model(model),
                model_size_b(short_model(model)) or "",
                rows_by_model[model],
                chars,
                *[f"{totals[model][group] / chars * 10000:.6f}" if chars else "0" for group in groups],
            ])


def write_benchmark_long_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    rows_by_model = data["rows_by_model"]
    rows_by_model_benchmark = data["rows_by_model_benchmark"]
    analysis_chars = data["analysis_chars_by_model_benchmark"]
    totals = data["total_by_model_benchmark_group"]
    hits = data["hit_by_model_benchmark_group"]
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "benchmark",
            "provider_model",
            "provider",
            "short_model",
            "size_b",
            "rows",
            "analysis_chars",
            "keyword_group",
            "total_count",
            "row_hits",
            "row_hit_rate",
            "mean_count_per_row",
            "count_per_10k_analysis_chars",
        ])
        for benchmark in available_benchmarks(data):
            for model in ordered_models(rows_by_model):
                key = (model, benchmark)
                rows = rows_by_model_benchmark[key]
                if not rows:
                    continue
                chars = analysis_chars[key]
                for group in groups:
                    total = totals[key][group]
                    hit = hits[key][group]
                    writer.writerow([
                        benchmark,
                        model,
                        provider_label(model),
                        short_model(model),
                        model_size_b(short_model(model)) or "",
                        rows,
                        chars,
                        group,
                        total,
                        hit,
                        f"{hit / rows:.6f}" if rows else "0",
                        f"{total / rows:.6f}" if rows else "0",
                        f"{total / chars * 10000:.6f}" if chars else "0",
                    ])


def write_benchmark_wide_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    rows_by_model = data["rows_by_model"]
    rows_by_model_benchmark = data["rows_by_model_benchmark"]
    hits = data["hit_by_model_benchmark_group"]
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["benchmark", "provider_model", "provider", "short_model", "size_b", "rows", *groups])
        for benchmark in available_benchmarks(data):
            for model in ordered_models(rows_by_model):
                key = (model, benchmark)
                rows = rows_by_model_benchmark[key]
                if not rows:
                    continue
                writer.writerow([
                    benchmark,
                    model,
                    provider_label(model),
                    short_model(model),
                    model_size_b(short_model(model)) or "",
                    rows,
                    *[f"{hits[key][group] / rows:.6f}" if rows else "0" for group in groups],
                ])


def write_benchmark_normalized_wide_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    rows_by_model = data["rows_by_model"]
    rows_by_model_benchmark = data["rows_by_model_benchmark"]
    analysis_chars = data["analysis_chars_by_model_benchmark"]
    totals = data["total_by_model_benchmark_group"]
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["benchmark", "provider_model", "provider", "short_model", "size_b", "rows", "analysis_chars", *groups])
        for benchmark in available_benchmarks(data):
            for model in ordered_models(rows_by_model):
                key = (model, benchmark)
                rows = rows_by_model_benchmark[key]
                if not rows:
                    continue
                chars = analysis_chars[key]
                writer.writerow([
                    benchmark,
                    model,
                    provider_label(model),
                    short_model(model),
                    model_size_b(short_model(model)) or "",
                    rows,
                    chars,
                    *[f"{totals[key][group] / chars * 10000:.6f}" if chars else "0" for group in groups],
                ])


def write_benchmark_trend_csv(out_path: Path, data: dict[str, Any], groups: list[str]) -> None:
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "metric",
            "benchmark",
            "keyword_group",
            "deepseek_delta",
            "kimi_delta",
            "qwen_delta",
            "mean_delta",
        ])
        for metric in ("row_hit_rate", "per_10k_chars"):
            for benchmark in available_benchmarks(data):
                bench_data = benchmark_metric_data(data, benchmark)
                for row in _comparison_deltas(bench_data, groups, metric):
                    writer.writerow([
                        metric,
                        benchmark,
                        row["group"],
                        f"{row['deltas']['DeepSeek']:.6f}",
                        f"{row['deltas']['Kimi']:.6f}",
                        f"{row['deltas']['Qwen']:.6f}",
                        f"{row['mean_delta']:.6f}",
                    ])


def write_source_csv(out_path: Path, data: dict[str, Any]) -> None:
    rows_by_model: Counter[str] = data["rows_by_model"]
    sources = sorted({source for counts in data["source_by_model"].values() for source in counts})
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["provider_model", "provider", "short_model", "size_b", "rows", *sources])
        for model in ordered_models(rows_by_model):
            writer.writerow([
                model,
                provider_label(model),
                short_model(model),
                model_size_b(short_model(model)) or "",
                rows_by_model[model],
                *[data["source_by_model"][model][source] for source in sources],
            ])


def color_for_rate(rate: float) -> str:
    # White -> blue, chosen to be readable on a light background.
    rate = max(0.0, min(1.0, rate))
    r = round(247 - 210 * rate)
    g = round(250 - 120 * rate)
    b = round(255 - 20 * rate)
    return f"#{r:02x}{g:02x}{b:02x}"


def max_metric_value(data: dict[str, Any], groups: list[str], metric: str) -> float:
    rows_by_model: Counter[str] = data["rows_by_model"]
    hits = data["hit_by_model_group"]
    totals = data["total_by_model_group"]
    analysis_chars = data["analysis_chars_by_model"]
    values = []
    for model in rows_by_model:
        for group in groups:
            if metric == "row_hit_rate":
                values.append(hits[model][group] / rows_by_model[model] if rows_by_model[model] else 0)
            elif metric == "per_10k_chars":
                values.append(totals[model][group] / analysis_chars[model] * 10000 if analysis_chars[model] else 0)
            else:
                raise ValueError(f"unknown metric: {metric}")
    return max(values) if values else 1.0


def metric_value(data: dict[str, Any], model: str, group: str, metric: str) -> float:
    rows_by_model: Counter[str] = data["rows_by_model"]
    hits = data["hit_by_model_group"]
    totals = data["total_by_model_group"]
    analysis_chars = data["analysis_chars_by_model"]
    if metric == "row_hit_rate":
        return hits[model][group] / rows_by_model[model] if rows_by_model[model] else 0
    if metric == "per_10k_chars":
        return totals[model][group] / analysis_chars[model] * 10000 if analysis_chars[model] else 0
    raise ValueError(f"unknown metric: {metric}")


def write_heatmap_svg(
    out_path: Path,
    data: dict[str, Any],
    groups: list[str],
    metric: str = "row_hit_rate",
    grouping: str = "comparison",
    counter_label: str = "counter",
    scope_label: str = "",
) -> None:
    rows_by_model: Counter[str] = data["rows_by_model"]
    if grouping == "comparison":
        models = ordered_models(rows_by_model)
        runs = comparison_runs(models)
        title_suffix = "comparison pair"
        grouping_text = "Models are adjacent columns; Qwen is grouped by nearby size."
    elif grouping == "family":
        models = ordered_models_by_family(rows_by_model)
        runs = family_runs(models)
        title_suffix = "model family"
        grouping_text = "Models are adjacent columns grouped as ds, kimi, q3, and q3.5."
    else:
        raise ValueError(f"unknown grouping: {grouping}")
    max_value = max_metric_value(data, groups, metric)
    title = (
        f"Reasoning {counter_label} row-hit rate by {title_suffix}"
        if metric == "row_hit_rate"
        else f"Reasoning {counter_label} counts per 10k output chars by {title_suffix}"
    )
    if scope_label:
        title = f"{scope_label}: {title}"
    subtitle = (
        "Cell value = fraction of model rows where keyword group appeared at least once."
        if metric == "row_hit_rate"
        else "Cell value = total keyword matches per 10,000 analyzed output characters."
    )

    cell_w = 72
    cell_h = 30
    left_w = 190
    top_h = 220
    right_pad = 34
    bottom_pad = 40
    width = left_w + cell_w * len(models) + right_pad
    height = top_h + cell_h * len(groups) + bottom_pad

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;font-size:12px;fill:#172033}.small{font-size:10px;fill:#526070}.title{font-size:16px;font-weight:700}</style>',
        f'<text class="title" x="16" y="24">{html.escape(title)}</text>',
        f'<text class="small" x="16" y="44">{html.escape(subtitle)} {html.escape(grouping_text)}</text>',
    ]

    for start, end, label in runs:
        x0 = left_w + start * cell_w
        x1 = left_w + end * cell_w
        if start > 0:
            parts.append(f'<line x1="{x0}" x2="{x0}" y1="58" y2="{height - bottom_pad}" stroke="#7b8794" stroke-width="1.4"/>')
        parts.append(f'<text class="small" x="{(x0 + x1) / 2:.1f}" y="72" text-anchor="middle">{html.escape(label)}</text>')
        parts.append(f'<line x1="{x0 + 4}" x2="{x1 - 4}" y1="80" y2="80" stroke="#b8c0cc" stroke-width="1"/>')

    for mi, model in enumerate(models):
        x = left_w + mi * cell_w + cell_w / 2
        parts.append(f'<g transform="translate({x:.1f},{top_h - 16}) rotate(-52)"><text text-anchor="start">{html.escape(short_model(model))}</text></g>')
        parts.append(f'<text class="small" x="{x:.1f}" y="{top_h - 4}" text-anchor="middle">n={rows_by_model[model]}</text>')

    for gi, group in enumerate(groups):
        y = top_h + gi * cell_h
        parts.append(f'<text x="14" y="{y + 19}" text-anchor="start">{html.escape(group.replace("_", " "))}</text>')
        for mi, model in enumerate(models):
            x = left_w + mi * cell_w
            value = metric_value(data, model, group, metric)
            fill = color_for_rate(value / max_value if max_value else 0)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{fill}" stroke="#e5eaf0"/>')
            label = f"{value:.2f}" if metric == "row_hit_rate" else f"{value:.1f}"
            parts.append(f'<text class="small" x="{x + cell_w / 2:.1f}" y="{y + 18}" text-anchor="middle">{label}</text>')

    parts.append("</svg>")
    out_path.write_text("\n".join(parts))


def write_heatmap_png(
    out_path: Path,
    data: dict[str, Any],
    groups: list[str],
    metric: str = "row_hit_rate",
    grouping: str = "comparison",
    counter_label: str = "counter",
    scope_label: str = "",
) -> None:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as exc:
        print(f"skipped PNG heatmap; matplotlib unavailable: {exc}")
        return

    rows_by_model: Counter[str] = data["rows_by_model"]
    if grouping == "comparison":
        models = ordered_models(rows_by_model)
        runs = comparison_runs(models)
        title_suffix = "comparison pair"
    elif grouping == "family":
        models = ordered_models_by_family(rows_by_model)
        runs = family_runs(models)
        title_suffix = "model family"
    else:
        raise ValueError(f"unknown grouping: {grouping}")
    values = np.array([
        [metric_value(data, model, group, metric) for model in models]
        for group in groups
    ])
    max_value = max_metric_value(data, groups, metric)
    title = (
        f"Reasoning {counter_label} row-hit rate by {title_suffix}"
        if metric == "row_hit_rate"
        else f"Reasoning {counter_label} counts per 10k output chars by {title_suffix}"
    )
    if scope_label:
        title = f"{scope_label}: {title}"
    colorbar_label = "row-hit rate" if metric == "row_hit_rate" else "count per 10k chars"

    fig_w = max(13, len(models) * 0.9)
    fig_h = max(8, len(groups) * 0.36)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=180)
    im = ax.imshow(values, cmap="Blues", vmin=0, vmax=max_value if max_value else 1, aspect="auto")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([short_model(model) for model in models], rotation=50, ha="right", fontsize=8)
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([group.replace("_", " ") for group in groups], fontsize=8)
    ax.set_title(title, fontsize=12, weight="bold")
    ax.set_xlabel("Model comparison columns")
    ax.set_ylabel(counter_label.replace("_", " ").title())

    for start, end, label in runs:
        if start > 0:
            ax.axvline(start - 0.5, color="#7b8794", linewidth=1.2)
        center = (start + end - 1) / 2
        ax.text(center, -1.05, label, fontsize=8, color="#526070", ha="center", va="bottom", clip_on=False)

    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            val = values[i, j]
            norm = val / max_value if max_value else 0
            if norm >= 0.65 or (i % 3 == 0 and norm >= 0.2):
                label = f"{val:.2f}" if metric == "row_hit_rate" else f"{val:.1f}"
                ax.text(j, i, label, ha="center", va="center", fontsize=5.5, color="white" if norm > 0.55 else "#203040")

    colorbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    colorbar.set_label(colorbar_label)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _fmt_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_delta(value: float) -> str:
    return f"{value * 100:+.1f} pp"


def _fmt_per10k(value: float) -> str:
    return f"{value:.2f}"


def _metric_label(metric: str) -> str:
    if metric == "row_hit_rate":
        return "row-hit rate"
    if metric == "per_10k_chars":
        return "length-normalized density"
    raise ValueError(f"unknown metric: {metric}")


def _fmt_metric_delta(value: float, metric: str) -> str:
    if metric == "row_hit_rate":
        return _fmt_delta(value)
    if metric == "per_10k_chars":
        return f"{value:+.2f}"
    raise ValueError(f"unknown metric: {metric}")


def _html_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _example_keywords(group: str) -> str:
    examples = COUNTER_EXAMPLES.get(group, [])
    if not examples:
        return ""
    return ", ".join(f"<code>{html.escape(example)}</code>" for example in examples)


def _model_by_short(data: dict[str, Any], short: str) -> str:
    for model in data["rows_by_model"]:
        if short_model(model) == short:
            return model
    raise KeyError(short)


def _family_models(data: dict[str, Any], family: str) -> list[str]:
    return [model for model in data["rows_by_model"] if model_family_label(model) == family]


def _metric_for_models(data: dict[str, Any], models: list[str], group: str, metric: str) -> float:
    rows_by_model: Counter[str] = data["rows_by_model"]
    hits = data["hit_by_model_group"]
    totals = data["total_by_model_group"]
    analysis_chars = data["analysis_chars_by_model"]
    if metric == "row_hit_rate":
        rows = sum(rows_by_model[model] for model in models)
        return sum(hits[model][group] for model in models) / rows if rows else 0
    if metric == "per_10k_chars":
        chars = sum(analysis_chars[model] for model in models)
        return sum(totals[model][group] for model in models) / chars * 10000 if chars else 0
    raise ValueError(f"unknown metric: {metric}")


def _comparison_deltas(data: dict[str, Any], groups: list[str], metric: str) -> list[dict[str, Any]]:
    pairs = {
        "DeepSeek": ([_model_by_short(data, "deepseek-r1")], [_model_by_short(data, "deepseek-v4-pro")]),
        "Kimi": ([_model_by_short(data, "kimi-k2")], [_model_by_short(data, "kimi-k2.6")]),
        "Qwen": (_family_models(data, "q3"), _family_models(data, "q3.5")),
    }
    rows = []
    for group in groups:
        deltas = {}
        old_values = {}
        new_values = {}
        for label, (old_models, new_models) in pairs.items():
            old = _metric_for_models(data, old_models, group, metric)
            new = _metric_for_models(data, new_models, group, metric)
            old_values[label] = old
            new_values[label] = new
            deltas[label] = new - old
        rows.append(
            {
                "group": group,
                "deltas": deltas,
                "old_values": old_values,
                "new_values": new_values,
                "mean_delta": sum(deltas.values()) / len(deltas),
            }
        )
    return rows


def _consistent_rows(data: dict[str, Any], groups: list[str], metric: str, direction: str) -> list[dict[str, Any]]:
    rows = _comparison_deltas(data, groups, metric)
    if direction == "higher_newer":
        selected = [row for row in rows if all(delta > 0 for delta in row["deltas"].values())]
        return sorted(selected, key=lambda row: row["mean_delta"], reverse=True)
    if direction == "lower_newer":
        selected = [row for row in rows if all(delta < 0 for delta in row["deltas"].values())]
        return sorted(selected, key=lambda row: row["mean_delta"])
    raise ValueError(f"unknown direction: {direction}")


def _consistent_table(data: dict[str, Any], groups: list[str], metric: str, direction: str) -> str:
    rows = _consistent_rows(data, groups, metric, direction)
    direction_text = "higher" if direction == "higher_newer" else "lower"
    metric_text = _metric_label(metric)
    if not rows:
        return f"<p>No counter is consistently {direction_text} in newer models by {html.escape(metric_text)} across all three comparisons.</p>"
    return _html_table(
        ["Counter", "DS V4 - R1", "Kimi 2.6 - K2", "Qwen3.5 - Qwen3", "Mean delta"],
        [
            [
                f"<code>{html.escape(row['group'])}</code>",
                html.escape(_fmt_metric_delta(row["deltas"]["DeepSeek"], metric)),
                html.escape(_fmt_metric_delta(row["deltas"]["Kimi"], metric)),
                html.escape(_fmt_metric_delta(row["deltas"]["Qwen"], metric)),
                html.escape(_fmt_metric_delta(row["mean_delta"], metric)),
            ]
            for row in rows
        ],
    )


def _fmt_metric_abs(value: float, metric: str) -> str:
    if metric == "row_hit_rate":
        return f"{value * 100:.1f} pp"
    if metric == "per_10k_chars":
        return f"{value:.2f}"
    raise ValueError(f"unknown metric: {metric}")


def _blend_hex(base: tuple[int, int, int], target: tuple[int, int, int], amount: float) -> str:
    amount = max(0.0, min(1.0, amount))
    r = round(base[0] + (target[0] - base[0]) * amount)
    g = round(base[1] + (target[1] - base[1]) * amount)
    b = round(base[2] + (target[2] - base[2]) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _trend_cell(value: float, metric: str, max_abs: float) -> str:
    intensity = abs(value) / max_abs if max_abs else 0
    if value > 0:
        color = _blend_hex((255, 255, 255), (63, 131, 197), intensity)
    elif value < 0:
        color = _blend_hex((255, 255, 255), (213, 94, 0), intensity)
    else:
        color = "#ffffff"
    return f'<span class="trend-cell" style="background:{color}">{html.escape(_fmt_metric_delta(value, metric))}</span>'


def _benchmark_mean_delta_grid(data: dict[str, Any], groups: list[str], metric: str) -> dict[str, dict[str, float]]:
    grid: dict[str, dict[str, float]] = {}
    for benchmark in available_benchmarks(data):
        bench_data = benchmark_metric_data(data, benchmark)
        grid[benchmark] = {
            row["group"]: row["mean_delta"]
            for row in _comparison_deltas(bench_data, groups, metric)
        }
    return grid


def _benchmark_trend_table(data: dict[str, Any], groups: list[str], metric: str) -> str:
    benchmarks = available_benchmarks(data)
    grid = _benchmark_mean_delta_grid(data, groups, metric)
    values = [grid[benchmark][group] for benchmark in benchmarks for group in groups]
    max_abs = max((abs(value) for value in values), default=0)
    rows = []
    for group in groups:
        group_values = [grid[benchmark][group] for benchmark in benchmarks]
        spread = max(group_values) - min(group_values) if group_values else 0
        rows.append([
            f"<code>{html.escape(group)}</code>",
            *[_trend_cell(grid[benchmark][group], metric, max_abs) for benchmark in benchmarks],
            html.escape(_fmt_metric_abs(spread, metric)),
        ])
    return _html_table(["Counter", *benchmarks, "Benchmark spread"], rows)


def _benchmark_consistency_table(data: dict[str, Any], groups: list[str], metric: str) -> str:
    benchmarks = available_benchmarks(data)
    grid = _benchmark_mean_delta_grid(data, groups, metric)
    rows = []
    for group in groups:
        values = [grid[benchmark][group] for benchmark in benchmarks]
        if all(value > 0 for value in values):
            direction = "higher in newer"
        elif all(value < 0 for value in values):
            direction = "lower in newer"
        else:
            continue
        rows.append({
            "group": group,
            "direction": direction,
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        })
    rows.sort(key=lambda row: abs(row["mean"]), reverse=True)
    if not rows:
        return f"<p>No counter has the same newer-vs-older direction across all benchmarks by {html.escape(_metric_label(metric))}.</p>"
    return _html_table(
        ["Counter", "Direction across all benchmarks", "Mean benchmark delta", "Smallest delta", "Largest delta"],
        [
            [
                f"<code>{html.escape(row['group'])}</code>",
                html.escape(row["direction"]),
                html.escape(_fmt_metric_delta(row["mean"], metric)),
                html.escape(_fmt_metric_delta(row["min"], metric)),
                html.escape(_fmt_metric_delta(row["max"], metric)),
            ]
            for row in rows
        ],
    )


def _benchmark_sensitive_table(data: dict[str, Any], groups: list[str], metric: str) -> str:
    benchmarks = available_benchmarks(data)
    grid = _benchmark_mean_delta_grid(data, groups, metric)
    rows = []
    for group in groups:
        values = {benchmark: grid[benchmark][group] for benchmark in benchmarks}
        low_benchmark, low_value = min(values.items(), key=lambda item: item[1])
        high_benchmark, high_value = max(values.items(), key=lambda item: item[1])
        rows.append({
            "group": group,
            "spread": high_value - low_value,
            "low_benchmark": low_benchmark,
            "low_value": low_value,
            "high_benchmark": high_benchmark,
            "high_value": high_value,
        })
    rows.sort(key=lambda row: row["spread"], reverse=True)
    return _html_table(
        ["Counter", "Benchmark spread", "Lowest benchmark", "Highest benchmark"],
        [
            [
                f"<code>{html.escape(row['group'])}</code>",
                html.escape(_fmt_metric_abs(row["spread"], metric)),
                f"{html.escape(row['low_benchmark'])}: {html.escape(_fmt_metric_delta(row['low_value'], metric))}",
                f"{html.escape(row['high_benchmark'])}: {html.escape(_fmt_metric_delta(row['high_value'], metric))}",
            ]
            for row in rows[:6]
        ],
    )


def _family_lift_rows(data: dict[str, Any], groups: list[str], metric: str) -> dict[str, list[dict[str, Any]]]:
    families = ["ds", "kimi", "q3", "q3.5"]
    values = {
        family: {
            group: _metric_for_models(data, _family_models(data, family), group, metric)
            for group in groups
        }
        for family in families
    }
    out: dict[str, list[dict[str, Any]]] = {}
    for family in families:
        rows = []
        for group in groups:
            other_mean = sum(values[other][group] for other in families if other != family) / 3
            lift = values[family][group] - other_mean
            if lift > 0:
                rows.append({"group": group, "value": values[family][group], "lift": lift})
        out[family] = sorted(rows, key=lambda row: row["lift"], reverse=True)
    return out


def write_report_html(
    out_path: Path,
    row_hit_svg_path: Path,
    normalized_svg_path: Path,
    family_row_hit_svg_path: Path,
    family_normalized_svg_path: Path,
    benchmark_row_hit_svg_paths: dict[str, Path],
    benchmark_normalized_svg_paths: dict[str, Path],
    data: dict[str, Any],
    groups: list[str],
) -> None:
    row_hit_svg = row_hit_svg_path.read_text()
    normalized_svg = normalized_svg_path.read_text()
    family_row_hit_svg = family_row_hit_svg_path.read_text()
    family_normalized_svg = family_normalized_svg_path.read_text()
    benchmark_sections = []
    for benchmark in available_benchmarks(data):
        bench_data = benchmark_metric_data(data, benchmark)
        row_hit_path = benchmark_row_hit_svg_paths.get(benchmark)
        normalized_path = benchmark_normalized_svg_paths.get(benchmark)
        if row_hit_path is None or normalized_path is None:
            continue
        row_hit_svg_for_benchmark = row_hit_path.read_text()
        normalized_svg_for_benchmark = normalized_path.read_text()
        rows = sum(
            data["rows_by_model_benchmark"][(model, bench)]
            for model, bench in data["rows_by_model_benchmark"]
            if bench == benchmark
        )
        source_counts = Counter()
        for model_counts in data["source_by_model"].values():
            for source, count in model_counts.items():
                if benchmark_label(source) == benchmark:
                    source_counts[source] += count
        source_text = ", ".join(f"{source}: {count}" for source, count in sorted(source_counts.items()))
        benchmark_sections.append(
            f'<section class="benchmark-block"><h2>{html.escape(benchmark)}</h2>'
            f'<p class="note">Rows: {rows}. Source mix: {html.escape(source_text)}.</p>'
            '<p class="note">The four tables below mirror Pages 2 and 3 inside this benchmark: a counter is listed only when all three newer comparisons move in the same direction.</p>'
            '<h3>Newer-model higher counters: row-hit rate</h3>'
            f'{_consistent_table(bench_data, groups, "row_hit_rate", "higher_newer")}'
            '<h3>Newer-model higher counters: length-normalized density</h3>'
            f'{_consistent_table(bench_data, groups, "per_10k_chars", "higher_newer")}'
            '<h3>Newer-model lower counters: row-hit rate</h3>'
            f'{_consistent_table(bench_data, groups, "row_hit_rate", "lower_newer")}'
            '<h3>Newer-model lower counters: length-normalized density</h3>'
            f'{_consistent_table(bench_data, groups, "per_10k_chars", "lower_newer")}'
            '<h3>Row-hit rate by model</h3>'
            f"{row_hit_svg_for_benchmark}"
            '<h3>Length-normalized counts by model</h3>'
            f"{normalized_svg_for_benchmark}</section>"
        )
    benchmark_block = "\n".join(benchmark_sections)

    explanation_rows = [
        [
            f"<code>{html.escape(group)}</code>",
            html.escape("deterministic check" if group.endswith("_check") or group == "truncated_no_answer" else "keyword substring count"),
            html.escape(COUNTER_EXPLANATIONS.get(group, "")),
            _example_keywords(group),
        ]
        for group in groups
    ]

    higher_row_hit_table = _consistent_table(data, groups, "row_hit_rate", "higher_newer")
    higher_density_table = _consistent_table(data, groups, "per_10k_chars", "higher_newer")
    lower_row_hit_block = _consistent_table(data, groups, "row_hit_rate", "lower_newer")
    lower_density_block = _consistent_table(data, groups, "per_10k_chars", "lower_newer")
    benchmark_row_hit_trend_table = _benchmark_trend_table(data, groups, "row_hit_rate")
    benchmark_density_trend_table = _benchmark_trend_table(data, groups, "per_10k_chars")
    benchmark_row_hit_consistency_table = _benchmark_consistency_table(data, groups, "row_hit_rate")
    benchmark_density_consistency_table = _benchmark_consistency_table(data, groups, "per_10k_chars")
    benchmark_row_hit_sensitive_table = _benchmark_sensitive_table(data, groups, "row_hit_rate")
    benchmark_density_sensitive_table = _benchmark_sensitive_table(data, groups, "per_10k_chars")

    family_lifts = _family_lift_rows(data, groups, "row_hit_rate")
    family_sections = []
    for family, rows in family_lifts.items():
        family_sections.append(
            f"<h3>{html.escape(family)}</h3>"
            + _html_table(
                ["Counter", "Family row-hit", "Lift over other families"],
                [
                    [
                        f"<code>{html.escape(row['group'])}</code>",
                        html.escape(_fmt_rate(row["value"])),
                        html.escape(_fmt_delta(row["lift"])),
                    ]
                    for row in rows[:6]
                ],
            )
        )
    family_block = "\n".join(family_sections)

    page_links = "\n".join(
        [
            '<a href="#page-1">Page 1: counters</a>',
            '<a href="#page-2">Page 2: newer higher</a>',
            '<a href="#page-3">Page 3: newer lower</a>',
            '<a href="#page-4">Page 4: family signatures</a>',
            '<a href="#page-5">Page 5: benchmark split</a>',
            '<a href="#page-6">Page 6: benchmark trends</a>',
            '<a href="keyword_row_hit_rates_by_model.csv">row-hit CSV</a>',
            '<a href="keyword_counts_per_10k_chars_by_model.csv">normalized CSV</a>',
            '<a href="keyword_counts_by_model_long.csv">long CSV</a>',
            '<a href="keyword_row_hit_rates_by_model_benchmark.csv">benchmark row-hit CSV</a>',
            '<a href="keyword_newer_trends_by_benchmark.csv">benchmark trend CSV</a>',
        ]
    )
    report = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Halu Reasoning Counts</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 0; color: #172033; background: #f6f8fb; }}
a {{ color: #0b62b4; }}
.report {{ max-width: 1420px; margin: 0 auto; padding: 24px; }}
.nav {{ position: sticky; top: 0; z-index: 2; background: rgba(246,248,251,.96); padding: 12px 0; border-bottom: 1px solid #dce3ed; }}
.nav a {{ margin-right: 16px; white-space: nowrap; }}
.page {{ background: white; border: 1px solid #dce3ed; border-radius: 8px; padding: 24px; margin: 22px 0; page-break-after: always; }}
.benchmark-block {{ border-top: 1px solid #dce3ed; padding-top: 18px; margin-top: 28px; }}
.benchmark-block:first-of-type {{ border-top: 0; padding-top: 0; }}
.note {{ color: #526070; max-width: 980px; }}
.trend-cell {{ display: block; margin: -8px -10px; padding: 8px 10px; min-width: 72px; }}
table {{ border-collapse: collapse; width: 100%; margin: 14px 0 22px; font-size: 13px; }}
th, td {{ border: 1px solid #dce3ed; padding: 8px 10px; vertical-align: top; text-align: left; }}
th {{ background: #eef3f8; }}
code {{ background: #f2f5f8; padding: 1px 4px; border-radius: 4px; }}
svg {{ max-width: 100%; height: auto; }}
</style></head>
<body><div class="report">
<div class="nav">{page_links}</div>
<section class="page" id="page-1">
<h1>Page 1: Counter Explanations</h1>
<p class="note">Keyword counters are lowercase substring counts over the analyzed output tail. Row-hit rate means a row is counted once when a counter appears at least once. Length-normalized rate is total matches per 10,000 analyzed output characters.</p>
{_html_table(["Counter", "Type", "What It Means", "Example Keywords"], explanation_rows)}
</section>
<section class="page" id="page-2">
<h1>Page 2: Counters Consistently Higher In Newer Models</h1>
<p class="note">A counter appears here only if it increases for DeepSeek V4 over R1, Kimi K2.6 over K2, and Qwen3.5 family over Qwen3 family. Row-hit deltas are percentage points; length-normalized density deltas are keyword matches per 10,000 analyzed output characters.</p>
<p class="note"><strong>Interpretive note:</strong> A plausible explanation for the overall pattern is that newer models evolved toward more rigorous-looking reasoning traces. They tend to write fewer overt guesses, give-up statements, and hedges, while using more source-reference or formal support language. This can make traces look more disciplined even when the underlying answer is not necessarily more reliable.</p>
<h2>Row-hit rate</h2>
{higher_row_hit_table}
<h2>Length-normalized density</h2>
{higher_density_table}
<h2>Pair/size grouped row-hit heatmap</h2>
{row_hit_svg}
<h2>Pair/size grouped length-normalized heatmap</h2>
{normalized_svg}
</section>
<section class="page" id="page-3">
<h1>Page 3: Counters Consistently Lower In Newer Models</h1>
<p class="note">A counter appears here only if it decreases for DeepSeek V4 relative to R1, Kimi K2.6 relative to K2, and Qwen3.5 family relative to Qwen3 family. Row-hit deltas are percentage points; length-normalized density deltas are keyword matches per 10,000 analyzed output characters.</p>
<h2>Row-hit rate</h2>
{lower_row_hit_block}
<h2>Length-normalized density</h2>
{lower_density_block}
<h2>Pair/size grouped row-hit heatmap</h2>
{row_hit_svg}
<h2>Pair/size grouped length-normalized heatmap</h2>
{normalized_svg}
</section>
<section class="page" id="page-4">
<h1>Page 4: Model-Family-Specific High Counters</h1>
<p class="note">Each table shows counters where that family's row-hit rate is higher than the average of the other three families. Families are <code>ds</code>, <code>kimi</code>, <code>q3</code>, and <code>q3.5</code>.</p>
{family_block}
<h2>Family grouped row-hit heatmap</h2>
{family_row_hit_svg}
<h2>Family grouped length-normalized heatmap</h2>
{family_normalized_svg}
</section>
<section class="page" id="page-5">
<h1>Page 5: Benchmark Split</h1>
<p class="note">The same counters are split by benchmark source group. AIME combines <code>HuggingFaceH4/aime_2024</code>, <code>MathArena/aime_2025</code>, and <code>MathArena/aime_2026</code>; the other groups are <code>math_sciencebench</code>, <code>open_problems</code>, and <code>skylenage-ai/HLE-Verified</code>. This view shows how each model's counter behavior changes across benchmarks.</p>
{benchmark_block}
</section>
<section class="page" id="page-6">
<h1>Page 6: Trend Comparison Across Benchmarks</h1>
<p class="note">Each cell is the mean newer-minus-older delta across the three upgrade comparisons: DeepSeek V4 minus R1, Kimi K2.6 minus K2, and Qwen3.5 family minus Qwen3 family. Blue means the counter increases in newer models on that benchmark; orange means it decreases. Row-hit values are percentage points, while length-normalized values are keyword matches per 10,000 analyzed output characters.</p>
<h2>Row-hit trend by benchmark</h2>
{benchmark_row_hit_trend_table}
<h3>Counters with the same row-hit direction across all benchmarks</h3>
{benchmark_row_hit_consistency_table}
<h3>Most benchmark-sensitive row-hit trends</h3>
{benchmark_row_hit_sensitive_table}
<h2>Length-normalized trend by benchmark</h2>
{benchmark_density_trend_table}
<h3>Counters with the same length-normalized direction across all benchmarks</h3>
{benchmark_density_consistency_table}
<h3>Most benchmark-sensitive length-normalized trends</h3>
{benchmark_density_sensitive_table}
</section>
</div></body></html>
"""
    out_path.write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="*", type=Path, default=[Path(p) for p in DEFAULT_INPUTS])
    parser.add_argument("--out-dir", type=Path, default=Path("eval_outputs/halu/keyword_counts"))
    parser.add_argument("--tail-chars", type=int, default=24000)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    data, groups = aggregate(args.inputs, args.tail_chars)
    write_long_csv(args.out_dir / "keyword_counts_by_model_long.csv", data, groups)
    write_wide_csv(args.out_dir / "keyword_row_hit_rates_by_model.csv", data, groups)
    write_normalized_wide_csv(args.out_dir / "keyword_counts_per_10k_chars_by_model.csv", data, groups)
    write_benchmark_long_csv(args.out_dir / "keyword_counts_by_model_benchmark_long.csv", data, groups)
    write_benchmark_wide_csv(args.out_dir / "keyword_row_hit_rates_by_model_benchmark.csv", data, groups)
    write_benchmark_normalized_wide_csv(args.out_dir / "keyword_counts_per_10k_chars_by_model_benchmark.csv", data, groups)
    write_benchmark_trend_csv(args.out_dir / "keyword_newer_trends_by_benchmark.csv", data, groups)
    write_source_csv(args.out_dir / "source_mix_by_model.csv", data)
    row_hit_svg_path = args.out_dir / "keyword_row_hit_rates_by_model.svg"
    normalized_svg_path = args.out_dir / "keyword_counts_per_10k_chars_by_model.svg"
    family_row_hit_svg_path = args.out_dir / "keyword_row_hit_rates_by_model_family.svg"
    family_normalized_svg_path = args.out_dir / "keyword_counts_per_10k_chars_by_model_family.svg"
    benchmark_row_hit_svg_paths: dict[str, Path] = {}
    benchmark_normalized_svg_paths: dict[str, Path] = {}
    write_heatmap_svg(row_hit_svg_path, data, groups, metric="row_hit_rate")
    write_heatmap_svg(normalized_svg_path, data, groups, metric="per_10k_chars")
    write_heatmap_svg(family_row_hit_svg_path, data, groups, metric="row_hit_rate", grouping="family")
    write_heatmap_svg(family_normalized_svg_path, data, groups, metric="per_10k_chars", grouping="family")
    for benchmark in available_benchmarks(data):
        bench_data = benchmark_metric_data(data, benchmark)
        slug = benchmark_slug(benchmark)
        bench_row_hit_svg_path = args.out_dir / f"keyword_row_hit_rates_by_model_benchmark_{slug}.svg"
        bench_normalized_svg_path = args.out_dir / f"keyword_counts_per_10k_chars_by_model_benchmark_{slug}.svg"
        benchmark_row_hit_svg_paths[benchmark] = bench_row_hit_svg_path
        benchmark_normalized_svg_paths[benchmark] = bench_normalized_svg_path
        write_heatmap_svg(
            bench_row_hit_svg_path,
            bench_data,
            groups,
            metric="row_hit_rate",
            scope_label=benchmark,
        )
        write_heatmap_svg(
            bench_normalized_svg_path,
            bench_data,
            groups,
            metric="per_10k_chars",
            scope_label=benchmark,
        )
    write_heatmap_png(args.out_dir / "keyword_row_hit_rates_by_model.png", data, groups, metric="row_hit_rate")
    write_heatmap_png(args.out_dir / "keyword_counts_per_10k_chars_by_model.png", data, groups, metric="per_10k_chars")
    write_heatmap_png(args.out_dir / "keyword_row_hit_rates_by_model_family.png", data, groups, metric="row_hit_rate", grouping="family")
    write_heatmap_png(args.out_dir / "keyword_counts_per_10k_chars_by_model_family.png", data, groups, metric="per_10k_chars", grouping="family")
    for benchmark in available_benchmarks(data):
        bench_data = benchmark_metric_data(data, benchmark)
        slug = benchmark_slug(benchmark)
        write_heatmap_png(
            args.out_dir / f"keyword_row_hit_rates_by_model_benchmark_{slug}.png",
            bench_data,
            groups,
            metric="row_hit_rate",
            scope_label=benchmark,
        )
        write_heatmap_png(
            args.out_dir / f"keyword_counts_per_10k_chars_by_model_benchmark_{slug}.png",
            bench_data,
            groups,
            metric="per_10k_chars",
            scope_label=benchmark,
        )
    write_report_html(
        args.out_dir / "keyword_counts_report.html",
        row_hit_svg_path,
        normalized_svg_path,
        family_row_hit_svg_path,
        family_normalized_svg_path,
        benchmark_row_hit_svg_paths,
        benchmark_normalized_svg_paths,
        data,
        groups,
    )
    write_report_html(
        args.out_dir / "keyword_counter_analysis_report.html",
        row_hit_svg_path,
        normalized_svg_path,
        family_row_hit_svg_path,
        family_normalized_svg_path,
        benchmark_row_hit_svg_paths,
        benchmark_normalized_svg_paths,
        data,
        groups,
    )

    print(f"wrote {args.out_dir / 'keyword_counts_by_model_long.csv'}")
    print(f"wrote {args.out_dir / 'keyword_row_hit_rates_by_model.csv'}")
    print(f"wrote {args.out_dir / 'keyword_counts_per_10k_chars_by_model.csv'}")
    print(f"wrote {args.out_dir / 'keyword_counts_by_model_benchmark_long.csv'}")
    print(f"wrote {args.out_dir / 'keyword_row_hit_rates_by_model_benchmark.csv'}")
    print(f"wrote {args.out_dir / 'keyword_counts_per_10k_chars_by_model_benchmark.csv'}")
    print(f"wrote {args.out_dir / 'keyword_newer_trends_by_benchmark.csv'}")
    print(f"wrote {args.out_dir / 'source_mix_by_model.csv'}")
    print(f"wrote {args.out_dir / 'keyword_row_hit_rates_by_model.svg'}")
    print(f"wrote {args.out_dir / 'keyword_row_hit_rates_by_model.png'}")
    print(f"wrote {args.out_dir / 'keyword_counts_per_10k_chars_by_model.svg'}")
    print(f"wrote {args.out_dir / 'keyword_counts_per_10k_chars_by_model.png'}")
    print(f"wrote {args.out_dir / 'keyword_row_hit_rates_by_model_family.svg'}")
    print(f"wrote {args.out_dir / 'keyword_row_hit_rates_by_model_family.png'}")
    print(f"wrote {args.out_dir / 'keyword_counts_per_10k_chars_by_model_family.svg'}")
    print(f"wrote {args.out_dir / 'keyword_counts_per_10k_chars_by_model_family.png'}")
    for benchmark in available_benchmarks(data):
        slug = benchmark_slug(benchmark)
        print(f"wrote {args.out_dir / f'keyword_row_hit_rates_by_model_benchmark_{slug}.svg'}")
        print(f"wrote {args.out_dir / f'keyword_row_hit_rates_by_model_benchmark_{slug}.png'}")
        print(f"wrote {args.out_dir / f'keyword_counts_per_10k_chars_by_model_benchmark_{slug}.svg'}")
        print(f"wrote {args.out_dir / f'keyword_counts_per_10k_chars_by_model_benchmark_{slug}.png'}")
    print(f"wrote {args.out_dir / 'keyword_counts_report.html'}")
    print(f"wrote {args.out_dir / 'keyword_counter_analysis_report.html'}")


if __name__ == "__main__":
    main()
