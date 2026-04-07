# Ingestion and localization workflow

## Purpose

This helper defines the bounded V1 path for obtaining target-paper text without pretending that every remote locator is directly readable.

The workflow must run in one explicit execution mode: `baseline` or `enriched`. The mode changes which optional capabilities may be used, but it does not change the output schema, artifact names, or fail-closed behavior.

## Required step separation

Treat these as separate workflow stages:

1. input normalization
2. mode selection
3. retrieval
4. localization
5. reading
6. quoting

The runtime must record source-access status after each meaningful transition. Do not merge these stages into one vague "looked at the paper" step.

## Mode-sensitive capability rules

1. In `baseline` mode, assume only URL fetch plus local read and search once text is locally readable.
2. In `enriched` mode, optional runtime-exposed web, citation, or search tools may be used when available.
3. Enriched mode is optional rather than required for supported arXiv-first inputs.
4. The runtime must record which capabilities were actually used so the trace shows whether the run stayed baseline-only or used enriched helpers.

## V1 target forms

- arXiv abs URL: `https://arxiv.org/abs/<id>`
- arXiv PDF URL: `https://arxiv.org/pdf/<id>` or `https://arxiv.org/pdf/<id>.pdf`
- bare arXiv ID: `<id>`

All three forms normalize to one canonical arXiv target record.

## Normalization rules

1. Bare arXiv IDs normalize to `https://arxiv.org/abs/<id>` as the canonical target.
2. arXiv PDF URLs normalize to the same canonical arXiv abs target while preserving the observed input form in provenance.
3. The run must remember equivalent locators in `alias_ids`, not treat them as separate papers.

## Retrieval rules

1. Fetch the arXiv landing page first, even when the observed input was a PDF URL or bare identifier.
2. Record the landing page and any discovered PDF locator as `discovered` once retrieved or identified.
3. Use bounded retries for retrieval attempts only. The retry ceiling must be explicit in the run trace.
4. If the landing page fetch fails or the URL is broken, record that retrieval failure in the trace and keep the affected source `unverified`.

## Fallback ordering

When the runtime still needs readable target text, it must follow a visible bounded fallback order rather than guessing:

1. arXiv abs or landing-page text first
2. localized arXiv PDF text second
3. readable HTML or page-text path third, where applicable

If a step fails, record the attempted path, the bounded retry count for that path, and the next fallback transition in `trace.json`.

## Localization rules

1. A remote PDF is not assumed readable just because its URL resolved.
2. Localize the PDF only when the workflow still needs paper-body text that is not already available from readable page content.
3. After successful localization, mark that source `localized`.
4. Use bounded retries for localization attempts only. Do not retry indefinitely.
5. If localization fails or yields an unreadable target, record the failure and leave the source `unverified`.

## Reading rules

1. Mark a source `read` only after the runtime successfully reads target text from that source.
2. Metadata-only access does not qualify as `read`.
3. Abstract-only access does not qualify as full-paper reading.
4. If the runtime can read only the abstract or other partial text, record that limitation explicitly and do not imply the full paper body was read.
5. If a readable HTML or page-text representation is used as a fallback, record that specific fallback path instead of implying direct PDF reading.

## Quoting rules

1. Mark a source `quoted` only when the runtime emits a quotation grounded in text it actually read.
2. Do not quote from `discovered`, `localized`, or `unverified` sources.
3. If a quotation cannot be traced back to readable target text, keep the source `unverified` for quoting purposes and fail closed where necessary.
4. If a claim is intended for downstream monologue quoting, the factual stage must record both the quote support and whether the quoted source was directly read.

## Source-access states

- `discovered`
- `localized`
- `read`
- `quoted`
- `unverified`

## Failure cases that must stay explicit

- broken URL or retrieval failure
- localization failure
- unreadable target after localization
- abstract-only access
- metadata-only access

These cases must surface in the trace and any fail-closed output. They must not be rewritten as successful reading.

## Baseline mode viability

V1 must remain usable with `WebFetch` plus local read and search assumptions once text has been localized or otherwise made locally readable. Optional research MCPs may improve coverage later, but baseline mode cannot depend on them.

Bounded retries and readable-text fallbacks must stay visible in the trace in both `baseline` and `enriched` modes.
