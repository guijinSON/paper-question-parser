# Pseudo-tag grammar

## Purpose

The monologue must expose explicit research moves with literal pseudo-tool tags. The syntax is mandatory, not aspirational.

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
- `<TOOL>INTERNET_SEARCH | QUERY: ... | MOTIVE: ... </TOOL>`
- `<TOOL>FOLLOW_CITATION | FROM: ... | TO: ... </TOOL>`
- `<TOOL>HYPOTHESIS | CLAIM: ... </TOOL>`
- `<TOOL>TEST_HYPOTHESIS | CHECK: ... | EXPECTED: ... </TOOL>`
- `<TOOL>REVISE_QUESTION | FROM: ... | TO: ... </TOOL>`

## Usage rules

- Use literal pseudo-tags exactly as written; do not replace them with bullets or inline prose.
- `INTERNET_SEARCH` may describe only pseudo-search moves bounded by upstream-known papers or topics. It must not introduce new literature beyond the factual bundle.
- Tag lines must punctuate real route changes, not decorative flavor text.
- A compliant monologue should use enough tag lines to make the search process legible.
