# Invocation contract

## Placement

- Scope: project-local only
- Directory: `.opencode/skills/math-genealogy-factual-trace/`
- Entry file: `SKILL.md`
- Helper directory: `references/`

## Accepted V1 inputs

The skill accepts exactly one target paper input in one of these forms:

1. arXiv abs URL: `https://arxiv.org/abs/<id>`
2. arXiv PDF URL: `https://arxiv.org/pdf/<id>.pdf` or `https://arxiv.org/pdf/<id>`
3. Bare arXiv ID: `<id>`

All accepted forms normalize to one canonical arXiv target record for the run.

## Identity and provenance contract

- Resolve exactly one canonical paper node per run.
- Record the canonical node with `canonical_work_id`.
- Record every equivalent identifier or locator that collapsed into that node with `alias_ids`.
- Record the concrete artifact actually inspected with `observed_source_url` and `observed_version`.
- Record the observed source family with `source_type`.
- Never silently equate `canonical_work_id` with `observed_source_url` or `observed_version`.

In V1, arXiv is the primary identity authority. An arXiv abs URL, arXiv PDF URL, and bare arXiv ID for the same paper collapse to one canonical paper node. A linked journal, proceedings, or publisher page may still refer to the same underlying work, but it is not automatically the same observed version.

If the run encounters evidence that the arXiv target and a published version may have drifted, the runtime must surface an explicit version-conflict state and require reconciliation rather than silently merging them.

## Rejected inputs

- multiple URLs or IDs in one invocation
- non-arXiv-first inputs in V1
- malformed or ambiguous identifiers
- empty input

## Runtime contract

- The workflow is phase-based, not a one-shot prompt.
- The runtime should remain mostly non-interactive after receiving the target input.
- The runtime must select one explicit execution mode per run: `baseline` or `enriched`.
- Baseline operation must not depend on optional research MCPs and may assume only URL fetch plus local read and search once text is locally readable.
- Enriched mode may use optional runtime-exposed web, citation, or search tools, but enriched capabilities are optional rather than required for supported arXiv-first inputs.
- Both runtime modes must preserve identical public artifact names, artifact ordering, and report schemas.
- Bounded target ingestion must separate normalization, retrieval, localization, reading, and quoting.
- Bounded target ingestion must also keep retries and fallback transitions explicit rather than implicit.
- Bounded backward genealogy must follow the explicit ancestor-role taxonomy and stopping rules in `references/genealogy-selection.md`.
- All rendered factual outputs must derive from adjudicated claim records in `claim-ledger.json` rather than from free-form narration.
- The fixed report contract must use a stable public section order, as defined in `references/fixed-report-template.md`.
- The fixed report may only render adjudicated ledger claims and must not degrade into a backward summary of the target paper.
- The factual stage is the sole owner of quote-readiness decisions for downstream monologue rendering.
- The factual stage must expose whether quoted passages come from directly read sources and whether each quoted claim is eligible for downstream monologue use.
- The runtime must fetch the arXiv landing page before treating any PDF locator as readable target text.
- The runtime must use bounded retries only. It must not introduce unbounded retry loops for retrieval, localization, or readable-text fallback.
- The runtime must keep fallback ordering visible when moving among arXiv abs, localized PDF, and readable HTML or page-text paths.
- Every fetched item must carry an explicit source-access state chosen from `discovered`, `localized`, `read`, `quoted`, or `unverified`.
- The trace and structured report outputs must reserve mode metadata including selected mode, capabilities used, retry count, and fallback path taken.
- The skill is fail-closed: if target access, identity, version reconciliation, or core evidence is insufficient, it must stop with structured failure artifacts rather than fabricate conclusions.

## Monologue-readiness contract

- A factual bundle may be valid for report rendering while still being blocked for monologue rendering.
- The bundle must make monologue readiness explicit rather than implicit.
- The factual side must define a named blocking reason `insufficient_quote_coverage` when the report is factually valid but quote coverage is too weak for the downstream monologue contract.
- `insufficient_quote_coverage` applies when the bundle lacks enough quote-bearing, directly-read, monologue-eligible claims to support actual quoted passages in the downstream monologue.
- If `insufficient_quote_coverage` applies, the factual artifacts remain canonical, but the downstream monologue must fail closed or be omitted.

## Ancestor-role taxonomy contract

Allowed V1 ancestor roles are:

- `immediate seed`
- `supporting seed`
- `deep ancestor`
- `technique ancestor`
- `author-local clue`
- `negative ancestor`

Every ancestor edge must include an explicit written inclusion reason plus explicit source support. External commentary, blog posts, summaries, and author pages may reinforce an already-supported edge, but they cannot by themselves create a core seed or ancestor edge.

## Source-access state model

- `discovered`: the runtime identified a source locator or landing page candidate but has not localized or read target text from it.
- `localized`: the runtime copied or otherwise localized a remote source into a form that may become readable locally, but text has not yet been read from it.
- `read`: the runtime successfully read target text from the source.
- `quoted`: the runtime emitted a quotation backed by text it read from that source.
- `unverified`: the runtime could not verify readable target text or could not confirm that a quotation came from readable target text.

The state model is monotonic evidence, not a guess about intent. A broken URL, unreadable file, or abstract-only page that never yielded the target text must not be promoted to `read`.

## Failure handling requirements

- Broken or malformed target URLs must be recorded as failed retrieval in the trace and left `unverified`.
- arXiv landing-page access without readable full target text must remain explicit; metadata-only or abstract-only access does not count as `read` for the paper body.
- Remote PDFs are not directly readable by assumption. They may only contribute `read` evidence after localization into a readable local form.
- Retry exhaustion and fallback exhaustion must be recorded explicitly in the trace rather than hidden as generic failure.
- Enriched-only capabilities may improve coverage, but the runtime must not treat their absence as a contract failure for otherwise supported arXiv inputs.
- If required target text remains unavailable after bounded retrieval and localization attempts, the run must fail closed instead of continuing as though the paper was read.

## Stable output artifacts

The factual stage reserves these public artifact names for the run output:

- `report.md`
- `report.json`
- `claim-ledger.json`
- `trace.json`

These names are fixed so later benchmark and loader tests can target them reliably.

## Claim-ledger rendering contract

- `claim-ledger.json` is the audited evidence ledger for all later outputs.
- Every renderable statement in `report.md` and `report.json` must trace to an adjudicated claim record in the ledger.
- `report.md` and `report.json` must render the stable section sequence defined in `references/fixed-report-template.md`.
- `report.md` and `report.json` must render fail-closed variants from `references/fail-closed-output.md` when the evidence base is insufficient, conflicted, or inaccessible.
- Claim records must preserve claim type, source tier, source-access level, quotation or excerpt support, `quote_kind`, `directly_read`, `monologue_quote_eligible`, and confidence as separate fields.
- Unsupported, downgraded, unread, abstract-only, indirectly quoted, conflict-marked, or notation-unsafe claims must stay visibly restricted in the ledger and must not silently become later report facts.
- The report renderer is not allowed to introduce new claims by paraphrasing the target paper backward from its abstract, bibliography, or conclusions. If a statement is not present as an adjudicated ledger claim, it is not renderable.
