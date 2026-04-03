# Paper Question Tools Bundle

This folder contains local OpenCode skills and runtime artifacts for prompt-driven paper-question workflows.

## Included

- `.opencode/skills/paper-question-parser/SKILL.md`
- `.opencode/skills/paper-question-refiner/SKILL.md`
- `.opencode/skills/math-genealogy-factual-trace/SKILL.md`
- `.opencode/skills/math-genealogy-reconstructed-monologue/SKILL.md`
- `.opencode/skills/math-genealogy-archaeologist/SKILL.md`
- `outputs/latest.json`
- `outputs/paper-question-refiner.latest.json`
- `outputs/parse-paper/*.json`
- `outputs/math-genealogy-archaeologist/<arxiv_id>/`

## Skill 1: Parse open questions from one paper

1. In the repo where you want to run this, ensure this path exists:
    - `.opencode/skills/paper-question-parser/SKILL.md`
2. Invoke the skill with one paper source:
    - `/paper-question-parser /absolute/path/to/paper.pdf`
    - or `/paper-question-parser https://arxiv.org/abs/<id>`
3. Output is returned in chat and auto-saved to:
    - `outputs/parse-paper/<input_name_sanitized>.json`
    - `outputs/latest.json`
4. The canonical output schema lives in `.opencode/skills/paper-question-parser/SKILL.md`; accepted items now include `question_text`, `context_brief`, `meta`, and `evidence`.

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

## Skill 3: Build the canonical factual genealogy bundle

1. In the repo where you want to run this, ensure this path exists:
   - `.opencode/skills/math-genealogy-factual-trace/SKILL.md`
2. Invoke the skill with exactly one arXiv-first target:
   - `/math-genealogy-factual-trace https://arxiv.org/abs/<id>`
   - or `/math-genealogy-factual-trace https://arxiv.org/pdf/<id>.pdf`
   - or `/math-genealogy-factual-trace <arxiv_id>`
3. This is the authoritative stage. It owns retrieval, source-access tracking, genealogy selection, adjudication, quote-readiness, fail-closed decisions, and the fixed report artifacts:
   - `claim-ledger.json`
   - `trace.json`
   - `report.md`
   - `report.json`
4. The factual bundle is canonical. A later monologue may depend on it, but may not override it.

## Skill 4: Render the reconstructed monologue from a frozen factual bundle

1. In the repo where you want to run this, ensure this path exists:
   - `.opencode/skills/math-genealogy-reconstructed-monologue/SKILL.md`
2. Invoke the skill with exactly one factual bundle directory path:
   - `/math-genealogy-reconstructed-monologue /absolute/path/to/outputs/math-genealogy-archaeologist/<arxiv_id>`
3. Required upstream artifacts in that directory are:
   - `claim-ledger.json`
   - `trace.json`
   - `report.md`
   - `report.json`
4. This skill writes only:
    - `monologue.md`
5. The monologue is derived but independently readable. It is not canonical evidence and must not be run safely without a frozen factual bundle.
6. A compliant monologue run should continue expanding autonomously until it reaches the full downstream target length and route-development requirements, unless a named fail-closed blocker stops it.

## Skill 5: Compatibility wrapper for the split genealogy flow

1. In the repo where you want to run this, ensure this path exists:
   - `.opencode/skills/math-genealogy-archaeologist/SKILL.md`
2. Invoke the skill with exactly one arXiv-first target:
   - `/math-genealogy-archaeologist https://arxiv.org/abs/<id>`
   - or `/math-genealogy-archaeologist https://arxiv.org/pdf/<id>.pdf`
   - or `/math-genealogy-archaeologist <arxiv_id>`
3. The wrapper preserves the legacy arXiv-first entrypoint but now runs a two-stage pipeline:
   - factual trace first
   - reconstructed monologue second only if the factual bundle authorizes it
4. The public output bundle stays stable:
   - `claim-ledger.json`
   - `trace.json`
   - `report.md`
   - `report.json`
   - `monologue.md`
5. This repo includes a packaged example run for arXiv `2603.29576` at:
   - `outputs/math-genealogy-archaeologist/2603.29576/claim-ledger.json`
   - `outputs/math-genealogy-archaeologist/2603.29576/trace.json`
   - `outputs/math-genealogy-archaeologist/2603.29576/report.md`
   - `outputs/math-genealogy-archaeologist/2603.29576/report.json`
   - `outputs/math-genealogy-archaeologist/2603.29576/monologue.md`
   - `outputs/math-genealogy-archaeologist/2603.29576/LEGACY_NOTE.md`
6. The packaged `2603.29576` monologue is a compliant example of the split monologue-side contract, while the directory itself remains a legacy combined-wrapper bundle shape.
7. Authority hierarchy:
   - factual bundle is canonical
   - monologue is derived narrative
   - wrapper preserves user-facing entrypoint and fail-closed dependency

## Notes

- This bundle is skill-first (no external Python scripts required by user).
- It uses built-in tools such as `look_at`, `read`, `bash`, and web/search tools available in OpenCode.
- The parser skill, refiner skill, factual genealogy skill, reconstructed monologue skill, and compatibility wrapper coexist.
