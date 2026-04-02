# Claim ledger schema

## Purpose

`claim-ledger.json` is the audited evidence ledger for the run. Later renderers may only render from adjudicated ledger claims rather than inventing facts, filling gaps from memory, or upgrading downgraded evidence.

## Top-level structure

At minimum, `claim-ledger.json` must contain:

- `target_paper`: canonical target-paper identity and observed provenance fields already locked by the contract
- `claims`: ordered array of claim records
- `adjudication_summary`: machine-readable summary of downgrades, exclusions, and unresolved conflicts
- `monologue_readiness`: machine-readable downstream-readiness summary

## Claim record

Each claim record must store all of the following fields:

- `claim_id`: stable identifier for the claim record
- `paper_node`: the paper or source node the claim is about
- `claim_text`: exact claim text or faithful paraphrase carried forward for rendering
- `claim_type`: one of `fact`, `supported synthesis`, or `speculative interpretation`
- `source_access_level`: explicit access status for the evidence supporting this claim
- `source_tier`: one of `primary`, `secondary`, or `tertiary`
- `quotation_or_excerpt`: direct quotation or bounded excerpt when available, otherwise the exact excerpted support text the runtime actually read
- `quote_kind`: one of `verbatim_quote`, `bounded_excerpt`, `summary_only`, or `none`
- `directly_read`: boolean stating whether the quoted support came from a source whose target text was actually read in this run
- `monologue_quote_eligible`: boolean stating whether the claim may supply actual quoted passages to the downstream monologue
- `confidence`: explicit confidence value for the claim after adjudication

The ledger may store additional implementation fields such as `source_ids`, `adjudication_status`, `conflict_group`, `notes`, `renderable`, or `monologue_quote_readiness_reason`, but the fields above are mandatory and stable.

## Field rules

### `paper_node`

Store the referenced paper node explicitly so each claim stays attached to a concrete node rather than a floating sentence.

### `claim_text`

The record may preserve verbatim wording or a faithful paraphrase, but it must remain close enough to the source evidence that a later renderer can repeat it without inventing new content.

### `claim_type`

- `fact`: directly supported statement that the runtime read from admissible evidence and can stand on its own.
- `supported synthesis`: a bounded synthesis assembled from multiple admissible pieces of evidence, where the synthesis step is explicit and support remains traceable.
- `speculative interpretation`: interpretive or inferential statement that may be useful context but cannot be rendered as settled fact.

The distinction is mandatory. A `supported synthesis` is not a `fact`, and a `speculative interpretation` must never be rendered as if it were settled.

### `source_access_level`

`source_access_level` records what the runtime actually accessed for the supporting source material. Keep this separate from source tier and align it with the run's evidence states such as `discovered`, `localized`, `read`, `quoted`, `unverified`, or a more specific bounded-access label like `abstract-only` when relevant.

### `source_tier`

- `primary`: the claim is supported by source text from the paper or artifact being described.
- `secondary`: the claim is supported by a later source describing another work.
- `tertiary`: the claim is supported only by higher-level summaries, catalogs, encyclopedias, or similar overview material.

Source tier captures evidentiary distance, not access quality. A readable tertiary summary is still tertiary, and an unread primary paper is still primary but unread.

### `quotation_or_excerpt`

Store the exact quotation when text was quoted, or a bounded excerpt from text actually read when the claim is paraphrased. If no readable text was available, do not fabricate an excerpt.

### `quote_kind`

- `verbatim_quote`: the record preserves a direct quotation suitable for downstream reuse.
- `bounded_excerpt`: the record preserves a tight source excerpt actually read in the run, but not a finalized downstream-ready quotation.
- `summary_only`: the claim is supported, but only by summarized or paraphrased support and therefore is not quote-ready.
- `none`: no quote-bearing support is available.

Do not infer `quote_kind` from a non-empty text field alone. It must be set explicitly.

### `directly_read`

Set `directly_read = true` only when the supporting quoted text came from a source whose target text was actually read in this run. A quotation relayed through another paper, abstract-only source, review, or catalog remains `directly_read = false`.

### `monologue_quote_eligible`

Set `monologue_quote_eligible = true` only when all of the following hold:

1. the claim survived adjudication as renderable
2. `quote_kind` is `verbatim_quote` or `bounded_excerpt`
3. `directly_read = true`
4. the claim is not blocked by conflict, unread-source dependence, or indirect-quotation limits

If any condition fails, set `monologue_quote_eligible = false` and keep the limiting reason explicit.

### `confidence`

Store explicit post-adjudication confidence. Confidence is an outcome of adjudication and must not overwrite `claim_type`, `source_access_level`, `source_tier`, `quote_kind`, or quote-eligibility fields.

## Monologue-readiness summary

`monologue_readiness` must expose the downstream decision in machine-auditable form.

At minimum include:

- `status`: one of `ready`, `insufficient_quote_coverage`, `blocked_by_upstream_failure`
- `eligible_quote_claim_ids`: ordered list of claims with `monologue_quote_eligible = true`
- `directly_read_source_ids`: source IDs that can support downstream actual quoted passages
- `notes`: explicit explanation of the readiness decision

## Rendering constraint

Only adjudicated ledger claims may be rendered into later outputs. Claims excluded, downgraded, unresolved, abstract-only, indirectly quoted, unread, or notation-unsafe in the ledger cannot silently become later report or monologue facts.
