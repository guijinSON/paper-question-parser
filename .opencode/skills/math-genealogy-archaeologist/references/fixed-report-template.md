# Fixed report template

## Renderer boundary

The fixed report is a rendering from adjudicated ledger entries only.

- Every rendered statement in `report.md` and `report.json` must trace to one or more adjudicated entries in `claim-ledger.json`.
- The renderer must not introduce fresh narration, backfill gaps from memory, or infer unlogged claims from the target paper's abstract, introduction, or bibliography.
- The renderer must not collapse into a backward summary of the target paper. The report's job is to state what the adjudicated evidence says about the paper's backward mathematical genealogy, not to retell the target paper itself.
- If a required section has no adjudicated support, the renderer must say so explicitly or switch to a fail-closed variant from `fail-closed-output.md`.

## Stable public section order

The public section order is fixed and must stay stable across runs:

1. `## Source ledger`
2. `## Seed ranking`
3. `## Pressure points`
4. `## Missing-cell analysis`
5. `## Transfer-vs-novelty boundary`
6. `## Blind reconstruction`
7. `## Comparison with target`
8. `## Reconstructed question`
9. `## Confidence and uncertainty`

Do not reorder, rename, merge, or drop these section headers in a normal full report.

## Section contract

### `## Source ledger`

Render a compact ledger-facing summary of what target and genealogy sources were discovered, localized, read, quoted, or left unverified. This section should expose source-access boundaries, not hide them.

### `## Seed ranking`

Render the ranked immediate and supporting seeds that survived genealogy selection. Each ranked seed must trace to adjudicated inclusion claims and explicit source support.

### `## Pressure points`

Render the decisive tensions, bottlenecks, or open technical constraints that the ledger indicates were inherited from the genealogy. This is not a generic importance summary.

### `## Missing-cell analysis`

Render the specific missing links, absent evidence cells, or unresolved support gaps that limited reconstruction confidence.

### `## Transfer-vs-novelty boundary`

Render what appears transferred from earlier work versus what appears novel in the target, but only at the level supported by adjudicated ledger claims. Do not promote a synthesis beyond its adjudicated confidence.

### `## Blind reconstruction`

Render the best evidence-backed reconstruction of the likely motivating path without using the target's own retrospective framing as an unearned authority.

### `## Comparison with target`

Render where the blind reconstruction agrees with, undershoots, or conflicts with the target's accessible framing. Keep all differences tied to adjudicated evidence and source-access limits.

### `## Reconstructed question`

Render the reconstructed underlying question or problem pressure that best fits the adjudicated evidence base. If the evidence is too thin, switch to a fail-closed mode instead of improvising.

### `## Confidence and uncertainty`

Render confidence, uncertainty, and any unresolved conflicts in a visibly bounded way. This section must make failure boundaries obvious when the evidence is thin or conflicted.

## Rendering rules

- Section content may summarize or synthesize adjudicated claims, but the summary itself must be fully supported by those ledger entries.
- Excluded, blocked, downgraded, unread, abstract-only, or conflict-marked claims must not re-enter as normal prose.
- Each section should remain evidence-first, with uncertainty stated where support is partial.
- The template defines report shape only. It does not authorize any monologue rendering.
