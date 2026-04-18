---
name: paper-question-parser
description: "Parse one paper or scholarly open-problem source (local PDF path, arXiv URL, direct PDF URL, DOI URL, HAL/DBLP/zbMATH/OpenAlex/Crossref landing page, workshop page, or MathOverflow thread), resolve it to readable full text, extract open/unsolved questions, rewrite them into self-contained form with evidence, dedupe, quality-gate, and auto-save structured JSON. Triggers: 'parse paper questions', 'extract open problems', 'unsolved questions from paper', 'parse open-problem page'."
---

# Paper Question Parser

You run a single-source workflow to extract open/unsolved research questions from a paper, workshop problem sheet, bibliographic landing page that resolves to full text, or scholarly problem page, and rewrite each into a self-contained, evidence-grounded question.

## Path Configuration
- **RUN_DIR**: `outputs/parse-paper/`
- **LATEST_FILE**: `outputs/latest.json`
- **TEMP_DIR**: `.sisyphus/paper-question-parser/tmp/`

## Operating Contract

- Process exactly one source per run.
- Accept either a local PDF path or one URL pointing to a scholarly source. Supported URL families include arXiv `abs`/`pdf`, direct PDFs, DOI URLs, HAL pages, DBLP/Crossref/OpenAlex/zbMATH landing pages, workshop/problem-session pages, and MathOverflow threads.
- Resolve URL inputs to a readable full-text artifact before extraction.
- Do not ask the user to run scripts.
- Return STRICT JSON only (no prose) with keys: `source`, `accepted`, `needs_review`, `trace`.
- Auto-save the final JSON result to disk every run.

## Input Normalization

1. Read `$ARGUMENTS` and extract a single source.
2. If input is a local PDF path:
   - Verify the file exists.
   - Use that absolute path as `paper_path`.
   - Set:
     - `source_kind = "pdf"`
     - `source_locator = paper_path`
     - `source_name = <local_pdf_stem>`
     - `citation_mode = "page_number"`
3. If input is a URL:
   - Normalize obvious wrappers while preserving the identity of the same source.
   - Resolve the URL in this order:
     1. If the URL is `https://arxiv.org/abs/<id>`, convert it to `https://arxiv.org/pdf/<id>.pdf`.
     2. If the URL is already a direct PDF URL, or the resolved response is a PDF, download it internally with Bash:
        - `mkdir -p TEMP_DIR`
        - `curl -L --fail "<pdf_url>" -o "TEMP_DIR/<paper_slug>.pdf"`
        - set `paper_path` to the downloaded file
        - set:
          - `source_kind = "pdf"`
          - `source_locator = paper_path`
          - `source_name = <arxiv_id_or_pdf_slug>`
          - `citation_mode = "page_number"`
     3. If the URL is a DOI URL or a bibliographic/landing page (for example Crossref, OpenAlex, DBLP, zbMATH, HAL, or a publisher landing page), inspect the page and follow the most specific full-text link available:
        - preferred targets: `PDF`, `Download article`, `Download extract`, `document`, `unpaywalled`, `external edition`, or an explicit article page whose visible body contains the problems
        - treat DBLP, Crossref, OpenAlex, and zbMATH primarily as resolvers, not as the technical source
        - for HAL, prefer an explicit `/document` or file-download link when available
        - if the landing page or download endpoint returns a missing-resource page, paywall page, or metadata-only page, query source-specific metadata APIs when available to recover the exact title and candidate readable copies of that same work:
          - HAL: `https://api.archives-ouvertes.fr/search/?q=halId_s:<id>&rows=1&fl=title_s,uri_s,openAccess_bool,submitType_s,label_xml&wt=json`
          - Crossref: `https://api.crossref.org/works/<doi>`
          - OpenAlex: `https://api.openalex.org/works?filter=doi:https://doi.org/<doi>&select=display_name,doi,open_access,best_oa_location,primary_location`
        - use API metadata only to identify the exact work, discover candidate full-text URLs, and detect access restrictions; do not extract open problems from API metadata, abstracts, or resolver records
        - only follow candidate URLs from APIs when the destination still matches the same DOI or the same exact title
     4. If the URL is a workshop/problem-session/forum page whose own body contains the relevant problem statements, use the page itself as the primary source.
        - examples: AIM pages, workshop problem-session pages, MathOverflow threads
        - for MathOverflow, prefer the question body as the primary source; use answers/comments only for explicit resolution claims or clarifications that are needed and clearly attributable
     5. If direct fetching fails because of redirects, robots/SSL issues, transient HTML fetch failures, or citation-only landing pages, search for the same source by exact title, DOI, repository identifier, or trailing URL slug and recover a readable artifact for that same work/source. Do not switch to a different work.
   - If the resolved primary source is HTML rather than PDF, set:
     - `source_kind = "html"`
     - `source_locator = <canonical URL of the chosen page>`
     - `source_name = <arxiv_id_or_doi_slug_or_url_slug>`
     - `citation_mode = "locator_string"`

