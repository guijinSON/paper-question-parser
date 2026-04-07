# Canonical paper identity policy

## Core distinction

The skill models one resolved scholarly work and one or more observed source artifacts.

- The resolved work is the canonical paper node.
- An observed source artifact is the concrete URL or identifier inspected during the run.
- Multiple observed URLs may collapse to the same canonical paper node.
- Multiple observed versions may still exist for that one canonical paper node.

V1 must keep canonical identity separate from observed provenance. Never treat these fields as interchangeable.

## Required fields

- `canonical_work_id`: stable identifier for the resolved work node used across the run.
- `observed_source_url`: exact URL or normalized locator actually inspected.
- `observed_version`: concrete version string or label attached to the observed source when known.
- `alias_ids`: alternate equivalent IDs or locators that resolve to the same canonical work.
- `source_type`: source family for the observation, such as `arxiv-abs`, `arxiv-pdf`, or `published`.

## V1 canonicalization policy

Use arXiv as the primary identity authority in V1.

1. Normalize a bare arXiv ID to the matching arXiv target.
2. Treat `https://arxiv.org/abs/<id>` and `https://arxiv.org/pdf/<id>` or `https://arxiv.org/pdf/<id>.pdf` as equivalent locators for the same canonical work.
3. Collapse those equivalent arXiv locators into one canonical paper node.
4. Preserve the observed input form in `observed_source_url` and `source_type`.
5. Record the equivalent locators and IDs in `alias_ids`.

This means duplicate arXiv abs and PDF inputs may refer to one canonical work while still remaining distinct observed-source records.

## Published-version policy

A linked journal or proceedings version may describe the same underlying work, but V1 does not automatically treat it as the same observed version as the arXiv source.

- A published locator may be attached to the same `canonical_work_id` only when the runtime explicitly reconciles it.
- The published locator keeps its own `observed_source_url`, `observed_version`, and `source_type`.
- If reconciliation has not happened yet, the runtime must keep the published artifact as a related observation, not as a silent replacement.

## Conflict handling

Surface version conflicts explicitly.

- If two observed sources collapse to the same canonical work but disagree on version metadata, report a version-conflict state.
- If arXiv metadata and a published version disagree materially, require explicit reconciliation before claiming they are the same observed version.
- Fail closed rather than silently preferring the published source over arXiv or vice versa.

## Minimum validation expectations

- Duplicate arXiv abs and arXiv PDF URLs for the same identifier collapse to one canonical paper node.
- The collapsed node retains both the canonical identifier and the observed-source provenance.
- Version disagreement is surfaced as an explicit conflict, not normalized away.
