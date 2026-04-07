---
name: math-genealogy-reconstructed-monologue
description: "Downstream-only genealogy monologue skill that consumes a frozen factual bundle directory and writes only monologue.md. It never performs retrieval, genealogy selection, or adjudication."
argument-hint: "</absolute/path/to/factual-bundle-directory>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
---

# Math Genealogy Reconstructed Monologue

Use this skill when the user wants the long-form reconstructed discovery transcript for a genealogy run that already has a frozen factual bundle.

This skill is downstream-only. It is a second-pass renderer over the frozen ledger and completed report. It consumes a factual bundle directory and produces only `monologue.md`.

The purpose of the monologue is to sound like a real mathematician's working notebook while deriving the target paper's research topic from tensions, failures, and partial inheritances visible in its ancestors.

## Required references

Before doing any substantive work, load these project-local references and treat them as the contract for this skill:

- @references/contract.md
- @references/monologue-style.md
- @references/pseudo-tag-grammar.md
- @references/monologue-guardrails.md

## Input contract

The argument must be a factual bundle directory path, not a raw paper identifier.

The bundle directory must already contain all of these upstream artifacts:

- `trace.json`
- `claim-ledger.json`
- `report.md`
- `report.json`

If the directory is missing any required upstream file, or if the factual bundle reports a fail-closed or blocked monologue state, fail closed instead of improvising.

## Authority boundary

- Do not accept raw arXiv URLs or bare arXiv IDs.
- Do not perform retrieval, normalization, landing-page access, PDF localization, genealogy selection, or adjudication.
- Do not render `report.md`, `report.json`, `trace.json`, or `claim-ledger.json`.
- Do not reopen the factual bundle by adding new papers, new quotes, or new claims.

## Rendering workflow

1. read the factual bundle directory and confirm the required upstream files are present
2. read `claim-ledger.json` and `report.md` / `report.json` as the canonical frozen evidence base
3. check the bundle's monologue-readiness status and quote-eligibility fields before drafting
4. render `monologue.md` only if the bundle is downstream-ready
5. run an explicit self-critique pass against the monologue guardrails after the first complete draft
6. revise the draft and run one more self-critique pass, specifically checking for intention-language, overconfident historical synthesis, and unmarked hypothetical bridges
7. if the draft is still materially below the full compliant target length, still misses required route-development beats, or still contains guardrail violations, continue revising within the same run rather than stopping for human feedback

The monologue is a second-pass renderer over the frozen ledger and completed report, not a parallel output path and not another genealogy analyzer.

## Revision discipline

- Treat every first complete draft as provisional rather than finished.
- Before writing the final `monologue.md`, perform at least two revision passes inside the same run.
- In each revision pass, specifically remove or weaken any sentence that attributes intentions, goals, motives, or strategy to the paper or its authors unless that language is directly supported by the factual bundle.
- In each revision pass, weaken any sentence that turns bounded synthesis into settled historical structure unless the relation is explicit in the frozen evidence.
- In each revision pass, mark any hypothetical bridge as plausible reconstruction rather than letting it read as settled fact.

## Output boundary

- Write only `monologue.md` into the same bundle directory.
- Keep the existing public artifact names stable.
- If the factual bundle is blocked, fail closed rather than writing a best-effort monologue anyway.
- Do not stop at a short partial draft when the bundle is downstream-ready; continue iterating until the monologue satisfies the style contract or a named fail-closed blocker is reached.
