---
name: math-genealogy-archaeologist
description: "Compatibility wrapper for the split genealogy pipeline. Accepts arXiv abs URLs, arXiv PDF URLs, and bare arXiv IDs, runs the factual trace stage first, then optionally runs the reconstructed monologue stage over the frozen factual bundle. Preserves the public output bundle names and path."
argument-hint: "<arXiv abs URL | arXiv PDF URL | bare arXiv ID>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
  - Write
  - Bash
---

# Math Genealogy Archaeologist

Use this skill when the user wants the legacy arXiv-first entrypoint for one paper's backward mathematical genealogy, with a fixed report first and a monologue second.

This is now a compatibility wrapper. It orchestrates a one-way pipeline:

1. `math-genealogy-factual-trace` runs first and owns retrieval, bounded source reading, genealogy selection, adjudication, quote-readiness, fail-closed decisions, and the canonical factual artifacts.
2. `math-genealogy-reconstructed-monologue` runs second and consumes the frozen factual bundle directory only.

The wrapper preserves the public bundle shape under `outputs/math-genealogy-archaeologist/<arxiv_id>/` with stable artifact names:

- `trace.json`
- `claim-ledger.json`
- `report.md`
- `report.json`
- `monologue.md`

## Split authority

- Canonical factual rules live under `.opencode/skills/math-genealogy-factual-trace/`.
- Canonical monologue rules live under `.opencode/skills/math-genealogy-reconstructed-monologue/`.
- This wrapper does not duplicate those full contracts.

## Wrapper input contract

Accept exactly one V1 input in one of these shapes:

1. `https://arxiv.org/abs/<id>`
2. `https://arxiv.org/pdf/<id>.pdf` or `https://arxiv.org/pdf/<id>`
3. Bare arXiv ID such as `2603.18531`

Normalize all accepted forms to one canonical arXiv target before the factual stage begins. If the input is missing, ambiguous, or not an accepted V1 shape, fail closed.

## Wrapper orchestration

### Stage 1: factual trace first

Invoke the factual skill first. It owns:

- arXiv-first normalization
- bounded ingestion and source-access recording
- genealogy selection
- evidence adjudication
- quote-readiness and `insufficient_quote_coverage` decisions
- rendering `trace.json`, `claim-ledger.json`, `report.md`, and `report.json`

### Stage 2: monologue second

Invoke the monologue skill only after the factual stage has completed and only against the frozen factual bundle directory.

The monologue skill is a second-pass renderer over the frozen ledger and completed report. It does not perform retrieval or adjudication.
When the factual bundle is downstream-ready, the monologue stage should continue expanding within the same run until it reaches the compliant full-length target or hits a named fail-closed blocker; it should not stop for human feedback after a short partial draft.

### Stage 3: fail-closed dependency

- If the factual stage fails closed, stop there.
- If the factual stage sets `monologue_readiness.status = insufficient_quote_coverage`, preserve the factual bundle and do not generate a best-effort monologue.
- Preserve the stable artifact order: factual artifacts first, monologue second only when authorized.

## Canonical paths

- Factual skill entrypoint: `.opencode/skills/math-genealogy-factual-trace/SKILL.md`
- Monologue skill entrypoint: `.opencode/skills/math-genealogy-reconstructed-monologue/SKILL.md`
- Public wrapper entrypoint: `.opencode/skills/math-genealogy-archaeologist/SKILL.md`

## Compatibility note

The old mixed reference directory remains only as a compatibility map. The authoritative contracts now live in the two split skills above.
