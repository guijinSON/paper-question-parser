# Monologue invocation contract

## Placement

- Scope: project-local only
- Directory: `.opencode/skills/math-genealogy-reconstructed-monologue/`
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
- `monologue.md` is derived but independently readable.
- The monologue skill may dramatize order, emphasis, and local reasoning movement, but only within the frozen evidence base.
- The monologue skill must not perform retrieval, genealogy selection, or adjudication.
- The monologue skill must not add new papers, new factual claims, or new quoted passages beyond the bundle.

## Output contract

- The only artifact this skill writes is `monologue.md`.
- The monologue is a second-pass renderer over the frozen ledger and completed report.
- If the factual bundle says `monologue_readiness.status` is `blocked_by_upstream_failure` or `insufficient_quote_coverage`, fail closed.
