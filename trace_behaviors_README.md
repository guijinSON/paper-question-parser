# Reasoning Trace Behaviors

This document lists candidate in-trajectory behaviors for math/problem-solving traces. Each behavior is meant to be inserted as one natural reasoning segment, as if the model paused and revalidated its own trajectory.

## Natural Insertion Style

Goal: the inserted segment should feel like an in-trace reasoning move.

It should sound like the same model paused mid-solution, noticed a risk, and adjusted its reasoning. It should not sound like an external evaluator grading the trace.

Use a behavior insertion only when the trace naturally reaches a real decision point:

- A claim has just become stronger than the evidence supports.
- A theorem is invoked without its hypotheses being checked.
- A local calculation is about to be treated as a global theorem.
- A reduced/simplified object is being used as if it retained forgotten structure.
- The trace is about to continue from a premise that would make later reasoning unreliable.

Avoid insertions for harmless verbosity, missing polish, or a merely incomplete plan. The inserted segment should change the reasoning trajectory, not just comment on style.

Do not refer to the trace-generation machinery inside an inserted segment. Avoid phrases like "the continuation says", "the model wrote", "the previous generated segment", or "this output". The inserted segment should read as if it is part of the original reasoning process:

```text
Good: Wait, I should re-check this step: the theorem I want to use needs formal deformation data, not just the reduced special fiber.
Bad: Wait, I should re-check this step: the continuation reintroduced the same overclaim.
```

## Behavior Cooldown

In iterative continue-and-fix runs, avoid repeatedly inserting the same behavior.

Rule: after a behavior is inserted, that same behavior is on cooldown for the next two insertion rounds. During cooldown, choose the earliest valid trigger for a different behavior. If no different behavior is valid, continue generation without inserting, or use `dead_end_detection` / `answer_mode_switch` if the trace is repeatedly returning to the same failure mode.

Example:

```text
Round 1 insertion: correction
Round 2 allowed: counterexample_search, branch_split, answer_mode_switch, dead_end_detection, lemma_decomposition
Round 3 allowed: counterexample_search, branch_split, answer_mode_switch, dead_end_detection, lemma_decomposition
Round 4 correction becomes allowed again
```

This cooldown is meant to force variety in training signals and prevent a loop from repeatedly teaching only correction.

## Consolidated JSON Trace Format

For iterative runs, keep one JSON artifact rather than splitting each repaired trace and insertion into separate files.

The JSON should preserve the repaired reasoning as an interleaved sequence of original trace chunks, inserted behavior chunks, and continuation chunks:

```json
{
  "prompt": "...",
  "max_length": 32768,
  "continuation_max_tokens": 1024,
  "status": "running | solved | length_cut",
  "target_answer_shape": "",
  "avoid_claims": [],
  "fix_memory": [],
  "rounds": [
    {
      "round": 1,
      "behavior": "correction",
      "trigger_segment_index": 4,
      "trigger_summary": "...",
      "inserted_segment": "...",
      "not_do": "Do not repeat the canceled claim.",
      "fix_summary": "The claim was weakened to require formal/logarithmic data.",
      "token_count_after_insertion": 1402,
      "cooldown_after_round": {"correction": 2}
    }
  ],
  "interleaved_trace": [
    {
      "type": "original",
      "round": 0,
      "truncated": true,
      "text": "..."
    },
    {"type": "insertion", "round": 1, "behavior": "correction", "text": "..."},
    {"type": "continuation", "round": 1, "text": "..."}
  ],
  "final_solution": "",
  "termination_summary": null
}
```

The full repaired trace can be reconstructed by concatenating `interleaved_trace[*].text` in order.

Important: `interleaved_trace` should contain the retained truncated original trace, not the full source trace. Once the first behavior trigger is found, keep only the original text through and including that trigger segment, then append the insertion. Do not keep downstream original text that the insertion is meant to cancel or replace.

The same rule applies to continuations. A continuation is not stored as-is if it later needs an insertion. When a continuation repeats an error, enters a dead end, or needs a new behavior, truncate that continuation through and including the trigger segment, then append the insertion. Do not keep downstream continuation text that the insertion is meant to redirect.

Do not stop immediately after inserting a behavior merely because the insertion seems decisive. After every insertion, continue generation at least once unless the max-length threshold has already been reached. Mark a run solved only after a continuation reaches a final-answer-style segment or after Codex is explicitly invoked to write the final solution from a completed trajectory.

Continuation entries may record truncation metadata:

```json
{
  "type": "continuation",
  "round": 2,
  "truncated": true,
  "trigger_summary": "The continuation restated the canceled kernel theorem.",
  "original_char_count": 3297,
  "text": "..."
}
```

## Persistent Fix Memory

