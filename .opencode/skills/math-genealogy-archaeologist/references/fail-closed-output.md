# Fail-closed report modes

## Purpose

Fail-closed output must stay visibly distinct from a successful full report.

- A fail-closed report is not a complete success case.
- It must name the blocking mode explicitly.
- It may render only the sections that still have adjudicated support.
- It must not imitate the tone or completeness of a full-confidence report.

## Named variants

The renderer must support at least these named fail-closed variants:

1. `insufficient_target_access`
2. `insufficient_genealogy`
3. `conflicting_evidence`

These names are part of the contract and must stay stable.

## Variant requirements

### `insufficient_target_access`

Use this when bounded ingestion failed to produce the readable target text required for the report contract.

- Keep `## Source ledger`.
- Keep `## Confidence and uncertainty`.
- Replace the middle genealogy-analysis sections with an explicit statement that target access was insufficient.
- Do not present seed ranking, transfer-vs-novelty, blind reconstruction, comparison with target, or reconstructed question as though the target paper had been read.

### `insufficient_genealogy`

Use this when target access succeeded but the bounded backward genealogy did not yield enough adjudicated support to populate the core analysis sections.

- Keep `## Source ledger`.
- Keep any section whose content is directly supported by adjudicated ledger entries, with missing sections marked unavailable.
- Keep `## Confidence and uncertainty` with an explicit statement that the genealogy evidence floor was not met.
- Do not pad the missing sections with target-paper summary or unsupported speculation.

### `conflicting_evidence`

Use this when material conflicts remain unresolved after adjudication and those conflicts block a stable reconstruction.

- Keep `## Source ledger`.
- Keep `## Pressure points` and `## Missing-cell analysis` if they are supported.
- Keep `## Confidence and uncertainty` with the unresolved conflict made explicit.
- Do not render a settled seed ranking, reconstructed question, or comparison-with-target conclusion if the conflict blocks them.

## Fail-closed rendering rules

- Every fail-closed output must include a visible `report_mode` marker in `report.json` and an equivalent human-readable marker in `report.md`.
- Fail-closed sections may only render adjudicated ledger claims that remain valid under the named failure mode.
- The renderer must not silently fall back from a blocked section into a narrative summary of the target paper.
- If more than one fail-closed condition applies, choose the earliest blocking mode in the workflow unless `conflicting_evidence` is the later dominant blocker for already-read evidence.
