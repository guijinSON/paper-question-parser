# Trajectory guardrails and fail behavior

## Downstream-only rule

The trajectory is a second-pass renderer over the frozen ledger and completed report. It is not another analyzer.

- Do not perform retrieval, adjudication, genealogy selection, or descendant comparison.
- Do not add new papers, new topics, or new factual bridges not present in the factual bundle.
- Do not let pseudo-search steps smuggle in unseen literature.

## Factual bounds

- All factual claims must come from the factual bundle.
- The trajectory may rearrange sequence and emphasis, but not evidence.
- A `supported synthesis` stays a synthesis; it does not become a `fact` through narrative confidence.
- A `speculative interpretation` stays visibly speculative.
- The trajectory may explore future-facing directions, but only as bounded hypothetical extensions from bundle-backed pressures.

## Descendant leakage rule

- Later descendants are evaluator-only inputs and must remain unavailable during generation.
- Do not mention later papers, later method names, hidden targets, overlap scores, or phrases that imply foreknowledge of historically realized descendants unless that exact information is already in the frozen bundle.
- Do not let the trajectory read like a disguised answer key.

## Wording-level guardrails

- Do not attribute intentions, goals, motives, strategy, or deliberation to the target paper or its authors unless that language is explicitly supported by the factual bundle.
- Avoid causal or teleological claims such as `therefore this inevitably leads to`, `the real point is`, `this is exactly the later method`, or `everything converges here` unless the relation is explicitly frozen in the evidence.
- Do not merge several bundle-backed observations into a new declarative historical fact. If the bridge is interpretive rather than explicit, mark it as plausible reconstruction or tentative route.
- Do not add unstated actors, scope, significance, or inevitability during connective paraphrase.

## Pseudo-search bounds

- Pseudo-search steps may mention only upstream-known papers, names, quotations, or topics already present in `trace.json`, `claim-ledger.json`, `report.md`, or `report.json`.
- Queries may be dramatized, but they cannot introduce genuinely new literature or facts.

## Speculation marker

- Include one fixed opening-note disclaimer that the transcript is a plausible reconstruction rather than a factual claim about private author thoughts.
- Do not repeat the disclaimer sentence throughout the body.
- When a sentence goes beyond direct rendering or neutral connective paraphrase, mark the move with wording such as `Plausible reconstruction:` or `Tentative route:` instead of letting the sentence harden into settled fact.

## Manifest boundary

- `trajectory.manifest.json` may contain only validation-facing metadata, structural markers, evidence references, and blocker fields.
- The manifest must not duplicate the full prose body.
- The manifest must not contain evaluator outputs or descendant-overlap scores.

## Fail behavior

- If the factual bundle is fail-closed upstream, do not write `trajectory.md` or `trajectory.manifest.json` as if the run succeeded.
- If required upstream artifacts are missing, fail closed.
- If the bundle lacks enough grounded pressure points, readable target support, or renderable ideation material to support a bounded transcript, fail with a named trajectory blocker rather than inventing content.
- If the draft is still materially below the route-development target or still lacks the required grammar markers, continue expanding in the same run instead of stopping for human feedback.
