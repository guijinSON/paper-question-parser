# Evidence adjudication rules

## Purpose

Adjudication decides what a collected claim is allowed to become in the frozen ledger. The runtime must not resolve difficult cases with vague judgment alone. Each rule below states whether a claim remains renderable, must be downgraded, or must be blocked.

## Core rule

Claims may be rendered later only if they survive adjudication as ledger claims with explicit support. Unsupported or downgraded claims cannot silently become report facts or downstream monologue facts later.

## Adjudication rules

### Abstract-only evidence

- If the runtime only accessed an abstract, metadata page, review snippet, or other partial surface, record the claim with `source_access_level` showing the limitation such as `abstract-only` or `unverified`.
- Abstract-only evidence cannot support paper-body `fact` claims about proofs, constructions, or detailed genealogy roles unless the abstract itself explicitly states that exact point.
- Abstract-only support may at most back a narrowly scoped `supported synthesis` or `speculative interpretation`, and the ledger must keep the downgrade explicit.

### Indirect quotations through another paper

- A quotation repeated by a secondary or tertiary source is an indirect quotation unless the runtime also read the original source text.
- Indirect quotations must not be stored as direct primary quotations in `quotation_or_excerpt`.
- If the original source was unread, the claim must retain the indirect nature in adjudication, use the actual secondary or tertiary source tier, and cannot be promoted to a primary-source `fact`.
- Indirect quotations force `directly_read = false` and `monologue_quote_eligible = false`.

### Conflicting evidence

- When admissible sources disagree, keep the conflicting claim records separate and connect them with an explicit conflict marker such as `conflict_group` or equivalent adjudication metadata.
- Do not average conflicting claims into one synthetic sentence.
- If one source is stronger because it is primary, directly read, and textually specific, the weaker claim may be downgraded, but the conflict must remain explicit in the ledger.
- Unresolved conflicts are not renderable as settled facts. Later outputs may only describe them as conflicts if the ledger says they are unresolved.

### Unread sources

- A source that was discovered or localized but not actually read cannot support a renderable quotation.
- Unread sources cannot support `fact` claims about paper content.
- If an unread source is mentioned by another source, the resulting claim remains secondary or tertiary and must stay marked as unread at the underlying-source level.
- Unread-source dependence forces `monologue_quote_eligible = false`.

### Unsupported notation mapping

- Do not silently normalize notation between papers when the runtime lacks explicit correspondence text.
- If symbol mapping, terminology mapping, or theorem-name mapping is not directly supported by readable evidence, the claim must be blocked or downgraded to `speculative interpretation`.
- Unsupported notation mapping cannot be used to merge claims, infer ancestry, or manufacture apparent agreement between sources.

### Quote-readiness rules

- `quote_kind` must be assigned explicitly during adjudication.
- `monologue_quote_eligible = true` requires both a quote-bearing support field and `directly_read = true`.
- `summary_only` and `none` are never quote-eligible.
- A claim with otherwise valid factual support may remain renderable in the report while still being ineligible for downstream monologue quoting.
- When the bundle as a whole lacks enough quote-eligible claims, the factual stage must set `monologue_readiness.status = insufficient_quote_coverage`.

## Guardrail summary

- `fact` requires directly admissible support commensurate with the statement.
- `supported synthesis` requires traceable multi-source support and explicit synthesis rather than hidden inference.
- `speculative interpretation` remains explicitly interpretive and non-settled.
- Secondary or tertiary sources must never masquerade as primary paper-content evidence.
- A later renderer may only repeat the adjudicated status already frozen in the ledger.
- Downstream quote use depends on `quote_kind`, `directly_read`, and `monologue_quote_eligible`, not on guesswork.
