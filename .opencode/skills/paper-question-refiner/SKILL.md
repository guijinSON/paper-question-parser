---
name: paper-question-refiner
description: "Read one research question plus arXiv ID, judge the rewritten question with a difficulty/perfectness rubric, emit a self-contained context-only rewrite plus an optional reformulation rewrite with paper-backed evidence, and search later literature to tag whether the question appears solved. Triggers: 'refine research question', 'make this question self contained', 'judge and rewrite paper question'."
---

# Paper Question Refiner

You run a one-question workflow that turns a user-provided research question plus one arXiv identifier into one or two self-contained rewrite artifacts for a broad mathematician.

## Path Configuration
- **RUN_DIR**: `outputs/runs/`
- **LATEST_FILE**: `outputs/paper-question-refiner.latest.json`
- **TEMP_DIR**: `.sisyphus/paper-question-refiner/tmp/`

## Operating Contract

- Process exactly one question per run.
- Accept exactly one JSON object through `$ARGUMENTS` with keys `question` and `arxiv_id`.
- Read the cited arXiv paper as the primary source of truth.
- Always try to determine whether the question appears solved in later literature.
- You may search and use up to 10 additional academic papers total across context recovery and solved-status search.
- Prefer the primary paper for the original formulation of the question, but use later academic papers to determine whether that question was subsequently solved.
- Return STRICT JSON only. The final answer must be a raw JSON array containing one or two artifact objects.
- Always emit one `context_only` artifact.
- Emit one `reformulation` artifact only when the context-only rewrite is still too awkward, unclear, or solver-hostile despite having enough definitions and evidence.
- Every emitted artifact must include a `resolution` block with solved-status metadata.
- Auto-save every emitted artifact to disk every run.
- Also write `outputs/paper-question-refiner.latest.json` as the exact JSON array returned to the user.
- Do not ask the user to run scripts.

## Input Normalization

1. Read `$ARGUMENTS`.
2. Parse it as a JSON object.
3. Require exactly these keys:
   - `question`: non-empty string
   - `arxiv_id`: non-empty string
4. Normalize `arxiv_id`:
   - trim whitespace
   - accept canonical IDs like `0704.1689` or `2501.01234`
   - if the value looks like an arXiv URL, extract the ID
5. Build:
   - `question_text_raw`
   - `arxiv_id`
   - `abs_url = https://arxiv.org/abs/<arxiv_id>`
   - `pdf_url = https://arxiv.org/pdf/<arxiv_id>.pdf`
6. Download the primary paper internally with Bash:
   - `mkdir -p TEMP_DIR`
   - `curl -L --fail "<pdf_url>" -o "TEMP_DIR/<arxiv_id>.pdf"`
7. Use the downloaded file as `paper_path`.

If the input is invalid, the arXiv identifier is invalid, or the PDF cannot be downloaded/read, return exactly one artifact object inside a JSON array with:

```json
[
  {
    "schema_version": "1.0",
    "input": {
      "question": "",
      "arxiv_id": ""
    },
    "target_reader": "broad_mathematician",
    "rewrite_kind": "context_only",
    "verdict": {
      "status": "error",
      "reasons": ["invalid_input"]
    },
    "original_question": "",
    "original_paper": {
      "title": null,
      "locator": "",
      "source_id": "primary"
    },
    "rewritten_question": "",
    "resolution": {
      "solved_status": "unknown",
      "status_confidence": "low",
      "status_reason": "The workflow did not reach a reliable solved-status determination.",
      "solving_paper": null,
      "search_trace": {
        "sources": [],
        "query_variants": [],
        "status_checked_at": null,
        "notes": "Solved-status search did not run because input normalization failed."
      }
    },
    "paper_evidence": [],
    "consulted_papers": [],
    "rubric_scores": {
      "difficulty": [],
      "perfectness": []
    },
    "trace": [
      {
        "stage": "input",
        "notes": "Input could not be normalized into a readable question plus arXiv paper source.",
        "evidence_refs": []
      }
    ],
    "persist": {
      "run_path": "",
      "latest_path": "outputs/paper-question-refiner.latest.json",
      "saved": false
    }
  }
]
```

Use the most specific failure reason available from this enum:
- `invalid_input`
- `invalid_arxiv_id`
- `download_failed`
- `pdf_unreadable`
- `question_not_located`
- `insufficient_primary_support`
- `insufficient_literature_support`
- `resolution_search_inconclusive`
- `undefined_terminology`
- `schema_invalid`
- `persist_failed`

