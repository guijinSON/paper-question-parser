# Deterministic SVG rules

## Purpose

`genealogy.svg` must be stable enough for fixture validation, XML parsing, and repeatable regeneration from the same frozen factual bundle.

## Allowed output form

- Output exactly one SVG document in the bundle directory, named `genealogy.svg`.
- The root element must be `<svg>` in valid SVG XML.
- The document must remain static. No HTML wrappers, JavaScript, CSS animations, canvas fallbacks, embedded raster screenshots, or browser-only behavior.

## Graph source rule

- Use `claim-ledger.json` as the primary graphable input because it is the frozen adjudicated evidence ledger.
- Read `report.md` and `report.json` only for compatible bundle context that does not override adjudicated ledger facts.
- Never create a node or edge from memory, guesswork, or fresh retrieval.

## Deterministic node ordering

- Derive the node set from adjudicated, renderable genealogy evidence only.
- Order nodes by stable bundle-backed identifiers when available.
- If multiple candidate fields exist, use one documented precedence order and apply it consistently for every render.
- When ties remain after identifier ordering, break ties lexicographically on escaped label text.
- Preserve the resulting node order in the emitted SVG structure.

## Deterministic edge ordering

- Emit only edges supported by frozen bundle relations.
- Sort edges by stable source-node identifier, then stable target-node identifier, then a stable edge-role or relation field when present.
- If ties remain, apply one consistent lexicographic fallback over the serialized edge key.
- Preserve the resulting edge order in the emitted SVG structure.

## Stable element IDs

- Every graph node element must expose a stable SVG element ID derived from the same stable node key used for ordering.
- Every graph edge element must expose a stable SVG element ID derived from the ordered source key, ordered target key, and stable relation discriminator when present.
- ID generation must be deterministic for repeated renders from the same bundle.
- Do not use random suffixes, timestamps, hash seeds that vary by process, or renderer-instance counters.

## Text and attribute escaping

- Escape all labels, titles, and text content for XML validity.
- Escape attribute values as needed for valid SVG XML.
- Preserve factual text content faithfully after escaping. Do not silently rewrite names or titles beyond XML-safe escaping and minimal deterministic whitespace normalization.

## Structural expectations

- The output should group graph content in a predictable structure such as graph-wide containers, then ordered edge elements, then ordered node elements, or another single documented structure used consistently.
- The structure must remain machine-parseable and stable across repeated renders from identical input.
- Use SVG elements only. Avoid foreign namespaces unless the contract is later expanded to require them.

## Fail-closed cases

- Missing required upstream artifacts
- Upstream-failed bundle state
- No adjudicated renderable genealogy nodes
- No adjudicated renderable genealogy relations
- Invalid or unescaped text that would make the SVG malformed

In those cases, fail closed instead of writing a placeholder, partial, or speculative SVG.
