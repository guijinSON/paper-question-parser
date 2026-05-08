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

SYSTEM_PROMPT = "You are a science research assistant that refines draft research questions by consulting the original arXiv paper."

USER_PROMPT_TEMPLATE = """\
I will give you an arXiv paper ID and a draft question.

Your job is to read the paper itself and turn my draft into a highly complete, sharp, stand-alone research question that stays as close as possible to the paper's actual intent.

Paper to inspect:
arXiv:{arxiv_id}

Draft question:
{question_text}

Instructions:

1. Search the paper and identify the exact statement, conjecture, or open problem that my draft is trying to capture.
   - Prefer the nearest official formulation in the paper.
   - Do not replace it with a broader neighboring problem.

2. Read the exact statement and the nearby context that defines notation, scope, and hidden assumptions.
   - Check the introduction first.
   - Then check any proposition/theorem/conjecture/remark/hypothesis that supplies equivalent conditions, notation, or a more precise reformulation.

3. Evaluate how complete my draft question is on a 0 to 10 scale.
   - Say what is already correct.
   - List every missing or implicit detail needed to make it fully stand-alone and paper-faithful.
   - Include domain-specific definitions (e.g. variables, operators, experimental conditions, model assumptions, scope restrictions, quantifiers) that a reader outside the paper would need to understand and attempt the question.

4. Rewrite the question as one refined research question that is:
   - self-contained (no unexplained symbols, jargon, or implicit scope),
   - tightly scoped,
   - as close as possible to the paper's original intent,
   - not broader than the paper,
   - not vague.

5. Give at most one alternate formulation only if the paper itself explicitly proves the equivalence.
   - Do not invent new variants.
   - Do not generalize unless the paper itself does so in the exact nearby discussion.

6. Guardrails:
   - Do not broaden a specific narrow question into a more general problem unless the paper explicitly treats that generalization as its main target.
   - Do not drift into side problems, variants, or adjacent subfields unless my draft explicitly asks for them.
   - Do not add speculative assumptions or remove paper-critical restrictions (e.g. specific parameter ranges, experimental constraints, model assumptions).
   - Keep the result narrow.
   - The "refined_question" field must contain only plain text. Do not include any URLs, hyperlinks, DOIs, PDF references, arXiv links, or citations of any kind inside the refined question itself.

7. Support every nontrivial claim by citing the exact place in the paper:
   - section number,
   - conjecture/proposition/theorem/open problem number,
   - and page number if available.

Output requirements:

Return ONLY a valid JSON object.

The JSON must contain the following fields:

- "target_in_paper": string
- "completeness_score": number
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
        description="Refine parsed paper questions using LLM with web search.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/parse-paper-questions.json"),
        help="Input JSON file with collected questions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/parse-paper-fast-refined"),
        help="Directory to write per-question refined JSON files.",
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
        help="Only process the first N questions (for testing).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent API calls.",
    )
    return parser.parse_args()


def build_input(arxiv_id: str, question_text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(
                arxiv_id=arxiv_id,
                question_text=question_text,
            ),
        },
    ]


def extract_json(text: str) -> dict:
    """Try to parse the response as JSON, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.index("\n")
        cleaned = cleaned[first_nl + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def _get(obj, key):
    """Access a field by attribute or dict key."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def extract_text_from_response(response) -> str:
    """Pull the assistant text out of a Responses-API response object (dict or pydantic)."""
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
    arxiv_id = item["arxiv_id"]
    question_id = item.get("question_id", "unknown")
    out_path = output_dir / f"{arxiv_id}__{question_id}.json"

    if out_path.exists():
        print(f"[{idx+1}/{total}] SKIP (exists) {out_path.name}")
        return json.loads(out_path.read_text())

    input_msgs = build_input(arxiv_id, item["question_text"])
    t0 = time.time()

    async with sem:
        print(f"[{idx+1}/{total}] START  {arxiv_id} / {question_id}")
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
            print(
                f"[{idx+1}/{total}] FAIL   {arxiv_id} / {question_id}  ({elapsed:.1f}s)"
            )
            print(f"           {type(exc).__name__}: {exc}")
            return {
                "arxiv_id": arxiv_id,
                "question_id": question_id,
                "_error": str(exc),
            }

    raw = extract_text_from_response(response)
    elapsed = time.time() - t0

    try:
        parsed = extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        parsed = {"_raw": raw, "_parse_error": True}

    result = {
        "arxiv_id": arxiv_id,
        "question_id": question_id,
        "original_question": item["question_text"],
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

    questions: list[dict] = json.loads(args.input.read_text())
    if args.top_n is not None:
        questions = questions[: args.top_n]

    print(f"Processing {len(questions)} questions  (model={args.model})")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)

    tasks = [
        refine_one(item, args.model, sem, args.output_dir, i, len(questions))
        for i, item in enumerate(questions)
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
