# Report and artifact schema

## Artifact set

### `report.md`

Human-readable fixed report.

`report.md` is not a free-form essay. It must render the stable section order and exact fail-closed branches defined in `fixed-report-template.md` and `fail-closed-output.md`.

The public section order is fixed:

1. `## Source ledger`
2. `## Seed ranking`
3. `## Pressure points`
4. `## Missing-cell analysis`
5. `## Transfer-vs-novelty boundary`
6. `## Blind reconstruction`
7. `## Comparison with target`
8. `## Reconstructed question`
9. `## Confidence and uncertainty`

Those sections must stay in that order for both full reports and any partial fail-closed report variant that can still be rendered. The renderer may omit normal-success sections only when `fail-closed-output.md` explicitly says to replace them with a named failure form.

Every section must be populated from adjudicated ledger entries only. The report must not devolve into a backward summary of the target paper, a bibliography recap, or a narration that treats unread evidence as settled.

### `report.json`

Machine-readable structured version of the fixed report.

At minimum, the structured payload must keep paper identity separate from the concrete observation by preserving stable provenance fields such as `canonical_work_id`, `observed_source_url`, `observed_version`, `alias_ids`, and `source_type`.

It must also reserve structured space for genealogy selection outputs, including each ancestor node or edge's `ancestor_role`, `inclusion_reason`, `edge_source_support`, and `outward_check_status`, even though V1 does not yet define the full rendered report sections for those fields.

`report.json` must preserve the same stable section order in a machine-readable form, plus a top-level report mode field such as `full_report` or one of the named fail-closed variants from `fail-closed-output.md`.

`report.json` must also reserve runtime-mode metadata without changing the section schema between `baseline` and `enriched` runs.

The structured payload must reserve space for:

- `source_ledger`
- `seed_ranking`
- `pressure_points`
- `missing_cell_analysis`
- `transfer_vs_novelty_boundary`
- `blind_reconstruction`
- `comparison_with_target`
- `reconstructed_question`
- `confidence_and_uncertainty`
- `report_mode`
- `fail_closed_reason`
- `execution_mode`
- `capabilities_used`
- `retry_count`
- `fallback_path`
- `monologue_readiness`

Each section payload must be renderable from adjudicated ledger entries only.

### `claim-ledger.json`

Frozen evidence ledger that later renderers must consume instead of inventing new facts.

At minimum, each claim entry must preserve `paper_node`, `claim_text`, `claim_type`, `source_access_level`, `source_tier`, `quotation_or_excerpt`, `quote_kind`, `directly_read`, `monologue_quote_eligible`, and `confidence`, with adjudication outcomes kept explicit rather than collapsed into prose.

The top-level payload should also reserve a `monologue_readiness` block that explains whether the bundle can support downstream actual quoted passages.

### `trace.json`

Run trace capturing normalization, execution mode, capabilities used, phase transitions, bounded retries, fallback path taken, quote-readiness decisions, and fail-closed reasons when relevant.

When duplicate URLs collapse or version drift is detected, record that normalization or reconciliation outcome explicitly in the trace rather than hiding it in free text.

At minimum, the trace must surface per-source access progress and failure states for each fetched item, including whether it was only `discovered`, successfully `localized`, actually `read`, later `quoted`, or left `unverified`.

The trace must make bounded retry behavior visible by reserving at least `execution_mode`, `capabilities_used`, `retry_count`, and `fallback_path` fields rather than burying those choices in prose.

The trace must also reserve space for genealogy stopping-limit outcomes, including recursion depth reached, evidence-quality stop reasons, and whether the one outward reinforcement check was used.

Broken URLs, unreadable targets, abstract-only access, retry exhaustion, fallback exhaustion, and `insufficient_quote_coverage` must be reported as explicit source-access or downstream-readiness outcomes rather than being described as if the paper body had been read.

## Ordering invariant

1. `claim-ledger.json` and `trace.json` may be produced during evidence work.
2. `report.md` and `report.json` are finalized after adjudication.
3. Downstream monologue rendering, if any, comes strictly after the factual bundle is complete.
4. `report.md` and `report.json` may only render adjudicated ledger claims.
5. `report.md` and `report.json` must preserve the stable section order from `fixed-report-template.md`.
6. Named fail-closed outputs must stay visibly distinct from a full report and must use the variants defined in `fail-closed-output.md`.
7. The factual side owns monologue-readiness and quote-eligibility metadata, but not `monologue.md` generation itself.

## Current scope

This scaffold now locks file names, sequencing, ingestion-trace expectations, fixed report section order, fail-closed report modes, claim-ledger rendering dependence, and the downstream handoff boundary.
