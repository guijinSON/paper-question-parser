# Runtime modes

## Purpose

This helper defines the explicit execution modes for the V1 factual runtime. The mode controls which capabilities may be used, but it does not change the required artifact set, artifact order, report schema, quote-readiness contract, or fail-closed behavior.

## Supported execution modes

- `baseline`
- `enriched`

Every run must record which mode was selected.

## Baseline mode

`baseline` mode must remain viable using only the currently locked tool surface for this skill: `Read`, `Grep`, `Glob`, `WebFetch`, `Write`, and `Bash`.

Baseline mode may assume only URL fetch plus local read and search once text has been localized or otherwise made locally readable.

Baseline mode must not depend on optional web, citation, or search MCPs for supported arXiv-first inputs.

## Enriched mode

`enriched` mode may use optional runtime-exposed web, citation, or search tools when they are available.

Enriched mode is optional rather than required for supported arXiv-first inputs.

If optional capabilities are unavailable, the runtime must remain able to continue in `baseline` mode or fail closed for normal evidence reasons rather than for missing enrichment alone.

## Shared invariants across both modes

1. Output schemas remain identical across `baseline` and `enriched`.
2. Artifact names remain `report.md`, `report.json`, `claim-ledger.json`, and `trace.json` on the factual side.
3. Both modes remain claim-ledger first and fail closed when required evidence is unavailable.
4. Both modes must keep retries bounded and fallback ordering explicit.
5. Both modes must preserve the same monologue-readiness signaling fields for downstream use.

## Required trace metadata

At minimum, `trace.json` and any structured report payload must reserve fields for:

- `execution_mode`
- `capabilities_used`
- `retry_count`
- `fallback_path`

Those markers must describe what actually happened in the run, not what the runtime wished had happened.

## Retry and fallback policy

1. Retries must be bounded per step. No unbounded retry loops are allowed.
2. The runtime must surface retry exhaustion explicitly.
3. Fallback order for supported arXiv-first inputs is: arXiv abs or landing-page text, then localized PDF text, then readable HTML or page-text where applicable.
4. Every fallback transition must be visible in the trace.
5. Missing enriched capabilities are not by themselves a reason to skip the baseline-compatible fallback path.
