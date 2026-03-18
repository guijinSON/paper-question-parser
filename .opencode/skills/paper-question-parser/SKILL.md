---
name: paper-question-parser
description: "Parse one paper (local PDF path or arXiv URL), extract open/unsolved questions, rewrite them into self-contained form with evidence, dedupe, quality-gate, and auto-save structured JSON. Triggers: 'parse paper questions', 'extract open problems', 'unsolved questions from paper'."
---

# Paper Question Parser

You run a single-paper workflow to extract open/unsolved research questions from a survey-style paper and rewrite each into a self-contained, evidence-grounded question.

## Path Configuration
- **RUN_DIR**: `outputs/runs/`
- **LATEST_FILE**: `outputs/latest.json`
- **TEMP_DIR**: `.sisyphus/paper-question-parser/tmp/`

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
     - `mkdir -p TEMP_DIR`
     - `curl -L --fail "<pdf_url>" -o "TEMP_DIR/<paper_slug>.pdf"`
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

Iterate through all the sections in `doc_map` and extract ALL explicit and implicit open problems/questions.

Extraction target:

- include markers like "Question", "Problem", "Open", "Unknown whether", "Is it true that"
- include entries labeled as solved (e.g., `(Solved) problem ...`) and keep them in output
- include implicit question statements that represent unresolved research problems
- for each candidate, capture:
  - raw question text (as close to source as possible)
  - page number(s)
  - verbatim supporting quote(s)
  - solved-status metadata derived from source labels (for example `(Solved)`, `Solved`, or equivalent)

Add one `trace` entry per section with stage `extract_candidates`.

### Stage 3: Self-Contained Rewrite (Precision-First)

For each candidate:

- rewrite into a standalone question understandable without the source paper
- `question_text` is the primary payload and must by itself be fully self-contained for a reader who has not seen the source paper or any other extracted question
- `question_text` should be as long as needed to inline all definitions, notation, assumptions, ambient setting, competitor class, optimization objective, and other problem data required for a mathematically usable standalone statement
- for extracted questions, prefer a clearly longer rewrite than the original paper question whenever the source wording is too compressed to stand alone; the goal is faithful expansion, not brevity
- prefer over-explaining rather than under-explaining when deciding whether to inline definitions; if a careful reader could not start solving without paper-specific terminology being unpacked, unpack it in `question_text`
- `question_text` may be a multi-sentence or multi-paragraph JSON string, but it must still read as one self-contained question rather than disconnected notes
- avoid source-pointing text in `question_text` such as "in the paper", "in this section", "as defined above", "the authors define", or similar phrasing that gestures at the source instead of stating the needed content directly
- `context_brief` is only a short label and must never carry definitions that are required to understand the problem
- resolve references like "Proposition 2.1" or "Section 3" only using evidence in the paper
- if required context is missing in evidence, do NOT guess; move item to `needs_review`

Add one `trace` entry per candidate with stage `rewrite`.

### Stage 4: Dedupe

- merge near-duplicate rewritten questions
- preserve all evidence references from merged members in `trace`
- keep one canonical `id` per merged cluster

Add one `trace` entry per candidate with stage `dedupe`.

### Stage 5: Quality Gates

Run deterministic gates:

1. Self-containedness gate:
   - no dangling references like "this", "above", "as discussed", "see Section X" unless expanded
   - if a reader would need paper-specific definitions, notation, setting details, competitor classes, or optimization criteria to understand the question, include them directly in `question_text` when supported by evidence
   - `question_text` must not rely on source-pointing language such as references to the paper, section, source text, or prior definitions instead of restating the content directly
2. Evidence coverage gate:
   - accepted items must include at least one evidence quote with page number
3. Evidence completeness gate
   - accepted items must include complete sentences as evidence; otherwise, move them to `needs_review`
4. No-new-facts gate:
   - rewritten content, including any added definitions or settings in `question_text`, must not introduce unsupported claims
5. Schema conformance gate:
   - accepted items must match the JSON output schema exactly and contain all required fields

Any failed item goes to `needs_review` with specific `reason`.
Add one `trace` entry per candidate with stage `quality_gates`.

## Required Prompt Clauses

## EVIDENCE_CITATION

- Every extracted or rewritten question must be backed by verbatim quote evidence and page number.
- Evidence format: `{ "page": <number>, "quote": "<verbatim text>" }`
- If evidence cannot be located, do not accept the item.

## NO_NEW_FACTS

- Do not invent facts, assumptions, constraints, or definitions.
- Do not infer missing technical statements beyond provided evidence.
- When expanding a question to make it self-contained, only inline definitions, notation, assumptions, or ambient-setting details that are directly supported by the paper.
- If missing context is required to make the question self-contained, move to `needs_review`.

## NEEDS_REVIEW_FLAG

Move candidate to `needs_review` when any of these hold:

- unresolved cross-reference (proposition/section/theorem not recoverable from evidence)
- ambiguous pronoun/deixis with unclear antecedent
- insufficient quote evidence for a rewritten claim
- undefined paper-specific terminology remains in `question_text`
- `question_text` points back to the source paper instead of stating the needed content directly
- potential merge conflict between similar but distinct problems

## SOLVED_STATUS_METADATA

- Do not drop candidates just because they are labeled solved.
- Every accepted question row must include solved-status metadata.
- Metadata format in each accepted row:
  - `"meta": { "is_solved": <boolean> }`
- Set `is_solved=true` only when the source explicitly marks the item as solved.
- Otherwise set `is_solved=false`.

## Output Schema (STRICT JSON)

Return exactly one JSON object:

```json
{
  "accepted": [
    {
      "id": "q_001",
      "question_text": "Fully self-contained open question text. It may be substantially longer than the original paper wording when needed to include definitions, notation, assumptions, ambient setting, competitor class, and optimization objective required to understand the problem without the source paper.",
      "context_brief": "Short topic label only; not a place to hide required definitions.",
      "meta": {
        "is_solved": false
      },
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
   - `RUN_DIR`
2. Generate output file name from the input name:
   - `<input_name_sanitized>.json` (local PDF stem or arXiv id)
3. Save the exact JSON output to:
   - `RUN_DIR/<input_name_sanitized>.json`
4. Also write/update:
   - `LATEST_FILE`
5. Append a `trace` entry noting save paths under stage `persist`.

If save fails, still return JSON but add a `needs_review` item with reason `persist_failed` and include failure details in `trace`.
