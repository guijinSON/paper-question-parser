# Trajectory fail-closed rules

## Purpose

Fail-closed trajectory output must stay visibly distinct from a successful full trajectory.

- A fail-closed run is not a complete success case.
- It must name the blocking mode explicitly.
- It must not imitate the tone or completeness of a successful ideation transcript.

## Named blockers

The renderer must support at least these named blockers:

1. `missing_required_bundle_artifact`
2. `blocked_by_upstream_failure`
3. `insufficient_target_access`
4. `insufficient_grounded_ideation_evidence`

These names are part of the contract and must stay stable.

## Blocker requirements

### `missing_required_bundle_artifact`

Use this when the supplied directory does not contain one or more required upstream artifacts.

- Do not write `trajectory.md`.
- Do not write `trajectory.manifest.json`.

### `blocked_by_upstream_failure`

Use this when `trace.json` or `report.json` reports an upstream fail-closed state that prevents downstream ideation output.

- Do not write `trajectory.md`.
- Do not write `trajectory.manifest.json`.

### `insufficient_target_access`

Use this when the factual bundle never reached enough readable target-paper support to ground the opening paper-reading and route-development beats.

- Do not write a best-effort transcript from metadata alone.
- Do not write `trajectory.manifest.json` for this blocker.
- Summary-only target support is still insufficient for this contract; downstream ideation requires at least one directly read, renderable, quote-bearing target claim.

### `insufficient_grounded_ideation_evidence`

Use this when the bundle exists and target access is acceptable, but the adjudicated evidence floor is too thin to support multiple grounded routes, revisions, and synthesis.

- Do not pad the transcript with generic mathematical brainstorming.
- Fail closed rather than faking rich search movement from sparse evidence.

## Rendering rules

- If more than one blocker applies, choose the earliest workflow blocker.
- A downstream-ready run must not silently downgrade into a short partial transcript.
- Fail-closed runs in this contract emit no downstream trajectory artifacts.
- If `trace.json` or `report.json` already carries one of the named blockers above, the runner may propagate that blocker directly instead of collapsing it to `blocked_by_upstream_failure`.
- If both upstream files carry named blockers and they disagree, prefer the earlier trace-level blocker for fail-closed propagation.
- If an upstream blocker name is unknown to this contract, collapse it to `blocked_by_upstream_failure`.