After a correction or dead-end insertion, preserve the lesson as loop memory:

- `avoid_claims`: claims or moves the continuation must not repeat.
- `fix_memory`: concise summaries of safe replacements or corrected directions.
- `target_answer_shape`: the desired answer mode once it becomes clear.

These fields should be injected into the next continuation as developer instructions. This is how the loop prevents the continuation model from reintroducing a canceled claim.

For correction insertions, always produce a specific not-do:

```json
{
  "behavior": "correction",
  "not_do": "Do not claim that Aut_k(X_k) alone determines the higher ramification filtration.",
  "fix_summary": "Use the caveat that formal/logarithmic stable-reduction data is required."
}
```

The inserted correction should also say the not-do naturally:

```text
Wait, I should re-check this step: I should not claim that Aut_k(X_k) alone determines the filtration. The safer statement is that the reduced action forgets valuation data, so any recovery statement needs formal or logarithmic stable-reduction data.
```

## Repeated Error Handling

If the same mistake recurs after it has already been canceled, do not automatically use another `correction`.

Use the behavior that best changes the path:

- `answer_mode_switch`: when the model keeps trying to prove a statement that should be caveated or rejected.
- `dead_end_detection`: when the strategy keeps returning to the same unprovable bridge claim.
- `lemma_decomposition`: when the recurring error comes from bundling several obligations into one broad theorem.
- `branch_split`: when the recurring error comes from treating reduced, formal, and logarithmic data as one interchangeable object.
- `counterexample_search`: when the recurring error is a universal recoverability claim that can be challenged by looking for two situations with the same reduced action but different formal/valuation data.

For repeated errors, slice the continuation before the repeated mistake propagates. The insertion should redirect the reasoning before the trace accumulates another long bad branch.

## Prefix Sets

Prefix sets are a labeling mechanism.

Rules:

1. Every inserted segment must start with one of the allowed prefixes for its behavior.
2. The prefix identifies the intended behavior class.
3. The rest of the segment must do the actual reasoning work.
4. Do not use a prefix as a decorative tag; it must flow naturally into the sentence.

Pattern:

```text
<behavior prefix> <behavior-specific reasoning content>
```

Examples:

```text
Wait, I should re-check this step: the reduction just used a stronger theorem than we have.
This should be broken into lemmas: first prove the local claim, then check whether it globalizes.
```

## Correction

Detect the first substantive error, truncate through that segment, and insert a self-correction that cancels the mistake.

Allowed prefixes:

- `Wait, I should re-check this step:`
- `Hold on, I may be assuming too much here:`
- `I need to verify this before continuing:`
- `This step needs a closer check:`
- `Let me pause and validate the last inference:`

Example:

> Wait, this step is too strong. The theorem does not imply recoverability from the reduced special fiber alone; it only applies after keeping additional formal or logarithmic data.

Natural trigger:

Use this when the current segment contains an actual false or unjustified step that would make the rest of the trace unreliable. The correction should be incurred at the first bad segment, not after several downstream consequences.

Slice cues:

- The trace asserts a theorem, equivalence, implication, or reduction that is false.
- A required hypothesis is missing and the step would fail without it.
- The trace treats a heuristic, analogy, or local calculation as a proved fact.
- The trace starts building later reasoning on an unsupported bridge claim.
- Continuing after this segment would mostly amplify the same mistake.

Do not use when:

- The segment is only vague but not yet wrong.
- The trace merely lacks polish or detail.
- A later segment makes the first clear mistake but this one is still defensible.

## Counterexample Search

Test small, boundary, or degenerate cases before committing to a universal claim.

Allowed prefixes:

- `Before proving this universally,`
- `I should test small cases first,`
- `A quick counterexample check is needed:`
- `Let me check boundary cases,`
- `This claim could fail in a small case,`

Example:

> Before trying to prove nonexistence, I should test small values and obvious degeneracies. A single exception would change the goal from proving none exist to classifying exceptions.

Natural trigger:

Use this when the trace is moving toward a universal claim and there is a cheap way to test small, boundary, or degenerate cases before committing to the proof direction.

Slice cues:

- The trace is about to prove a universal negative or universal classification.
- The problem has small parameters, boundary cases, equality cases, degenerate objects, or excluded-but-nearby trivial cases.
- A single counterexample would change the answer shape.
- The trace assumes the target statement is true before testing examples.
- The domain is discrete enough for quick sanity examples: integers, finite groups, small graphs, low dimensions, simple curves, endpoint exponents.

Do not use when:

- The problem is purely structural and examples would not test the claim.
- Small cases have already been checked.
- The trace already found a decisive proof obstruction or error.

## Branch Split

Recognize that the problem naturally splits into structurally different cases or proof branches and should not be treated as one uniform argument.

