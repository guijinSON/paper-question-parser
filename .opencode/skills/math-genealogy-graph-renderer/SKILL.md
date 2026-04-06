---
name: math-genealogy-graph-renderer
description: "Downstream-only genealogy graph skill that consumes a frozen factual bundle directory and writes only genealogy.svg. It never performs retrieval, genealogy selection, or adjudication."
argument-hint: "</absolute/path/to/factual-bundle-directory>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
---

# Math Genealogy Graph Renderer

Use this skill when the user wants a deterministic genealogy graph for a run that already has a frozen factual bundle.

This skill is downstream-only. It is a second-pass renderer over the frozen ledger and completed report. It consumes a factual bundle directory and produces only `genealogy.svg`.

The purpose of the graph is to render the frozen genealogy structure into a stable SVG artifact that later tooling can parse, validate, and compare without fresh evidence work.

## Required references

Before doing any substantive work, load these project-local references and treat them as the contract for this skill:

- @references/contract.md
- @references/deterministic-svg-rules.md
- @references/graph-render-guardrails.md

## Input contract

The argument must be a factual bundle directory path, not a raw paper identifier.

The bundle directory must already contain all of these upstream artifacts:

- `trace.json`
- `claim-ledger.json`
- `report.md`
- `report.json`

If the directory is missing any required upstream file, or if the factual bundle reports an upstream-failed state that leaves no renderable genealogy evidence, fail closed instead of improvising.

## Authority boundary

- Do not accept raw arXiv URLs or bare arXiv IDs.
- Do not perform retrieval, normalization, landing-page access, PDF localization, genealogy selection, or adjudication.
- Do not render `report.md`, `report.json`, `trace.json`, or `claim-ledger.json`.
- Do not reopen the factual bundle by adding new papers, new claims, new edges, or inferred labels that are not supported by the frozen evidence.

## Rendering workflow

1. read the factual bundle directory and confirm the required upstream files are present
2. read `claim-ledger.json` as the primary frozen graph input, then use `report.md` and `report.json` only for compatible bundle context that does not override the ledger
3. confirm the bundle has renderable genealogy nodes and relations, or fail closed if the factual bundle blocks downstream graph output
4. render `genealogy.svg` only from the frozen evidence base
5. apply the deterministic SVG rules before finalizing output, including stable node ordering, stable edge ordering, stable element IDs, and escaped text content
6. verify that the final SVG contains only valid static SVG structure for this contract, with no HTML, scripting, raster export, or interactive behavior

The graph renderer is a second-pass renderer over the frozen ledger and completed report, not a parallel output path and not another genealogy analyzer.

## Output boundary

- Write only `genealogy.svg` into the same bundle directory.
- Keep the existing public artifact names stable.
- If the factual bundle is blocked by upstream failure, missing required artifacts, or lacks renderable genealogy relations after adjudication, fail closed rather than writing a best-effort graph.
- The output must be a deterministic static SVG, not HTML, not PNG, and not an interactive document.
