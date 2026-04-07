# Research trajectory invocation contract

## Placement

- Scope: project-local only
- Directory: `.opencode/skills/math-genealogy-research-trajectory/`
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
- `trajectory.md` is derived but independently readable.
- `trajectory.manifest.json` is derived but independently machine-parseable.
- The trajectory skill may dramatize order, emphasis, and local search movement only within the frozen evidence base.
- The trajectory skill must not perform retrieval, genealogy selection, adjudication, or descendant comparison.
- The trajectory skill must not add new papers, new factual claims, or descendant-aware hints beyond the bundle.

## Completion rule

- A first draft is not success by itself.
- Success means the trajectory satisfies the downstream style contract, includes failed routes and revision movement, and emits a valid manifest sidecar.
- Success also requires at least one directly read, renderable, quote-bearing target claim so the transcript can open from actual target-paper pressure rather than summary-only access.
- If the bundle is downstream-ready, the trajectory skill must continue expanding within the same run until it reaches compliant completion or encounters a named fail-closed blocker.
- Before finalizing output, the skill must run at least two internal revision passes against the trajectory guardrails.
- A draft is not compliant if it still contains descendant leakage, unsupported new facts, missing route-development beats, or unmarked speculative bridges.

## Output contract

- The only artifacts this skill writes are `trajectory.md` and `trajectory.manifest.json`.
- The trajectory is a second-pass renderer over the frozen ledger and completed report.
- The manifest exists only for contract validation, provenance references, and structural checks; it does not replace the text artifact.
- If the factual bundle is missing required files, is blocked by upstream failure, or lacks enough grounded evidence to support a bounded ideation transcript, the skill must fail closed instead of writing placeholder output.