## Source Metadata

- Every final JSON object must include a top-level `source` object.
- `source.url` must preserve the original user-supplied source locator:
  - if input was a URL, store that original URL
  - if input was a local PDF path, store the absolute local path
- `source.resolved_locator` must record the canonical URL or local file path actually used for extraction.
- `source.title` must be a non-empty source title.
- `source.title_origin` must be one of:
  - `source_text`
  - `resolver_metadata`
  - `ai_extracted`
  - `filename`
- Determine `source.title` in this order:
  1. Prefer the visible title from the chosen primary source itself:
     - PDF title page, first page heading, or explicit article/workshop title
     - HTML `<title>`, `<h1>`, main heading, or obvious visible page title
  2. If the chosen primary source lacks a reliable visible title, use trusted resolver metadata for the same exact work/source.
  3. If no reliable title is available, infer a concise descriptive title from the readable source body and set `title_origin = "ai_extracted"`.
  4. If the source is unreadable and no better title is available, fall back to the local filename stem or URL slug and set `title_origin = "filename"`.
- Never leave `source.title` blank.

## Source Resolution Rules

- Prefer the direct PDF of the exact source document when available.
- Otherwise use full HTML text whose visible body actually contains the problem statements.
- Otherwise use the closest source-authorized readable copy.
- Treat direct-fetch failures such as robots-blocked pages, broken TLS, redirect loops, and citation-only HTML as resolver failures, not as proof that the source is unusable.
- Metadata APIs may be used for discovery, title recovery, DOI verification, and access-status checks, but never as the technical source for extraction.
- If a resolver or API confirms the record is metadata-only or restricted with no readable full text (for example a HAL `notice` record with `openAccess_bool=false`), stop retrying equivalent resolver URLs and move the item to `needs_review` unless you can recover another exact-work readable copy.
- Candidate links discovered in resolver metadata, API fields, or publisher abstracts must be treated as hints only; follow them only if the resulting page or file still matches the same DOI or the same exact title.
- Do not rely on abstract-only pages, citation-only pages, search snippets, or index metadata as the technical source when they do not contain the problem statements themselves.
- Do not combine multiple separate works into one run. If a resolver page exposes multiple editions, choose one canonical readable source and stay with it.

## Source-Family Hints

- **AIM / AIMPL pages**: if the exact URL does not fetch cleanly, search the AIM Problem Lists site by the trailing slug and exact visible title, then use the matching list page that contains the problem statements. If the root page is only an index, follow the numbered internal subpage that actually lists the problems.
- **Legacy HAL hosts**: normalize old `hal-*.ccsd.cnrs.fr` pages to their canonical `hal.science` record when possible; if needed, search by the HAL identifier and prefer a `document` or direct file URL. If `/document` returns a missing-resource page, query the HAL API by identifier. Treat records such as `submitType_s="notice"` with `openAccess_bool=false` as metadata-only dead ends unless another exact-work readable copy is found.
- **DBLP / zbMATH / OpenAlex / Crossref**: treat these as bibliographic resolvers. Prefer explicit links labeled `unpaywalled version`, `electronic edition`, `external edition`, `PDF`, `document`, `arXiv`, or DOI targets that lead to readable full text. If the resolver page still exposes only metadata, use the exact title, DOI, year, and author metadata to recover an accessible copy of that same work.
- **OpenAlex**: prefer `best_oa_location.pdf_url`, then `best_oa_location.landing_page_url`, then `primary_location` when they correspond to the same exact work. If `open_access.is_oa=false` and there is no repository or PDF location, treat OpenAlex as identity metadata only.
- **Crossref**: use Crossref to recover the exact title, DOI, and candidate resource URLs. Treat `resource.primary.URL`, `link[]`, and any full-text URL embedded in the abstract only as candidate leads, and only follow them when the resolved destination still matches the same DOI or exact title.
- **DOI URLs**: if the DOI landing page is paywalled or metadata-only, query Crossref and OpenAlex by DOI before doing a generic exact-title search. Prefer repository copies, accepted manuscripts, or author-posted PDFs of the same work.
- **zbMATH**: if the zbMATH page itself is access-denied or metadata-only, use the zbMATH identifier plus the exact title/year/author metadata to search for the same work elsewhere. If no readable exact-work copy exists, move the item to `needs_review` rather than extracting from bibliographic metadata.