## Workflow Stages

### Stage 1: Map the Primary Paper

Use `look_at(file_path=paper_path, goal=...)` and, when needed, `read(filePath=paper_path, ...)` to recover:

- title, authors, and broad topic
- section hierarchy
- notation/definitions index
- theorem/proposition/lemma references
- exact locations where the user question or its core objects appear
- any question labels, conjecture numbers, problem names, or aliases that will help later literature search

Record a `trace` entry with stage `map_primary`.

### Stage 2: Locate the Question and Primary Evidence

Find where the supplied question is stated, implied, or discussed in the primary paper.

Capture primary evidence for:
- the goal of the question
- every mathematical object mentioned in the question
- every notation item required to understand the question
- any explicit open/unknown status
- any wording that identifies the exact formulation to match against later literature

If the question itself cannot be located in the primary paper, return a `context_only` artifact with `verdict.status = "needs_review"` and reason `question_not_located`.

Record a `trace` entry with stage `locate_question`.

### Stage 3: Recover Definitions and Context from the Primary Paper

Build the minimal set of definitions, assumptions, ambient setting, and notation required for a broad mathematician to understand the question without reading the source paper.

Rules:
- unpack paper-specific jargon when the term is not standard for a broad mathematician
- inline definitions rather than gesturing back to the paper
- prefer faithful expansion over brevity
- do not invent missing assumptions or strengthen statements

Record a `trace` entry with stage `recover_primary_context`.

### Stage 4: Bounded Academic-Paper Backfill and Resolution Search

Use this stage for two purposes:

- recover missing definitions, setup details, or standard formulations needed for a self-contained rewrite
- search later academic literature to determine whether the same question appears solved

Backfill rules:
- you may search up to 10 additional academic papers total
- default to `solved_status = "unknown"` unless the literature supports a stronger claim
- only papers actually used either in the final rewrite or in the final solved-status determination go into `consulted_papers`
- failed searches or papers you inspected but did not use must not appear in `consulted_papers`
- acceptable backfill sources are academic papers, preprints, journal versions, conference papers, or survey papers
- do not use non-academic web sources as evidence
- if backfill papers disagree with the primary paper about terminology or formulation, prefer the primary paper's formulation of the question
- use backfill primarily to recover missing definitions, standard formulations, or missing setup details
- do not use backfill to silently replace the primary paper’s actual question with a different problem
- do not claim `solved` unless a later paper explicitly solves the same question or proves a result that clearly subsumes it
- do not claim `unsolved` merely because no solving paper was found; `unsolved` requires that the primary paper explicitly frames the question as open or unknown and that bounded later-literature search found no credible solving paper
- when evidence is partial, conflicting, or only supports a nearby special case, keep `solved_status = "unknown"`

If the primary paper plus bounded backfill still do not support a self-contained rewrite, keep the `context_only` artifact but set `verdict.status = "needs_review"` with reason `insufficient_literature_support` or `undefined_terminology`.

If solved-status search remains ambiguous after bounded search, keep the artifact but either leave `solved_status = "unknown"` or set `verdict.status = "needs_review"` with reason `resolution_search_inconclusive` when the ambiguity materially affects usefulness.

Record a `trace` entry with stage `backfill`.

### Stage 5: Build the `resolution` Block

Every emitted artifact must include a `resolution` block with:

- `solved_status`: one of `solved`, `unsolved`, or `unknown`
- `status_confidence`: one of `high`, `medium`, or `low`
- `status_reason`: short evidence-grounded explanation of the solved-status decision
- `solving_paper`: either `null` or an object with `source_id`, `title`, and `locator`
- `search_trace`: object summarizing search sources, query variants, and the date of the bounded solved-status search

Resolution rules:

- default to `solved_status = "unknown"`
- set `solved_status = "solved"` only when the primary paper states the target question and a later academic paper explicitly solves that same question or proves a result that clearly subsumes it
- set `solved_status = "unsolved"` only when the primary paper explicitly marks the question as open or unknown and bounded later-literature search found no credible solving paper
- set `status_confidence` based on evidence strength and exact-match certainty: `high` only for explicit exact-match evidence, `medium` for strong but slightly indirect support, and `low` for unresolved or ambiguous cases
- if `solved_status = "solved"`, `solving_paper` must be non-null and must point to the solving paper using a stable URL, preferably a DOI URL and otherwise an arXiv abstract URL
- if `solving_paper` is non-null, `solving_paper.source_id` must match exactly one `consulted_papers` entry with `used_for_resolution = true`
- if `solved_status != "solved"`, set `solving_paper = null`
- do not place solved-status prose inside `rewritten_question`; keep it in `resolution`

