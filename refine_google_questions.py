#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import litellm
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = (
    "You are a science research assistant that refines open problems across all scientific "
    "disciplines — including mathematics, physics, biology, chemistry, computer science, "
    "and other fields — by consulting the original source document and related primary sources."
)

USER_PROMPT_TEMPLATE = """\
I will give you an open problem from a curated open-problems document along with the \
section/context it appears in and a direct quote from the source.

Your job is to look up the problem in the source document (and any primary sources it cites) \
and produce a highly complete, sharp, stand-alone formulation of the problem.

Problem ID: {problem_id}
Draft question: {question_text}
Section / context: {context_brief}
Source page: {page}
Source quote: {source_quote}
Is solved: {is_solved}

Instructions:

1. Locate the exact statement in the source document (or the primary source it cites).
   - Prefer the nearest official formulation in the document.
   - Do not replace it with a broader neighboring problem.

2. Read the statement and the nearby context that defines notation, scope, and hidden assumptions.
   - Identify all variables, operators, quantities, experimental conditions, model assumptions, \
and domain-specific terms a reader outside the field would need to understand and attempt the problem.
   - Note any known partial results or conditions under which the problem is already solved.

3. Evaluate how complete the draft question is on a 0 to 10 scale.
   - Say what is already correct.
   - List every missing or implicit detail needed to make it fully stand-alone and \
source-faithful.
   - Include discipline-specific definitions (e.g. mathematical objects, physical constants, \
biological entities, experimental constraints, scope restrictions, quantifiers) that a reader \
outside the field would need.

4. Rewrite the question as one refined, self-contained research question that is:
   - self-contained (no unexplained symbols, jargon, or implicit scope),
   - tightly scoped to the core open question,
   - as close as possible to the source's original intent,
   - not broader than the source,
   - not vague.

5. Give at most one alternate formulation only if the source itself explicitly proves or states \
the equivalence.
   - Do not invent variants.

6. Guardrails:
   - Do not broaden a specific narrow problem into a more general one unless the source \
explicitly treats that generalization as its main target.
   - Do not drift into side problems, variants, or adjacent subfields unless the draft \
explicitly asks for them.
   - Do not add speculative assumptions or remove source-critical restrictions (e.g. specific \
parameter ranges, experimental constraints, model assumptions).
   - Keep the result narrow.
   - The "refined_question" field must contain only plain text. Do not include any URLs, \
hyperlinks, DOIs, PDF references, or citations of any kind inside the refined question itself.

7. Support every nontrivial claim by citing the exact place in the document:
   - section name or number,
   - problem/conjecture/theorem/hypothesis label if available,
   - page number.

Output requirements:

Return ONLY a valid JSON object with the following fields:

- "target_in_source": string (exact label / location of the problem in the source document)
- "completeness_score": number (0-10)
- "correct_elements": string
- "missing_details": array of strings
- "refined_question": string
- "equivalent_formulation": string or null
- "justification": string
- "citations": array of objects with:
    - "section": string
    - "label": string
    - "page": string or number

Do NOT include any text outside the JSON.
Do NOT include markdown formatting.
Ensure the JSON is syntactically valid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refine open problems using LLM with web search.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/google-questions.json"),
        help="Collected questions JSON file (output of collect_google_questions.py).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/google-refined"),
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


def build_input(item: dict) -> list[dict]:
    evidence = item.get("evidence") or []
    first = evidence[0] if evidence else {}
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                problem_id=item["question_id"],
                question_text=item["question_text"],
                context_brief=item.get("context_brief", ""),
                page=first.get("page", "unknown"),
                source_quote=first.get("quote", item["question_text"]),
                is_solved=item.get("is_solved", False),
            ),
        },
    ]


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.index("\n")
        cleaned = cleaned[first_nl + 1 :]
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
) -> dict:
    question_id = item["question_id"]
    source_stem = Path(item.get("source_file", "unknown")).stem
    out_path = output_dir / f"{source_stem}__{question_id}.json"

    if out_path.exists():
        print(f"[{idx+1}/{total}] SKIP (exists) {out_path.name}")
        return json.loads(out_path.read_text())

    input_msgs = build_input(item)
    t0 = time.time()

    async with sem:
        print(f"[{idx+1}/{total}] START  {source_stem} / {question_id}")
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
            print(f"[{idx+1}/{total}] FAIL   {problem_id}  ({elapsed:.1f}s)")
            print(f"           {type(exc).__name__}: {exc}")
            return {
                "question_id": question_id,
                "source_file": item.get("source_file"),
                "_error": str(exc),
            }

    raw = extract_text_from_response(response)
    elapsed = time.time() - t0

    try:
        parsed = extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        parsed = {"_raw": raw, "_parse_error": True}

    result = {
        "question_id": question_id,
        "source_file": item.get("source_file"),
        "source_title": item.get("source_title"),
        "source_url": item.get("source_url"),
        "original_question": item["question_text"],
        "context_brief": item.get("context_brief", ""),
        "is_solved": item.get("is_solved", False),
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

    problems: list[dict] = json.loads(args.input.read_text())
    if args.top_n is not None:
        problems = problems[: args.top_n]

    print(f"Processing {len(problems)} problems  (model={args.model})")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)

    tasks = [
        refine_one(item, args.model, sem, args.output_dir, i, len(problems))
        for i, item in enumerate(problems)
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
