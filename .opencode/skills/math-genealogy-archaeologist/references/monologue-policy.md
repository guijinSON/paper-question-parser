# Monologue policy

## Output ordering

- The report comes first.
- The monologue comes second.
- The monologue is rendered only after the ledger is frozen and the report is complete.
- The monologue is a second-pass renderer over the frozen ledger and completed report, not a parallel output path.

## Evidence boundary

- The monologue is rendered from frozen evidence artifacts, not from fresh speculation.
- It must not introduce new factual claims beyond the adjudicated evidence base.
- It must not introduce new factual content beyond adjudicated ledger claims.
- It must not upgrade `supported synthesis` to `fact` or `speculative interpretation` to settled conclusion.
- If the report fails closed, the monologue must also fail closed or be omitted according to the future renderer contract.

## Speculation rule

- Speculation is allowed only when explicitly marked as plausible reconstruction.
- The monologue must include the sentence `This is a plausible reconstruction, not a factual claim about the authors' private thoughts.` whenever a speculative reconstruction appears.
- Speculation must not sound like factual history about the authors' private thoughts, intentions, feelings, or unpublished reasoning.

## Voice boundary

- Write in a mathematically informed notebook voice.
- Keep the monologue in first person singular.
- Do not turn it into publicity prose, a motivation essay, or a polished backward summary of the target.

## Current scope

This scaffold now locks the no-new-facts boundary, report-before-monologue ordering, the notebook-like voice boundary, and the explicit plausible-reconstruction disclaimer.
