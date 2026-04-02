---
name: math-genealogy-archaeologist
description: "ArXiv-first skill scaffold for reconstructing a paper's backward mathematical genealogy into a fixed evidence-backed report and a grounded monologue. Accepts arXiv abs URLs, arXiv PDF URLs, and bare arXiv IDs. Fails closed when the contract cannot be satisfied."
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

Use this skill when the user wants an arXiv-first investigation of one paper's backward mathematical genealogy, with a fixed report first and a monologue second.

This scaffold locks the contract, file layout, output artifact names, paper identity policy, genealogy-selection rules, claim-ledger schema, adjudication rules, report-before-monologue ordering, and the grounded second-pass monologue boundary.

## Required references

Before doing any substantive work, load these project-local references and treat them as the contract for this skill:

- @references/contract.md
- @references/runtime-modes.md
- @references/identity-policy.md
- @references/ingestion-workflow.md
- @references/genealogy-selection.md
- @references/report-schema.md
- @references/fixed-report-template.md
- @references/claim-ledger-schema.md
- @references/evidence-adjudication.md
- @references/source-policy.md
- @references/fail-closed-output.md
- @references/monologue-policy.md
- @references/grounded-monologue-template.md

## Phase workflow

### Phase 0: Intake and normalization

Accept exactly one V1 input in one of these shapes:

1. `https://arxiv.org/abs/<id>`
2. `https://arxiv.org/pdf/<id>.pdf` or `https://arxiv.org/pdf/<id>`
3. Bare arXiv ID such as `2603.18531`

Normalize all accepted forms to one canonical arXiv target before later phases begin. If the input is missing, ambiguous, or not an accepted V1 shape, fail closed.

### Phase 0.5: Bounded source ingestion

Run target access as an explicit bounded workflow before any genealogy work:

1. normalize the input into one canonical arXiv target record
2. choose an explicit runtime mode from `baseline` or `enriched` by following @references/runtime-modes.md
3. fetch the arXiv landing page for that target first
4. retry bounded retrieval attempts only as allowed by @references/ingestion-workflow.md
5. localize the PDF only when the landing page or target access requires it
6. fall back in bounded order across arXiv abs, localized PDF, and readable HTML or page-text paths where applicable
7. read only the text that is actually available to the runtime
8. quote only from sources whose text was actually read
9. record source-access state, runtime mode, capability use, retry count, and fallback path for every fetched item

Use the source-access states defined in @references/contract.md, the mode rules in @references/runtime-modes.md, and the detailed ingestion rules in @references/ingestion-workflow.md. Do not collapse retrieval, localization, reading, quoting, retries, or fallbacks into one implied step.

### Phase 1: Contract lock

Read the helper files above and lock these invariants before continuing:

- project-local placement under `.opencode/skills/math-genealogy-archaeologist/`
- arXiv-first invocation contract
- one canonical work node per resolved paper, even when multiple equivalent arXiv URLs are observed
- stable provenance fields: `canonical_work_id`, `observed_source_url`, `observed_version`, `alias_ids`, and `source_type`
- explicit reconciliation before treating an arXiv observation and a published version as the same observed version
- claim-ledger fields and enums from `@references/claim-ledger-schema.md`
- adjudication guardrails from `@references/evidence-adjudication.md`
- fixed report section order and fail-closed report variants from `@references/fixed-report-template.md` and `@references/fail-closed-output.md`
- fixed output artifact names
- fixed report-then-monologue ordering
- explicit runtime modes: `baseline` and `enriched`, with identical output schemas in both modes
- explicit source-access states: `discovered`, `localized`, `read`, `quoted`, `unverified`
- bounded retries and visible fallback ordering among arXiv abs, localized PDF, and readable HTML or page-text paths
- fail-closed behavior when required evidence is unavailable

Do not improvise new output files, alternate invocation shapes, or optional dependency requirements.

### Phase 2: Evidence collection plan

Plan the run as a multi-phase workflow rather than a one-shot answer:

1. complete bounded ingestion and source-access recording for the target source
2. gather bounded backward-genealogy evidence using the rules in @references/genealogy-selection.md
3. freeze adjudicated claims into named artifacts using the ledger schema and adjudication rules
4. render the fixed report
5. render the monologue as a second pass over the frozen ledger and completed report only

If any upstream phase cannot satisfy the contract, including broken URLs, unreadable targets, abstract-only access where full-paper reading was required, exhausted bounded retries, or an exhausted fallback path, stop and emit the fail-closed artifact set instead of guessing.

### Phase 3: Fixed artifact production

Produce the artifacts named in @references/report-schema.md. The report is always rendered before the monologue. Artifact filenames are part of the contract and must stay stable.

Render `report.md` and `report.json` by following the stable section order in @references/fixed-report-template.md and the fail-closed variants in @references/fail-closed-output.md. The fixed report must be a rendering from adjudicated ledger entries only. Do not let it collapse into a backward summary of the target paper or a prose recap of unread evidence.

Render `monologue.md` only after the report is complete, by following @references/monologue-policy.md and @references/grounded-monologue-template.md. The monologue is a second-pass renderer over the frozen ledger and completed report, not a parallel output path, and it must keep a mathematically informed notebook voice rather than publicity prose.

### Phase 4: Final policy check

Before finishing, verify that:

- the report precedes the monologue
- no artifact claims unsupported input normalization, localization, reading, or quoting
- every rendered claim comes from adjudicated ledger entries rather than fresh narration
- unsupported or downgraded claims never silently reappear as report or monologue facts
- no monologue content introduces facts outside the frozen evidence base
- any speculative sentence is explicitly marked as plausible reconstruction rather than private-author factual history
- the monologue includes the required disclaimer that it is not a factual claim about the authors' private thoughts
- the result remains usable in baseline mode without optional research MCPs

If any check fails, return the fail-closed result described in @references/contract.md.
