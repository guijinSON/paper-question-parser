# Graph render guardrails

## Frozen-evidence guardrails

- Render from adjudicated bundle content only.
- Treat `claim-ledger.json` as the primary graphable evidence source.
- Do not upgrade excluded, downgraded, unresolved, unread, or non-renderable claims into visible graph facts.
- Do not treat `report.md` prose as a license to invent nodes or edges that are not already supported by the ledger.

## Downstream-only guardrails

- Accept only one factual bundle directory.
- Reject raw arXiv URLs, raw PDF URLs, bare IDs, or mixed inputs.
- Do not perform retrieval, source access, normalization, genealogy selection, or evidence adjudication.
- Do not modify `trace.json`, `claim-ledger.json`, `report.md`, or `report.json`.

## SVG-only guardrails

- Write exactly one derived artifact: `genealogy.svg`.
- Keep the output in the same bundle directory as the upstream artifacts.
- Do not emit HTML, PNG, PDF, JSON sidecars, screenshots, animation payloads, or interactive controls.
- Do not depend on browser execution to make the graph complete or valid.

## Determinism guardrails

- Use stable node ordering and stable edge ordering.
- Use stable element IDs that repeat across identical renders.
- Escape text and attributes so the result is valid XML.
- Keep one consistent top-level SVG structure for all successful renders.

## Fail-closed guardrails

- If required upstream files are missing, stop.
- If the factual bundle reports upstream failure, stop.
- If adjudicated evidence does not support a renderable genealogy graph, stop.
- If valid deterministic SVG cannot be emitted from the frozen bundle, stop.

Fail closed instead of inventing content, softening blockers, or writing a best-effort placeholder graph.