Record a `trace` entry with stage `resolve_status`.

### Stage 6: Build the `context_only` Rewrite

Always emit a `context_only` artifact.

This rewrite must:
- preserve the mathematical goal of the source question
- add only definitions, notation expansions, assumptions, and setting details needed for comprehension
- avoid gratuitous stylistic reframing
- read as one self-contained question for a broad mathematician
- avoid source-pointing language such as "in the paper", "as defined above", "the authors ask", or "see Section X"
- use plain JSON-safe mathematical prose rather than TeX or LaTeX markup

`rewritten_question` may be multi-sentence or multi-paragraph JSON text, but it must read as a single coherent question.

Record a `trace` entry with stage `rewrite_context_only`.

### Stage 7: Decide Whether `reformulation` Is Necessary

Emit a second `reformulation` artifact only when the `context_only` rewrite still fails one of these despite having enough evidence:

- clarity
- naturalness
- solver usability

Examples of valid reformulation:
- reordering definitions so the question reads more naturally
- compressing repetitive setup after definitions are already explicit
- turning an awkward paper-native phrasing into a more standard mathematical statement

Examples of invalid reformulation:
- changing the problem being asked
- strengthening or weakening quantifiers without evidence
- adding unsupported equivalences, conjectural interpretations, or external facts

The reformulation artifact must still be evidence-grounded and must still prefer the primary paper’s statement when conflicts exist.

The `resolution` block should normally be identical across emitted artifacts unless one artifact is downgraded to `needs_review` for a schema or evidence reason unique to that artifact.

Record a `trace` entry with stage `rewrite_reformulation` when emitted.

### Stage 8: Score the Emitted Rewrite Artifact(s)

Score artifacts intended for emission at this stage. If a later quality gate downgrades an artifact to a non-usable output, its score arrays may be left empty. Score only the emitted `rewritten_question` for each artifact. Do not score the original question or the `resolution` block.

Use a 1–10 scale with `10 = harder/better`.

#### Difficulty Axes
- `A1_prerequisite_specificity` — Does solving require niche facts, folklore, or a narrow genre-specific trick?
- `A2_domain_recognition` — Is it obvious what area and viewpoint the problem belongs to?
- `A3_object_unfamiliarity` — Are the objects, definitions, or constraints unusual for the target solver?
- `A4_representation_setup` — Must one choose a non-obvious substitution, normalization, invariant, encoding, or model before progress?
- `A5_first_foothold_visibility` — Is there an obvious productive first move, toy case, or experiment?
- `D2_dead_end_surface` — How many plausible but wrong approaches naturally present themselves?
- `D3_key_leap_size` — How far is the winning idea from the most natural first attempts?
- `D5_method_novelty` — How far outside standard repertoire does the correct method feel?
- `C1_technical_length` — After the main idea is known, how many nontrivial steps still remain?
- `C2_computation_burden` — How much algebra, estimation, symbolic cleanup, or exact manipulation is needed?

#### Perfectness Axes
- `P1_well_posedness_unambiguity` — Is there a single clean interpretation, with no hidden assumptions or ambiguity?
- `P2_solver_fit_self_containedness` — Does the problem assume only what the target solver should reasonably know, or explicitly define what is nonstandard?
- `P3_purity_of_difficulty` — Is the challenge mathematical rather than caused by wording clutter, notation friction, or accidental pathology?
- `P4_fair_concealment` — Is the key idea hidden in a fair way, rather than arbitrarily obscured or accidentally leaked?
- `P5_naturalness_of_core` — Does the intended solution feel motivated and coherent rather than gimmicky or patched together?
- `P6_payoff_finish_quality` — Is the ending clean and satisfying, with the sense that the problem resolves at the right level of elegance?

For every score row include:
- `id`
- `label`
- `score`
- `direction` with value `higher_is_better`
- `rationale`

Record a `trace` entry with stage `score`.

### Stage 9: Quality Gates

Run deterministic gates on each emitted artifact:

1. Self-containedness gate
   - `rewritten_question` must stand alone for a broad mathematician
   - no dangling references to the paper, source sections, prior statements, or undefined paper-local notation
