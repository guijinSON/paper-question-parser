# Monologue guardrails and fail behavior

## Downstream-only rule

The monologue is a second-pass renderer over the frozen ledger and completed report. It is not another analyzer.

- Do not perform retrieval, adjudication, or genealogy selection.
- Do not add new papers, new topics, or new factual bridges not present in the factual bundle.
- Do not let pseudo-search steps smuggle in unseen literature.

## Quote bounds

- All quoted passages must come from claims with `monologue_quote_eligible = true`.
- Those quoted passages must come only from directly read sources.
- If the bundle lacks enough quote-eligible support, fail with the named blocker `insufficient_quote_coverage`.
- Do not quote unread sources, abstract-only sources, or indirectly quoted material.

## Factual bounds

- All factual claims must come from the factual bundle.
- The monologue may rearrange sequence and emphasis, but not evidence.
- A `supported synthesis` stays a synthesis; it does not become a `fact` through narrative confidence.
- A `speculative interpretation` stays visibly speculative.
- The monologue may derive the target paper's research topic from ancestor tensions, but only as a bounded reconstruction from bundle-backed claims.

## Pseudo-search bounds

- Pseudo-search steps may mention only upstream-known papers, names, quotations, or topics already present in `trace.json`, `claim-ledger.json`, `report.md`, or `report.json`.
- Queries may be dramatized, but they cannot introduce genuinely new literature or facts.

## Fail behavior

- If the factual bundle is fail-closed upstream, do not write `monologue.md` as if the run succeeded.
- If `monologue_readiness.status = insufficient_quote_coverage`, do not write a best-effort monologue without actual quoted passages.
- If required upstream artifacts are missing, fail closed.
- If the draft is still materially below the full-length target or still lacks the required route-development beats, continue expanding in the same run instead of stopping for human feedback.

## Speculation marker

- Include one fixed opening-note disclaimer that the transcript is a plausible reconstruction rather than a factual claim about the authors' private thoughts.
- Do not repeat the disclaimer sentence throughout the monologue body.
- Do not replace repeated disclaimers with body-level self-policing lines such as checking yourself against the bundle or explaining the contract from inside the transcript.

## Fixtures

The fixtures directory documents both accepted and rejected outputs for this contract.
