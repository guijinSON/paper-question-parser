# Trajectory pseudo-tag grammar

## Purpose

The trajectory must expose explicit research moves with literal pseudo-tool tags. The syntax is mandatory, not aspirational.

## Tag line grammar

Use this exact wrapper shape on its own line:

`<TOOL>TAG_NAME | FIELD: value | FIELD: value </TOOL>`

Rules:

- Start with literal `<TOOL>` and end with literal `</TOOL>`.
- `TAG_NAME` must be one of the allowed tags below.
- Fields must be uppercase snake case labels.
- Separate fields with ` | `.
- The prose that follows should show what changed because of that step.

## Minimum required tags

- `<TOOL>READ_PAPER | SOURCE_ID: ... | GOAL: ... </TOOL>`
- `<TOOL>HYPOTHESIS | CLAIM: ... </TOOL>`
- `<TOOL>TEST_HYPOTHESIS | CHECK: ... | EXPECTED: ... </TOOL>`
- `<TOOL>INTERNET_SEARCH | QUERY: ... | MOTIVE: ... </TOOL>`
- `<TOOL>FOLLOW_CITATION | FROM: ... | TO: ... </TOOL>`
- `<TOOL>REVISE_QUESTION | FROM: ... | TO: ... </TOOL>`
- `<TOOL>ABANDON_ROUTE | ROUTE: ... | REASON: ... </TOOL>`
- `<TOOL>SYNTHESIZE_DIRECTION | METHOD: ... | PRESSURE: ... </TOOL>`

## Usage rules

- Use literal pseudo-tags exactly as written; do not replace them with bullets or inline prose.
- `INTERNET_SEARCH` may describe only pseudo-search moves bounded by upstream-known papers, names, quotations, or topics already present in the factual bundle.
- `FOLLOW_CITATION` may only traverse source relationships already preserved in the frozen bundle.
- Tag lines must punctuate real route changes, not decorative flavor text.
- A compliant trajectory should use enough tag lines to make failed routes, revisions, and synthesis legible.