2. Evidence coverage gate
   - every nontrivial inserted definition, contextual clause, or solved-status claim must be supported by at least one page-numbered quote
3. No-new-facts gate
   - no unsupported claims, assumptions, equivalences, or solved-status assertions
4. Resolution gate
   - `solved` requires evidence that a later paper solves the same question or clearly subsumes it
   - `unsolved` requires explicit open/unknown framing in the primary paper plus bounded later-literature search with no credible solving paper found
   - `unknown` is required when the evidence is ambiguous, partial, conflicting, or only supports nearby variants
   - `solving_paper` must be non-null only when `solved_status = "solved"`
   - `search_trace` must be present whenever the workflow reaches solved-status search
5. Primary-paper priority gate
   - when sources disagree about the original formulation, the emitted rewrite follows the primary paper while later papers may still establish subsequent resolution of that formulation
6. Reformulation necessity gate
   - do not emit `reformulation` if `context_only` already meets clarity, naturalness, and solver-usability goals
7. JSON-safety gate
   - do not use raw TeX or LaTeX commands such as `\(`, `\)`, `\[`, `\]`, `\operatorname`, `\mathbb`, or similar markup in generated prose fields such as `rewritten_question`, `notes`, and score `rationale`
   - verbatim `quote` evidence may preserve the source notation when needed
   - prefer plain words or Unicode symbols instead of backslash-based math markup in generated prose
8. Schema conformance gate
   - every emitted artifact must match the schema below exactly

If a gate fails irrecoverably:
- return `verdict.status = "needs_review"` when the artifact is still useful but incomplete
- return `verdict.status = "error"` when the artifact cannot be responsibly emitted

Record a `trace` entry with stage `quality_gates`.

## Evidence Rules

### EVIDENCE_CITATION

- Every inserted definition, notation expansion, assumption, contextual clause, or solved-status claim must be backed by a verbatim quote and page number.
- Evidence format:
  - `{ "source_id": "primary", "page": 12, "quote": "...", "supports": ["def_hessian_nilpotent"] }`
- `supports` must contain concise snake_case labels naming the rewrite component justified by that quote.
- For `solved_status = "solved"`, include evidence for the source question, the solving claim, and the match between them.
- For `solved_status = "unsolved"`, include evidence that the primary paper poses the question as open or unknown; record the bounded no-match search summary in `resolution.search_trace` rather than inventing pseudo-paper evidence.
- For `solved_status = "unknown"`, include evidence from any candidate papers actually cited in the ambiguity analysis, and record the unresolved search summary in `resolution.search_trace`.

### CONSULTED_PAPERS

- When the primary paper was successfully identified and read, `consulted_papers` must include the primary paper and any backfill papers actually used either in the final rewrite or in the final solved-status determination.
- Every `source_id` in `paper_evidence`, including `primary`, must resolve to exactly one entry in `consulted_papers`.
- `original_paper.locator` should usually be the arXiv abstract URL.
- For backfill papers, `locator` should be the most stable URL available for that paper, preferably `https://doi.org/...` and otherwise an arXiv abstract URL.
- Add a `used_for_resolution` boolean to each consulted backfill paper entry.
- Any paper cited in `resolution.status_reason`, `resolution.solving_paper`, or ambiguity analysis counts as used for resolution and must appear in `consulted_papers`.

### NO_NEW_FACTS

- Do not invent definitions, assumptions, reformulations, solved-status claims, or solving-paper links.
- Do not infer stronger conclusions than the evidence supports.
- If a definition cannot be recovered responsibly, move to `needs_review` or `error` rather than guessing.
- If solved status cannot be established responsibly, use `unknown` rather than guessing.

### JSON_SAFE_TEXT

- Every string value in the final JSON must be valid JSON text.
- Do not place raw TeX or LaTeX commands in generated prose fields such as `rewritten_question`, `notes`, or `rationale`.
- Verbatim evidence `quote` fields may preserve source notation when that is the faithful quote.
- When mathematical notation would naturally use TeX in generated prose, rewrite it in plain text or Unicode-safe notation instead.

## Output Schema (STRICT JSON)

Return raw JSON only.

- The final answer must be a JSON array of one or two artifact objects.
- Each artifact object must match this schema:

