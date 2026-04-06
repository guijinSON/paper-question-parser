---
name: math-genealogy-research-trajectory
description: "Downstream-only genealogy research-trajectory skill that consumes a frozen factual bundle directory and writes a long-form ideation transcript plus a minimal validation manifest. It never performs retrieval, genealogy selection, or adjudication."
argument-hint: "</absolute/path/to/factual-bundle-directory>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
---

# Math Genealogy Research Trajectory

Use this skill when the user wants a long-form research-ideation transcript for a genealogy run that already has a frozen factual bundle.

This skill is downstream-only. It is a second-pass renderer over the frozen ledger and completed report. It consumes a factual bundle directory and produces `trajectory.md` plus the minimal validation sidecar `trajectory.manifest.json`.

The purpose of the trajectory is to simulate a mathematician reading the target paper, generating ideas, trying neighboring routes, abandoning weak directions, revising the problem, and synthesizing a direction that could advance the mathematics without pretending to be a factual record of private author thoughts.

## Required references

Before doing any substantive work, load these project-local references and treat them as the contract for this skill:

- @references/contract.md
- @references/trajectory-style.md
- @references/trajectory-tag-grammar.md
- @references/trajectory-guardrails.md
- @references/fail-closed-rules.md

## Input contract

The argument must be a factual bundle directory path, not a raw paper identifier.

The bundle directory must already contain all of these upstream artifacts:

- `trace.json`
- `claim-ledger.json`
- `report.md`
- `report.json`

If the directory is missing any required upstream file, or if the factual bundle reports an upstream-failed or insufficient-evidence state for downstream ideation, fail closed instead of improvising.

## Authority boundary

- Do not accept raw arXiv URLs or bare arXiv IDs.
- Do not perform retrieval, normalization, landing-page access, PDF localization, genealogy selection, or adjudication.
- Do not render `report.md`, `report.json`, `trace.json`, or `claim-ledger.json`.
- Do not reopen the factual bundle by adding new papers, new quotes, new facts, or new descendant-aware hints.
- Do not use later descendants, overlap judgments, or evaluator outputs at generation time.

## Rendering workflow

1. read the factual bundle directory and confirm the required upstream files are present
2. read `claim-ledger.json` and `report.md` / `report.json` as the canonical frozen evidence base
3. check downstream ideation blockers before drafting, including missing target access, upstream-failed state, and insufficient grounded ideation evidence, using the frozen bundle's existing evidence-quality fields rather than descendant-aware guessing
4. draft `trajectory.md` as a non-linear, first-person ideation transcript using only the frozen bundle and the trajectory tag grammar
5. emit `trajectory.manifest.json` as a minimal validator-facing sidecar with artifact metadata, structural markers, evidence references, and blocker flags only
6. run an explicit self-critique pass against the trajectory guardrails after the first complete draft
7. revise the draft and run one more self-critique pass, specifically checking for descendant leakage, unsupported new facts, overconfident synthesis, and missing failed-route development
8. if the draft is still materially below the required route-development depth, still lacks the required trajectory tags, or still contains guardrail violations, continue revising within the same run rather than stopping for human feedback

The trajectory skill is a second-pass renderer over the frozen ledger and completed report, not a parallel output path and not another genealogy analyzer.

## Revision discipline

- Treat every first complete draft as provisional rather than finished.
- Before writing the final `trajectory.md`, perform at least two revision passes inside the same run.
- In each revision pass, remove or weaken any sentence that turns supported synthesis into settled fact unless that stronger relation is explicit in the frozen evidence.
- In each revision pass, remove any sentence that smuggles in new papers, future knowledge, or descendant-aware method hints.
- In each revision pass, mark speculative bridges visibly as plausible reconstruction or hypothetical exploration rather than letting them harden into historical fact.
- In each revision pass, ensure the transcript still contains multiple failed lines of effort instead of collapsing into a polished retrospective summary.
- Do not treat summary-only target access as enough to simulate reading the paper live; the opening route-development beats require at least one directly read, renderable, quote-bearing target claim.

## Output boundary

- Write only `trajectory.md` and `trajectory.manifest.json` into the same bundle directory.
- Keep the existing public artifact names stable.
- If the factual bundle is blocked, fail closed rather than writing a best-effort trajectory anyway.
- Do not stop at a short partial draft when the bundle is downstream-ready; continue iterating until the trajectory satisfies the style contract or a named fail-closed blocker is reached.
