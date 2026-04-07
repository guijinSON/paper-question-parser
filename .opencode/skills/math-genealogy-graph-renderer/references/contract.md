# Graph renderer invocation contract

## Placement

- Scope: project-local only
- Directory: `.opencode/skills/math-genealogy-graph-renderer/`
- Entry file: `SKILL.md`
- Helper directory: `references/`

## Accepted V1 input

The skill accepts exactly one input: a factual bundle directory path.

That directory must contain:

- `trace.json`
- `claim-ledger.json`
- `report.md`
- `report.json`

## Rejected inputs

- raw arXiv abs URLs
- raw arXiv PDF URLs
- bare arXiv IDs
- multiple directories or mixed inputs
- any bundle missing required upstream artifacts

## One-way authority rule

- The factual bundle is canonical and authoritative.
- `genealogy.svg` is derived but independently parseable.
- The graph renderer may choose layout, grouping, and drawing order only within the frozen evidence base and deterministic SVG rules.
- The graph renderer must not perform retrieval, genealogy selection, or adjudication.
- The graph renderer must not add new papers, new factual claims, new ancestry relations, or non-evidenced labels beyond the bundle.

## Completion rule

- Success means the skill emits a valid static SVG when the bundle is downstream-ready for graph rendering.
- If the bundle is renderable, the skill must finish a deterministic `genealogy.svg` in the same run rather than stopping after a partial structure.
- If required upstream artifacts are missing, the bundle reports upstream failure, or no adjudicated renderable genealogy relations remain, fail closed instead of inventing graph structure.
- The graph renderer must validate stable ordering, stable IDs, and escaped text before finalizing `genealogy.svg`.

## Output contract

- The only artifact this skill writes is `genealogy.svg`.
- The graph is a second-pass renderer over the frozen ledger and completed report.
- If the factual bundle is missing required files, is blocked by upstream failure, or lacks renderable genealogy relations, the skill must fail closed instead of writing a placeholder image.