```json
{
  "schema_version": "1.0",
  "input": {
    "question": "Original user-provided question.",
    "arxiv_id": "0704.1689"
  },
  "target_reader": "broad_mathematician",
  "rewrite_kind": "context_only",
  "verdict": {
    "status": "accepted",
    "reasons": []
  },
  "original_question": "Original user-provided question.",
  "original_paper": {
    "title": "Title of the cited primary paper.",
    "locator": "https://arxiv.org/abs/0704.1689",
    "source_id": "primary"
  },
  "rewritten_question": "Self-contained rewritten question for a broad mathematician.",
  "resolution": {
    "solved_status": "solved",
    "status_confidence": "high",
    "status_reason": "A later paper explicitly proves the same conjecture posed in the source paper.",
    "solving_paper": {
      "source_id": "paper_001",
      "title": "A later paper that resolves the question.",
      "locator": "https://doi.org/10.1000/example"
    },
    "search_trace": {
      "sources": ["primary paper", "arXiv", "Crossref"],
      "query_variants": ["exact conjecture title", "authors plus conjecture name"],
      "status_checked_at": "2026-03-24",
      "notes": "The bounded literature search found an explicit later-paper resolution claim."
    }
  },
  "paper_evidence": [
    {
      "source_id": "primary",
      "page": 2,
      "quote": "Verbatim supporting quote from the source paper.",
      "supports": ["question_goal", "def_hessian_nilpotent", "resolution_baseline"]
    },
    {
      "source_id": "paper_001",
      "page": 5,
      "quote": "We prove the conjecture stated in [source paper] in full generality.",
      "supports": ["resolution_status", "solving_paper_match"]
    }
  ],
  "consulted_papers": [
    {
      "source_id": "primary",
      "title": "Title of the cited primary paper.",
      "authors": ["Author One", "Author Two"],
      "year": 2007,
      "locator": "https://arxiv.org/abs/0704.1689",
      "role": "primary",
      "used_for_rewrite": true,
      "used_for_resolution": true
    },
    {
      "source_id": "paper_001",
      "title": "A later paper that resolves the question.",
      "authors": ["Author Three"],
      "year": 2018,
      "locator": "https://doi.org/10.1000/example",
      "role": "resolution_candidate",
      "used_for_rewrite": false,
      "used_for_resolution": true
    }
  ],
  "rubric_scores": {
    "difficulty": [
      {
        "id": "A1_prerequisite_specificity",
        "label": "Prerequisite specificity",
        "score": 7,
        "direction": "higher_is_better",
        "rationale": "Requires specialized terminology from Hessian nilpotence and vanishing-conjecture literature."
      }
    ],
    "perfectness": [
      {
        "id": "P2_solver_fit_self_containedness",
        "label": "Solver-fit and self-containedness",
        "score": 9,
        "direction": "higher_is_better",
        "rationale": "The rewrite states the needed definitions directly and no longer depends on source-local notation."
      }
    ]
  },
  "trace": [
    {
      "stage": "resolve_status",
      "notes": "Searched later academic literature and matched a later paper's explicit resolution claim to the source question.",
      "evidence_refs": ["primary:p2", "paper_001:p5"]
    },
    {
      "stage": "rewrite_context_only",
      "notes": "Expanded Hessian nilpotence and the Laplace operator into standalone wording using primary-paper evidence.",
      "evidence_refs": ["primary:p2", "primary:p3"]
    }
  ],
  "persist": {
    "run_path": "outputs/runs/0704.1689--context-only.json",
    "latest_path": "outputs/paper-question-refiner.latest.json",
    "saved": true
  }
}
```

## Auto-Save (MANDATORY)

Before returning the final JSON array to the user:

1. Create output directory:
   - `RUN_DIR`
2. Generate base name from the normalized arXiv ID:
   - `<arxiv_id_sanitized>`
3. Save the context-only artifact to:
   - `RUN_DIR/<arxiv_id_sanitized>--context-only.json`
4. If emitted, save the reformulation artifact to:
   - `RUN_DIR/<arxiv_id_sanitized>--reformulation.json`
5. Save the exact final returned JSON array to:
   - `LATEST_FILE`
6. In each emitted artifact, set `persist.run_path` to its own run file and `persist.latest_path` to `outputs/paper-question-refiner.latest.json`.
7. Append a `trace` entry with stage `persist`.

Saved artifacts must preserve the exact `resolution` block and any consulted solving-paper metadata included in the final JSON.

If saving fails:
- still return strict JSON
- set `persist.saved = false`
- add reason `persist_failed`
- explain the failure in `trace`
