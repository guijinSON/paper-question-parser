# Paper Question Parser Bundle

This folder contains the skill and runtime artifacts needed for the prompt-driven paper parsing flow.

## Included

- `.opencode/skills/paper-question-parser/SKILL.md`
- `outputs/latest.json`
- `outputs/runs/*.json`

## How to use

1. In the repo where you want to run this, ensure this path exists:
   - `.opencode/skills/paper-question-parser/SKILL.md`
2. Invoke the skill with one paper source:
    - `/paper-question-parser /absolute/path/to/paper.pdf`
    - or `/paper-question-parser https://arxiv.org/abs/<id>`
3. Output is returned in chat and auto-saved to:
    - `outputs/runs/<input_name_sanitized>.json`
    - `outputs/latest.json`
4. The canonical output schema lives in `.opencode/skills/paper-question-parser/SKILL.md`; accepted items now include `question_text`, `context_brief`, `meta`, and `evidence`.

## Notes

- This flow is skill-first (no external Python scripts required by user).
- It uses built-in tools such as `look_at` and `bash` available in OpenCode.