Allowed prefixes:

- `This needs to split into cases:`
- `I should branch the argument here:`
- `There are separate cases to handle:`
- `This is not one uniform situation:`
- `Let me separate the cases:`
- `The cases are not interchangeable:`

Example:

> The plus and minus cases behave differently, and the parity of the exponent matters. I should split these before invoking a primitive-divisor theorem.

Natural trigger:

Use this when the trace is about to apply one argument across situations that have materially different assumptions, tools, exceptional cases, or conclusions.

Slice cues:

- The next argument would treat non-equivalent cases uniformly.
- Different signs, parity, characteristic, dimension, smooth/singular cases, reducible/irreducible cases, or boundary regimes change the available tools.
- A theorem has different exceptional cases across branches.
- The trace uses language like "similarly" or "same argument" where symmetry is not obvious.
- The proof target naturally decomposes into separate implications or parameter ranges.

Do not use when:

- The cases are genuinely identical after a clear normalization.
- The split would be cosmetic and not change the reasoning.
- The trace first needs a direct verification of assumptions before deciding the correct branches.

## Answer Mode Switch

Reclassify the answer shape: proof, disproof, conditional answer, caveat, or non-recoverability statement.

Allowed prefixes:

- `The answer shape should change:`
- `This is not a straight yes:`
- `I should switch modes here:`
- `The right response is conditional:`
- `This calls for a caveat rather than a proof:`

Example:

> The right answer is not a clean yes. It is no from the reduced special fiber alone, and only a qualified yes after enriching the data with formal or logarithmic structure.

Natural trigger:

Use this when the trace has enough information to see that the requested answer type is wrong: the response should become conditional, negative, caveated, or reframed instead of continuing as a direct proof.

Slice cues:

- The prompt asks a yes/no question but the trace has discovered a conditional or qualified answer.
- The trace is trying to prove a statement that should instead be refuted, caveated, or reframed.
- The data available in the problem is insufficient for the requested conclusion.
- The correct response is "not from this information alone", "only under extra hypotheses", or "the premise is false".
- Continuing in proof mode would overclaim.

Do not use when:

- A direct proof or disproof is still viable.
- The trace only needs a local correction, not a different answer type.
- The answer shape is already explicit and appropriate.

## Dead-End Detection

Notice that the current proof path cannot deliver the intended conclusion, even if no single previous step is plainly false.

Allowed prefixes:

- `This path is a dead end because`
- `Continuing this route will not prove the claim:`
- `This approach cannot close the argument:`
- `I should abandon this route here:`
- `The strategy has stalled because`

Example:

> This path seems to be a dead end. Even if the local node calculations are correct, they only describe extra formal data of the stable model; they do not show that the reduced automorphism action determines the higher ramification filtration.

Natural trigger:

Use this when the current strategy cannot plausibly reach the intended conclusion, even though the previous segments may be individually defensible.

Slice cues:

- The current strategy can at best prove a weaker, different, or irrelevant claim.
- The trace keeps adding detail but not moving closer to the requested conclusion.
- The needed bridge would require information not available in the problem.
- The proof path depends on future facts that are unlikely or false.
- No single prior sentence is necessarily false, but the strategy cannot close.

Do not use when:

- There is a specific false step; use correction instead.
- The path is merely incomplete but has a plausible route to completion.
- The trace only needs decomposition into lemmas or cases.

## Lemma Decomposition

Break a large informal argument into explicit lemmas or subclaims that can be checked independently.

Allowed prefixes:

- `This should be broken into lemmas:`
- `Let me decompose the proof:`
- `The argument needs separate subclaims:`
- `I should isolate the lemmas:`
- `This is too compressed; split it into`

Example:

> This is getting too compressed. I should break the claim into lemmas: first, what the reduced stable fiber action sees; second, what formal/log data adds; third, whether either determines the classical ramification filtration.

Natural trigger:

Use this when the trace is about to compress several independent proof obligations into one broad claim, and the argument would become safer if those obligations were separated into checkable subclaims.

Slice cues:

- The trace is about to assert a large multi-part conclusion in one step.
- Several independent claims are being bundled together.
- A proof needs intermediate statements that can be verified separately.
- The model is juggling definitions, reductions, and conclusion at once.
- The argument would become clearer if each subclaim had a role: reduction, local claim, global claim, obstruction, conclusion.

Do not use when:

- The trace has already made a concrete mistake; use correction.
- The problem naturally splits by cases rather than lemmas; use branch split.
- The argument is short enough that decomposition would be artificial.

## Suggested Starting Set

For the current failure mode, the most useful initial behavior labels are:

1. `correction`
2. `dead_end_detection`
3. `lemma_decomposition`
