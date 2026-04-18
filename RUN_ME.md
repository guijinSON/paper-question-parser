# Paper Question Tools Bundle

This folder contains local OpenCode skills and runtime artifacts for prompt-driven paper-question workflows.

## Included

- `.opencode/skills/paper-question-parser/SKILL.md`
- `.opencode/skills/paper-question-refiner/SKILL.md`
- `.opencode/skills/math-genealogy-archaeologist/SKILL.md`
- `outputs/latest.json`
- `outputs/paper-question-refiner.latest.json`
- `outputs/parse-paper/*.json`
- `outputs/math-genealogy-archaeologist/<arxiv_id>/`

## Skill 1: Parse open questions from one paper

1. In the repo where you want to run this, ensure this path exists:
    - `.opencode/skills/paper-question-parser/SKILL.md`
2. Invoke the skill with one source:
    - `/paper-question-parser /absolute/path/to/paper.pdf`
    - or `/paper-question-parser https://arxiv.org/abs/<id>`
    - or `/paper-question-parser https://doi.org/<doi>`
    - or `/paper-question-parser <direct-pdf-or-problem-page-url>`
3. Output is returned in chat and auto-saved to:
    - `outputs/parse-paper/<source_name_sanitized>.json`
    - `outputs/latest.json`
4. The parser now resolves local PDFs, arXiv URLs, DOI/publisher/HAL/DBLP/zbMATH/OpenAlex/Crossref landing pages, workshop/problem pages, and MathOverflow threads to one readable PDF or HTML source before extraction.
5. The canonical output schema lives in `.opencode/skills/paper-question-parser/SKILL.md`; parser outputs now include a top-level `source` object with the original URL/path, resolved locator, and title, and accepted items include `question_text`, `context_brief`, `meta`, and `evidence`.

## Skill 2: Refine one question into self-contained form

1. In the repo where you want to run this, ensure this path exists:
   - `.opencode/skills/paper-question-refiner/SKILL.md`
2. Invoke the skill with exactly one JSON object containing the question and arXiv ID:
   - `/paper-question-refiner {"question":"Let P(z) be a homogeneous polynomial of degree 4 in C[z] whose Hessian matrix Hes P is nilpotent, so P is Hessian nilpotent. If Delta := sum_{i=1}^n D_i^2 is the Laplace operator on C[z], must the iterated Laplacians of the powers of P eventually vanish in the sense that Delta^m(P(z)^(m+1)) = 0 for all sufficiently large m?","arxiv_id":"0704.1689"}`
3. Output is returned in chat as a strict JSON array of one or two rewrite artifacts:
   - one mandatory `context_only` artifact
   - one optional `reformulation` artifact when needed
4. Output is auto-saved to:
   - `outputs/runs/<arxiv_id_sanitized>--context-only.json`
   - optional `outputs/runs/<arxiv_id_sanitized>--reformulation.json`
   - `outputs/paper-question-refiner.latest.json` containing the exact JSON array returned in chat
5. The canonical output schema lives in `.opencode/skills/paper-question-refiner/SKILL.md`.
6. Optional batch runners read one JSON object per line from:
   - `targets_refiner` for `run_refiner.sh`
   - `targets_refiner2` for `run_refiner2.sh`

## Skill 3: Reconstruct one paper's backward mathematical genealogy

1. In the repo where you want to run this, ensure this path exists:
   - `.opencode/skills/math-genealogy-archaeologist/SKILL.md`
2. Invoke the skill with exactly one arXiv-first target:
   - `/math-genealogy-archaeologist https://arxiv.org/abs/<id>`
   - or `/math-genealogy-archaeologist https://arxiv.org/pdf/<id>.pdf`
   - or `/math-genealogy-archaeologist <arxiv_id>`
3. The skill is contract-bound and emits this fixed artifact set before any monologue:
   - `claim-ledger.json`
   - `trace.json`
   - `report.md`
   - `report.json`
   - `monologue.md`
4. This repo now includes a packaged example run for arXiv `2603.29576` at:
   - `outputs/math-genealogy-archaeologist/2603.29576/claim-ledger.json`
   - `outputs/math-genealogy-archaeologist/2603.29576/trace.json`
   - `outputs/math-genealogy-archaeologist/2603.29576/report.md`
   - `outputs/math-genealogy-archaeologist/2603.29576/report.json`
   - `outputs/math-genealogy-archaeologist/2603.29576/monologue.md`
5. The skill's fixed report ordering, source-access rules, and fail-closed behavior live in:
   - `.opencode/skills/math-genealogy-archaeologist/references/`

## Notes

- This bundle is skill-first (no external Python scripts required by user).
- It uses built-in tools such as `look_at`, `read`, `bash`, and web/search tools available in OpenCode.
- The parser skill, refiner skill, and math genealogy skill coexist; adding the newer skills does not replace the earlier ones.
- The parser skill supports non-arXiv scholarly URLs; the refiner skill remains arXiv-centered.