If input is invalid or cannot be downloaded, return:

```json
{
  "source": {
    "url": "<original_input_url_or_path>",
    "resolved_locator": "",
    "title": "<best_effort_slug_or_filename>",
    "title_origin": "filename"
  },
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
      "notes": "Input could not be normalized to a readable PDF or HTML full-text source.",
      "evidence_refs": []
    }
  ]
}
```

## Workflow Stages

### Stage 1: Map

- If `source_kind = "pdf"`, use `look_at(file_path=paper_path, goal=...)` to extract:

  - section hierarchy (major sections and subsections)
  - notation/definitions index
  - theorem/proposition/lemma reference index (labels and where they appear)
  - likely "open problems/questions" regions

- If `source_kind = "html"`, use the available web/page-reading tools on `source_locator` to extract:
  - section hierarchy or page structure (headings, numbered problem blocks, post/answer/comment blocks, list items)
  - notation/definitions index when present
  - likely "open problems/questions" regions
  - stable locators for later citation, such as section titles, numbered items, and HTML line spans

Record this as `doc_map` in working memory and add a `trace` entry with stage `map`.

### Stage 2: Candidate Extraction (Recall-First)

Iterate through all the sections in `doc_map` and extract ALL explicit and implicit open problems/questions.

Extraction target:

- include markers like "Question", "Problem", "Open", "Unknown whether", "Is it true that"
- include bullet lists, numbered problem sessions, named open-problem blocks, and forum-style top-level question statements when they are clearly mathematical research questions
- include entries labeled as solved (e.g., `(Solved) problem ...`) and keep them in output
- include implicit question statements that represent unresolved research problems
- for forum-style sources, extract the main post and any explicitly separated subquestions; do not mine side comments or answers as separate research problems unless they clearly formulate one
- for each candidate, capture:
  - raw question text (as close to source as possible)
  - page number(s) or stable HTML locator(s)
  - verbatim supporting quote(s)
  - solved-status metadata derived from source labels (for example `(Solved)`, `Solved`, or equivalent)

Add one `trace` entry per section with stage `extract_candidates`.

### Stage 3: Self-Contained Rewrite (Precision-First)

For each candidate:

- rewrite into a standalone question understandable without the source
- `question_text` is the primary payload and must by itself be fully self-contained for a reader who has not seen the source or any other extracted question
- `question_text` should be as long as needed to inline all definitions, notation, assumptions, ambient setting, competitor class, optimization objective, and other problem data required for a mathematically usable standalone statement
- for extracted questions, prefer a clearly longer rewrite than the original source wording whenever that wording is too compressed to stand alone; the goal is faithful expansion, not brevity
- prefer over-explaining rather than under-explaining when deciding whether to inline definitions; if a careful reader could not start solving without source-specific terminology being unpacked, unpack it in `question_text`
- `question_text` may be a multi-sentence or multi-paragraph JSON string, but it must still read as one self-contained question rather than disconnected notes
- avoid source-pointing text in `question_text` such as "in the paper", "in this section", "as defined above", "the authors define", or similar phrasing that gestures at the source instead of stating the needed content directly
- `context_brief` is only a short label and must never carry definitions that are required to understand the problem
- resolve references like "Proposition 2.1", "Section 3", "Problem 4", or "the accepted answer" only using evidence in the chosen primary source artifact
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
   - if a reader would need source-specific definitions, notation, setting details, competitor classes, or optimization criteria to understand the question, include them directly in `question_text` when supported by evidence
   - `question_text` must not rely on source-pointing language such as references to the paper, section, source text, or prior definitions instead of restating the content directly
2. Evidence coverage gate:
   - accepted items must include at least one evidence quote with a page number or stable HTML locator
3. Evidence completeness gate
   - accepted items must include complete sentences or a contiguous self-contained problem statement as evidence; otherwise, move them to `needs_review`
4. No-new-facts gate:
   - rewritten content, including any added definitions or settings in `question_text`, must not introduce unsupported claims
