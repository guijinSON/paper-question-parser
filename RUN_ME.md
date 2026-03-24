# Paper Question Tools Bundle

This folder contains local OpenCode skills and runtime artifacts for prompt-driven paper-question workflows.

## Included

- `.opencode/skills/paper-question-parser/SKILL.md`
- `.opencode/skills/paper-question-refiner/SKILL.md`
- `outputs/latest.json`
- `outputs/paper-question-refiner.latest.json`
- `outputs/parse-paper/*.json`

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

## Notes

- This bundle is skill-first (no external Python scripts required by user).
- It uses built-in tools such as `look_at`, `read`, `bash`, and web/search tools available in OpenCode.
- The parser skill and refiner skill coexist; adding the second skill does not replace the first one.
