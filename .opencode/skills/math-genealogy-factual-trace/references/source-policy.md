# Source access policy

## Baseline mode assumptions

- V1 must work without optional research MCPs.
- arXiv is the primary source family.
- Baseline source acquisition may rely on `WebFetch` for remote pages plus local read and search operations once text is actually available inside the runtime.
- Remote PDF understanding cannot be assumed until the source has been localized into a readable form for the runtime.

## Source handling guardrails

- Treat input normalization, retrieval, reading, and quoting as separate steps.
- Treat localization as a separate step between retrieval and reading whenever the target source is not already readable text.
- Fetch the arXiv landing page first for arXiv abs URLs, arXiv PDF URLs, and bare arXiv IDs.
- Normalize bare arXiv IDs and arXiv PDF inputs back to the canonical arXiv abs target before deciding whether PDF localization is needed.
- Localize a remote PDF only when the landing page does not already provide the needed readable text and the bounded workflow still requires paper-body access.
- Do not claim full-paper access when only metadata or an abstract was inspected.
- Do not silently skip failed retrieval attempts.
- Do not continue past missing target access as though the paper was read.
- Do not promote a source beyond `discovered` or `localized` when readable target text was not actually obtained.
- Mark broken URLs, unreadable targets, and abstract-only targets `unverified` unless later steps genuinely produce readable target text.
- Treat source identity and observed version as separate provenance dimensions.
- Collapse equivalent arXiv abs and arXiv PDF locators to one canonical paper node in V1.
- Do not automatically treat a linked published page as the same observed version as the arXiv source.
- Surface explicit reconciliation work when arXiv and published evidence disagree on version, title, or bibliographic details.

## Minimum ingestion workflow

1. Normalize the input into one canonical arXiv target record.
2. Retrieve the arXiv landing page and record the target as `discovered`.
3. If target text is only available through a remote PDF, localize that PDF and record `localized`.
4. Read only text that is actually accessible to the runtime and record `read`.
5. Emit quotations only from text that reached `read`, then record `quoted`.
6. If any required target text remains inaccessible, keep the affected source `unverified` and fail closed where the contract requires full-paper access.

## Future expansion boundary

This scaffold does not yet define ancestor selection internals beyond the linked rules. It locks the identity and source-policy boundary that later tasks must respect.