5. Source adequacy gate:
   - do not accept items extracted only from abstracts, citation metadata, link labels, thread titles, or search snippets when the technical problem statement is not visible in the chosen source text
6. Schema conformance gate:
   - accepted items must match the JSON output schema exactly and contain all required fields

Any failed item goes to `needs_review` with specific `reason`.
Add one `trace` entry per candidate with stage `quality_gates`.

## Required Prompt Clauses

## EVIDENCE_CITATION

- Every extracted or rewritten question must be backed by verbatim quote evidence and a source locator.
- Evidence format: `{ "page": <number_or_string>, "quote": "<verbatim text>" }`
- Use numeric page numbers for PDFs.
- Use stable locator strings for HTML/page/thread sources, such as `"HTML lines 57-58"`, `"Problem 3, HTML lines 23-28"`, or `"Accepted answer lines 167-169"`.
- If evidence cannot be located, do not accept the item.

## JSON_SERIALIZATION

- The final payload must be valid JSON that parses without repair.
- Escape every backslash inside JSON strings. This matters especially for TeX/LaTeX-rich HTML sources such as MathOverflow, arXiv HTML, and copied formulas.
- In `question_text`, prefer plain-text or Unicode mathematical notation over raw TeX when either would be equally faithful.
- In `evidence.quote`, keep the source text verbatim, but serialize it as a valid JSON string with required escaping.
- Before returning and before saving, check that the exact payload would parse as JSON; if not, repair the escaping first.

## NO_NEW_FACTS

- Do not invent facts, assumptions, constraints, or definitions.
- Do not infer missing technical statements beyond provided evidence.
- When expanding a question to make it self-contained, only inline definitions, notation, assumptions, or ambient-setting details that are directly supported by the chosen source.
- Do not treat citation metadata, abstracts, or search snippets as sufficient technical evidence unless the chosen source page itself states the full problem there.
- If missing context is required to make the question self-contained, move to `needs_review`.

## NEEDS_REVIEW_FLAG

Move candidate to `needs_review` when any of these hold:

- unresolved cross-reference (proposition/section/theorem not recoverable from evidence)
- ambiguous pronoun/deixis with unclear antecedent
- insufficient quote evidence for a rewritten claim
- undefined source-specific terminology remains in `question_text`
- `question_text` points back to the source instead of stating the needed content directly
- potential merge conflict between similar but distinct problems
- source resolves only to abstract/citation metadata without the full problem text
- resolver/API metadata confirms the record is restricted, notice-only, or lacks any readable full-text copy of the same work
- forum/workshop page is not self-contained enough and missing context cannot be recovered from the same source
- resolver chain is ambiguous between multiple possible full-text sources

## SOLVED_STATUS_METADATA

- Do not drop candidates just because they are labeled solved.
- Every accepted question row must include solved-status metadata.
- Metadata format in each accepted row:
  - `"meta": { "is_solved": <boolean> }`
- Set `is_solved=true` only when the chosen primary source explicitly marks the item as solved or explicitly resolves it in the same source artifact.
- Otherwise set `is_solved=false`.

## Output Schema (STRICT JSON)

Return exactly one JSON object:

```json
{
  "source": {
    "url": "https://example.org/problem-page",
    "resolved_locator": "https://example.org/problem-page",
    "title": "Example Problems Page",
    "title_origin": "source_text"
  },
  "accepted": [
    {
      "id": "q_001",
      "question_text": "Fully self-contained open question text. It may be substantially longer than the original source wording when needed to include definitions, notation, assumptions, ambient setting, competitor class, and optimization objective required to understand the problem without the source.",
      "context_brief": "Short topic label only; not a place to hide required definitions.",
      "meta": {
        "is_solved": false
      },
      "evidence": [
        {
          "page": 12,
          "quote": "Verbatim supporting quote from the source."
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
          "page": "HTML lines 57-58",
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

`page` may be either a numeric page number or a stable string locator, depending on `citation_mode`.

## Auto-Save (MANDATORY)

Before returning the final JSON to user:

1. Create output directory:
   - `RUN_DIR`
2. Generate output file name from the normalized source name:
   - `<source_name_sanitized>.json` (local PDF stem, arXiv id, DOI slug, or URL slug)
3. Save the exact JSON output to:
   - `RUN_DIR/<source_name_sanitized>.json`
4. Also write/update:
   - `LATEST_FILE`
5. Append a `trace` entry noting save paths under stage `persist`.

If save fails, still return JSON but add a `needs_review` item with reason `persist_failed` and include failure details in `trace`.
