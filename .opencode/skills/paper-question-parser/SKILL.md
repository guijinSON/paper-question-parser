---
name: paper-question-parser
description: "Parse one paper (local PDF path or arXiv URL), extract open/unsolved questions, rewrite them into self-contained form with evidence, dedupe, quality-gate, and auto-save structured JSON. Triggers: 'parse paper questions', 'extract open problems', 'unsolved questions from paper'."
---

# Paper Question Parser

You run a single-paper workflow to extract open/unsolved research questions from a survey-style paper and rewrite each into a self-contained, evidence-grounded question.

## Operating Contract

- Process exactly one paper per run.
- Accept either a local PDF path or a URL (arXiv `abs` or direct `pdf`).
- Do not ask the user to run scripts.
- Return STRICT JSON only (no prose) with keys: `accepted`, `needs_review`, `trace`.
- Auto-save the final JSON result to disk every run.

## Input Normalization

1. Read `$ARGUMENTS` and extract a single paper source.
2. If input is a local PDF path:
   - Verify the file exists.
   - Use that absolute path as `paper_path`.
3. If input is a URL:
   - If URL is `https://arxiv.org/abs/<id>`, convert to `https://arxiv.org/pdf/<id>.pdf`.
   - Download internally with Bash:
     - `mkdir -p .sisyphus/paper-question-parser/tmp`
     - `curl -L --fail "<pdf_url>" -o ".sisyphus/paper-question-parser/tmp/<paper_slug>.pdf"`
   - Use downloaded path as `paper_path`.

If input is invalid or cannot be downloaded, return:

```json
{
  "accepted": [],
  "needs_review": [
    {
      "id": "error_input",
      "reason": "invalid_or_unreadable_input",
      "question_text_raw": "",
      "evidence": []
    }
  ],
  "trace": [
    {
      "id": "error_input",
      "stage": "input",
      "notes": "Input could not be normalized to a readable PDF path.",
      "evidence_refs": []
    }
  ]
}
```

## Workflow Stages

### Stage 1: Map

Use `look_at(file_path=paper_path, goal=...)` to extract:

- section hierarchy (major sections and subsections)
- notation/definitions index
- theorem/proposition/lemma reference index (labels and where they appear)
- likely "open problems/questions" regions

Record this as `doc_map` in working memory and add a `trace` entry with stage `map`.

### Stage 2: Candidate Extraction (Recall-First)

Use `look_at(file_path=paper_path, goal=...)` to extract ALL explicit and implicit open problems/questions.

Extraction target:

- include markers like "Question", "Problem", "Open", "Unknown whether", "Is it true that"
- include implicit question statements that represent unresolved research problems
- for each candidate, capture:
  - raw question text (as close to source as possible)
  - page number(s)
  - verbatim supporting quote(s)

Add `trace` entries with stage `extract_candidates`.

### Stage 3: Self-Contained Rewrite (Precision-First)

For each candidate:

- rewrite into a standalone question understandable without the source paper
- resolve references like "Proposition 2.1" or "Section 3" only using evidence in the paper
- if required context is missing in evidence, do NOT guess; move item to `needs_review`

Add `trace` entries with stage `rewrite`.

### Stage 4: Dedupe

- merge near-duplicate rewritten questions
- preserve all evidence references from merged members in `trace`
- keep one canonical `id` per merged cluster

Add `trace` entries with stage `dedupe`.

### Stage 5: Quality Gates

Run deterministic gates:

1. Self-containedness gate:
   - no dangling references like "this", "above", "as discussed", "see Section X" unless expanded
2. Evidence coverage gate:
   - accepted items must include at least one evidence quote with page number
3. No-new-facts gate:
   - rewritten content must not introduce unsupported claims

Any failed item goes to `needs_review` with specific `reason`.
Add `trace` entries with stage `quality_gates`.

## Required Prompt Clauses

## EVIDENCE_CITATION

- Every extracted or rewritten question must be backed by verbatim quote evidence and page number.
- Evidence format: `{ "page": <number>, "quote": "<verbatim text>" }`
- If evidence cannot be located, do not accept the item.

## NO_NEW_FACTS

- Do not invent facts, assumptions, constraints, or definitions.
- Do not infer missing technical statements beyond provided evidence.
- If missing context is required to make the question self-contained, move to `needs_review`.

## NEEDS_REVIEW_FLAG

Move candidate to `needs_review` when any of these hold:

- unresolved cross-reference (proposition/section/theorem not recoverable from evidence)
- ambiguous pronoun/deixis with unclear antecedent
- insufficient quote evidence for a rewritten claim
- potential merge conflict between similar but distinct problems

## Output Schema (STRICT JSON)

Return exactly one JSON object:

```json
{
  "accepted": [
    {
      "id": "q_001",
      "question_text": "Self-contained open question text.",
      "context_brief": "Minimal context needed to understand the question.",
      "evidence": [
        {
          "page": 12,
          "quote": "Verbatim supporting quote from the paper."
        }
      ]
    }
  ],
  "needs_review": [
    {
      "id": "q_017",
      "reason": "unresolved_cross_reference",
      "question_text_raw": "Original extracted statement with unresolved reference.",
      "evidence": [
        {
          "page": 21,
          "quote": "Verbatim source quote for the unresolved item."
        }
      ]
    }
  ],
  "trace": [
    {
      "id": "q_001",
      "stage": "rewrite",
      "notes": "Expanded Proposition 2.1 reference using evidence from page 10.",
      "evidence_refs": [
        "p10",
        "p12"
      ]
    }
  ]
}
```

Do not include markdown fences in final answer. Output raw JSON only.

## Auto-Save (MANDATORY)

Before returning the final JSON to user:

1. Create output directory:
   - `outputs/runs/`
2. Generate output file name from the input name:
   - `<input_name_sanitized>.json` (local PDF stem or arXiv id)
3. Save the exact JSON output to:
   - `outputs/runs/<input_name_sanitized>.json`
4. Also write/update:
   - `outputs/latest.json`
5. Append a `trace` entry noting save paths under stage `persist`.

If save fails, still return JSON but add a `needs_review` item with reason `persist_failed` and include failure details in `trace`.
