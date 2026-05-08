#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

import litellm
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = "You are a research assistant that writes precise, self-contained formulations of famous open problems in science and mathematics."

USER_PROMPT_TEMPLATE = """\
I will give you the name of a well-known open problem and its field/category.

Your job is to look up the problem (via Wikipedia or authoritative sources) and produce a highly complete, sharp, stand-alone formulation of the problem.

Problem name: {problem}
Field: {field}
Category: {category}

Instructions:

1. Look up the canonical formulation of this problem from Wikipedia or a primary mathematical/scientific source.
   - Prefer the exact statement as given in the authoritative source.
   - Do not replace it with a broader or weaker version.

2. Read the statement and the nearby context that defines notation, scope, and hidden assumptions.
   - Identify all variables, operators, and domain-specific terms needed to understand the question.
   - Note any known partial results or conditions under which the problem is solved.

3. Evaluate how precisely the problem name alone captures the actual problem on a 0 to 10 scale.
   - Say what is already implicit in the name.
   - List every detail needed to make it fully stand-alone.

4. Write the problem as one refined, self-contained research question that is:
   - self-contained (no unexplained symbols or jargon),
   - tightly scoped to the core open question,
   - faithful to the canonical formulation,
   - not broader or vaguer than the original.

5. Give at most one alternate formulation only if the source itself explicitly states an equivalence.
   - Do not invent variants.

6. Guardrails:
   - Do not broaden a specific problem into a more general one.
   - Do not add speculative assumptions or remove known constraints.
   - Keep the result narrow and precise.
   - The "refined_question" field must contain only plain text. Do not include any URLs, hyperlinks, DOIs, PDF references, Wikipedia links, or citations of any kind inside the refined question itself.

7. Support every nontrivial claim by citing the source:
   - Wikipedia article title or section,
   - or paper/book reference if applicable.

Output requirements:

Return ONLY a valid JSON object with the following fields:

- "problem": string (the original problem name)
- "field": string
- "category": string
- "source": string (primary source consulted, e.g. Wikipedia article title)
- "completeness_score": number (0-10, how much the name alone captures the problem)
- "missing_details": array of strings
- "refined_question": string
- "equivalent_formulation": string or null
- "justification": string
- "citations": array of objects with:
    - "source": string
    - "section": string
    - "label": string

Do NOT include any text outside the JSON.
Do NOT include markdown formatting.
Ensure the JSON is syntactically valid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refine Wikipedia open problems using LLM with web search.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/wikipedia_problems.jsonl"),
        help="Input JSONL file with problems.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/wikipedia-refined"),
        help="Directory to write per-problem refined JSON files.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="openai/gpt-5.4",
        help="litellm model identifier.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Only process the first N problems (for testing).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent API calls.",
    )
    return parser.parse_args()


def category_to_slug(category: str) -> str:
    slug = category.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:60]


def build_input(item: dict) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                problem=item["problem"],
                field=item.get("field", ""),
                category=item.get("category", ""),
            ),
        },
    ]


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.index("\n")
        cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def extract_text_from_response(response) -> str:
    output = _get(response, "output") or []
    for item in output:
        if _get(item, "type") == "message":
            for part in _get(item, "content") or []:
                if _get(part, "type") == "output_text":
                    return _get(part, "text") or ""
    return ""


async def refine_one(
    item: dict,
    model: str,
    sem: asyncio.Semaphore,
    output_dir: Path,
    idx: int,
    total: int,
    filename: str,
) -> dict:
    out_path = output_dir / filename

    if out_path.exists():
        print(f"[{idx+1}/{total}] SKIP (exists) {out_path.name}")
        return json.loads(out_path.read_text())

    input_msgs = build_input(item)
    t0 = time.time()

    async with sem:
        print(f"[{idx+1}/{total}] START  {item['problem']!r}")
        try:
            response = await litellm.aresponses(
                model=model,
                input=input_msgs,
                tools=[
                    {
                        "type": "web_search_preview",
                        "search_context_size": "medium",
                    }
                ],
                reasoning={"effort": "medium"},
            )
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"[{idx+1}/{total}] FAIL   {item['problem']!r}  ({elapsed:.1f}s)")
            print(f"           {type(exc).__name__}: {exc}")
            return {
                "problem": item["problem"],
                "_error": str(exc),
            }

    raw = extract_text_from_response(response)
    elapsed = time.time() - t0

    try:
        parsed = extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        parsed = {"_raw": raw, "_parse_error": True}

    result = {
        "problem": item["problem"],
        "field": item.get("field", ""),
        "category": item.get("category", ""),
        "solved": item.get("solved", None),
        "model": model,
        "elapsed_s": round(elapsed, 2),
        **parsed,
    }

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    status = "ERROR" if parsed.get("_parse_error") else "OK"
    print(f"[{idx+1}/{total}] {status}    {out_path.name}  ({elapsed:.1f}s)")
    return result


async def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    problems: list[dict] = [
        json.loads(line) for line in args.input.read_text().splitlines() if line.strip()
    ]
    if args.top_n is not None:
        problems = problems[: args.top_n]

    print(f"Processing {len(problems)} problems  (model={args.model})")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)

    # Assign per-category indices to build filenames like "millennium_prize_problems_001.json"
    category_counters: dict[str, int] = {}
    filenames: list[str] = []
    for item in problems:
        slug = category_to_slug(item.get("category", "uncategorized"))
        category_counters[slug] = category_counters.get(slug, 0) + 1
        filenames.append(f"{slug}_{category_counters[slug]:03d}.json")

    tasks = [
        refine_one(item, args.model, sem, args.output_dir, i, len(problems), fname)
        for i, (item, fname) in enumerate(zip(problems, filenames))
    ]
    results = await asyncio.gather(*tasks)

    successes = sum(
        1
        for r in results
        if isinstance(r, dict) and not r.get("_parse_error") and not r.get("_error")
    )
    errors = len(results) - successes
    print(f"\nDone. {successes} succeeded, {errors} failed/skipped.")


if __name__ == "__main__":
    asyncio.run(main())
