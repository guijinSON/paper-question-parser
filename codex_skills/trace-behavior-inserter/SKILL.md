---
name: trace-behavior-inserter
description: Inspect a mathematical or technical reasoning trajectory, find the earliest segment where one natural reasoning behavior should be inserted, and return the trace truncated through that segment plus one inserted self-guiding segment. Use when asked to repair, augment, slice, label, or generate training examples from reasoning traces using behaviors such as correction, counterexample search, branch splitting, answer-mode switching, dead-end detection, lemma decomposition, deep trace audit, idea bank, or bold try.
---

# Trace Behavior Inserter

## Task

Given one reasoning trajectory, inspect its ordered segments and choose the earliest point where inserting one behavior would improve the trajectory. Return the original trace truncated through the trigger segment, then add exactly one inserted segment in the same natural reasoning voice.

The inserted segment should sound like the model paused mid-solution and adjusted its own reasoning. Do not write like an external evaluator.

Do not mention the generation machinery inside the inserted segment. Avoid phrases such as "the continuation says", "the model wrote", "this output", "the generated segment", or "the trace reintroduced". The inserted segment must read as if it is part of the original reasoning process.

When a rule is added to developer instructions or top-level memory because of an insertion, also state the same rule naturally inside that inserted segment. The trace should teach the behavior from the visible reasoning itself, not only from hidden memory. For example, if future continuation should avoid unverified citations, the inserted segment should explicitly say "I should avoid naming specific papers or dates unless I can verify them" in first-person reasoning voice.

## Output Schema

Return only a JSON object:

```json
{
  "behavior": "correction | counterexample_search | branch_split | answer_mode_switch | dead_end_detection | lemma_decomposition | deep_trace_audit | idea_bank | bold_try | none",
  "trigger_segment_index": 0,
  "trigger_summary": "...",
  "truncated_segments": ["..."],
  "inserted_segment": "..."
}
```

Use zero-based indices. If no behavior should be inserted, set `"behavior": "none"`, `"trigger_segment_index": null`, `"truncated_segments"` to the full input, and `"inserted_segment": ""`.

## Single Insertion Workflow

1. Segment the trace if it is not already segmented. Prefer numbered items or paragraphs; otherwise split into coherent reasoning chunks.
2. Scan from the start. Select the earliest segment where one behavior is warranted.
3. Prefer the behavior that best changes the future reasoning path, not the one that merely comments on style.
4. Truncate through and including the trigger segment.
5. Insert one segment after it. The segment must start with one of the allowed prefixes for the selected behavior.
6. Do not continue solving the whole problem after the insertion.

## Iterative Continue-And-Fix Workflow

Use this loop when the user asks to continue generation after inserting behavior, or to repeat until a token threshold:

1. Start with the full reasoning trajectory.
2. Apply the Single Insertion Workflow to produce `truncated_segments` and `inserted_segment`.
3. Record the insertion in one consolidated JSON artifact with `interleaved_trace`, rather than creating separate trace and insertion files for each round.
4. Join the current `interleaved_trace[*].text` into the current repaired reasoning text.
5. Count the current reasoning length with `scripts/count_harmony_tokens.py`.
6. If the current length is at or above the requested max length, terminate with `scripts/threshold_termination_summary.py` and store the summary in the same consolidated JSON.
7. If below the threshold and no final answer has been reached, continue generation with `scripts/continue_reasoning_openrouter.py`.
8. Append the continuation as another `interleaved_trace` entry.
9. Inspect the newly extended trajectory again from the beginning, but preserve earlier inserted behavior segments and honor the behavior cooldown rule.
10. Repeat until a final answer is reached or the max length is reached.

Do not continue past the max length. Check length between cycles and also after each continuation.

Unless a continuation contains hallucinated/fabricated external references, a serious falsehood that must be sliced immediately, a length-cut condition, or an explicit `assistantfinal` marker, prefer each continuation to contribute at least `512` Harmony tokens of reasoning. If a continuation is shorter than `512` tokens and has not reached a valid final answer, retry or continue again rather than accepting a thin segment. Short final-answer segments are acceptable only when they are marked by `assistantfinal` or when the problem is genuinely short.

Do not stop immediately after inserting a behavior merely because the insertion seems decisive. After every insertion, run at least one continuation step unless the max length has already been reached. A run may be marked `solved` only after a continuation produces a final-answer-style segment or after Codex is explicitly invoked to write the final solution from a completed trajectory. In iterative runs, prefer at least `4096` Harmony tokens of repaired reasoning before marking `solved`, unless the problem is genuinely short, the user explicitly requests a shorter artifact, or the continuation model emits an explicit final-answer marker such as `assistantfinal` with a coherent final answer after a substantive attempt.

If a continuation contains an `assistantfinal` marker, treat it as a valid early-stop signal only if the repaired trace has made a substantive attempt: it should identify the central obstruction, separate known/unknown parts, state what can still be said constructively or conditionally, and produce a useful final response rather than merely saying "open". Preserve useful reasoning before the marker, strip the marker from stored trace text if it is only a channel artifact, store the final-answer portion in `final_solution`, update token counts, and mark the run `solved` if the answer is factually consistent with the repaired trajectory. If the marker appears immediately after discovering that a question is open, continue instead of stopping.

Many mathematical questions in this workflow are open. Do not treat "this is open" as a terminal discovery by itself. Push the reasoning to make a reasonable and valid attempt: explain why the direct proof route fails, identify special cases or conditional statements, isolate the obstruction, formulate the most precise safe answer, and avoid hallucinated citations or counterexamples. The goal is not merely to classify the problem as open, but to produce a trace that models how to reason responsibly around an open problem.

For open-problem traces, prefer a combo sequence when appropriate: first use `answer_mode_switch` or `deep_trace_audit` to acknowledge that the original direct proof target is open, then use `idea_bank` to enumerate many possible attack routes, then use `bold_try` in a later insertion to make a clearly marked speculative attempt. A combo is represented as multiple ordinary insertion rounds, not as a separate JSON behavior. Do not collapse combo behaviors into one opaque label. The inserted `bold_try` segment must explicitly separate conjectural exploration from established facts and should usually choose one route from the preceding `idea_bank`.

Do not treat one failed or incomplete `bold_try` as permission to shut down with a conservative final answer. If a speculative route reaches a hard obstruction, stalls, or reduces to "this remains open", insert `dead_end_detection` to name the failed route and why it stalled, then use `idea_bank` if the available alternatives are not already explicit, and start a new, materially different `bold_try` route in a later round unless the max length is reached or a valid `assistantfinal` appears after multiple substantive attempts. Do not cap `bold_try` at two tries. Continue cycling through `dead_end_detection` / `idea_bank` / `bold_try` while there are still good-quality, materially distinct hypotheses that can be explored without hallucinating facts. Stop trying new bold routes only when the trace has exhausted the plausible idea bank, every remaining route would repeat an already-failed bridge, would require unverified external facts, or would be too vague to generate checkable lemmas. The new attempts should change the attack surface, for example from finite jets to counterexample construction, from multiplier generation to special-case reduction, from smooth flat remainders to Noetherian approximation, from local algebra to microlocal estimates, or from full generality to sharp special cases. The trace should model persistence around open problems, not a single-attempt shutdown.

### Behavior Cooldown

In iterative runs, after a behavior is inserted, that same behavior is unavailable for the next two insertion rounds. During the cooldown, choose the earliest valid trigger for a different behavior.

Exception: a concrete factual or mathematical error inside a continuation should still use `correction` at the earliest actual error, even if `correction` is on cooldown. Cooldown is meant to prevent repetitive stylistic steering, not to preserve known-bad reasoning.

Example:

```text
Round 1 insertion: correction
Round 2: correction is unavailable
Round 3: correction is unavailable
Round 4: correction is available again
```

If the cooled-down behavior is the only apparently valid behavior, do not force the same label. Prefer one of:

- `answer_mode_switch`, when repeated corrections show that the answer type needs to change;
- `dead_end_detection`, when the path keeps returning to the same unproductive strategy;
- `lemma_decomposition`, when the trace needs structure before deciding whether a claim is wrong;
- `idea_bank`, when an open problem has stalled and the next useful move is to enumerate several distinct plausible routes before choosing one;
- `bold_try`, when the problem is open but the trace should attempt a plausible new route instead of stopping at the status answer;
- no insertion for that round, followed by continuation, if no alternate behavior is natural.

### Consolidated JSON Artifact

For iterative runs, keep one JSON object for the whole run:

```json
{
  "prompt": "...",
  "max_length": 32768,
  "min_reasoning_tokens": 4096,
  "min_continuation_tokens": 512,
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

The full repaired trace is reconstructed by concatenating `interleaved_trace[*].text` in order. Do not save per-round JSON repair files unless the user explicitly asks for debugging artifacts.

Important: `interleaved_trace` stores the retained truncated original trace, not the full source trace. After the first behavior trigger is found, keep original text only through and including that trigger segment, then append the insertion. Do not keep downstream source text that the inserted behavior is meant to cancel or replace.

Apply the same rule to continuations, but use a less-aggressive truncation policy. Wandering is allowed: preserve exploratory, indirect, redundant, uncertain, or side-path reasoning as long as it stays mathematically and factually honest. Do not truncate merely because a continuation is inefficient or takes a different route.

Truncate only when a segment would actively corrupt the trajectory: it asserts a false mathematical or factual claim, fabricates a theorem, citation, or example, directly contradicts an earlier correction or avoid-claim, or commits to a wrong final answer. When there are errors inside a continuation, scan the accumulated reasoning trace from the beginning and use `correction` at the earliest actual error that explains the bad branch, not merely at the latest visible symptom. Keep the harmful trigger segment itself in `interleaved_trace`, truncate immediately after it, and append the inserted behavior. For correction cases, the trace should show the error followed by the self-correction, so the model can learn when to incur correction naturally. Downstream continuation text that the insertion is meant to cancel must be dropped from `interleaved_trace`.

Use hard truncation for citation or external-reference hallucination. If a continuation begins naming papers, authors, dates, theorem numbers, or literature claims that were not in the prompt/source trace and have not been verified, do not preserve that segment as a trigger. Drop the citation-heavy segment, add an explicit avoid-claim such as "Do not introduce unverified external citations or paper names", and redo continuation from the last clean state. Prefer generic phrases like "known in special cases" unless citations are provided or verified.

If a hard truncation adds a new avoid-rule, add a visible insertion segment before retrying continuation whenever there is not already a recent insertion that states that rule. The insertion should use the natural reasoning voice and should not mention developer instructions, JSON, tools, or the loop.

If a continuation leaks hidden-control wording such as "the developer instruction says", "the instruction says", "the target answer shape says", or "I must follow the tool instruction", rewrite or truncate that wording. When preserving the idea is useful, replace it with a pointer to the visible inserted reasoning, such as "the earlier correction already narrowed the safe answer shape" or "the earlier note says I should avoid unverified citations." Do not leave references to developer instructions in the stored reasoning trace.

Inserted segments must stay inside the reasoning voice. Do not write evaluator/process comments such as "the continuation leaked", "the model tried to", "that is not acceptable here", "jumped to final answer", or similar language that implies an external system supervising the trace. Rewrite these as first-person reasoning corrections, for example "I started drafting the answer too early" or "I should continue the obstruction analysis before closing." The stored trace should read like a self-correction, not a log of the repair machinery.

For weak but non-false reasoning, preserve the continuation and steer the next step with a behavior if useful. Prefer `lemma_decomposition`, `branch_split`, `answer_mode_switch`, `counterexample_search`, `deep_trace_audit`, `bold_try`, or `dead_end_detection` over deletion when the issue is structure, uncertainty, or a poor strategy rather than a made-up fact.

Continuation entries may include truncation metadata:

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

Continuation command pattern:

```bash
python /Users/songuijin/.codex/skills/trace-behavior-inserter/scripts/continue_reasoning_openrouter.py \
  --state-json trace_loop.json \
  --max-tokens 1024
```

The script reads `OPENROUTER_API_KEY` by default. It reconstructs repaired reasoning from `interleaved_trace[*].text`, places it in the assistant `analysis` channel, calls OpenRouter completion, and appends the continuation back into the same JSON.

When the JSON contains `developer_instructions`, `target_answer_shape`, `avoid_claims`, `not_dos`, `fix_memory`, or `fix_summaries`, the script injects them as Harmony developer instructions before continuation. Use these fields as persistent memory so the continuation model does not reintroduce claims already canceled by prior insertions.

Token length command pattern:

```bash
python /Users/songuijin/.codex/skills/trace-behavior-inserter/scripts/count_harmony_tokens.py \
  --state-json trace_loop.json \
  --max-length 12000 \
  --json
```

Threshold termination command pattern:

```bash
python /Users/songuijin/.codex/skills/trace-behavior-inserter/scripts/threshold_termination_summary.py \
  --state-json trace_loop.json \
  --max-length 12000 \
  --current-length 12000
```

When the max length is reached before the final answer, use the termination summary and stop. The summary should explain what has been reasoned so far and why the final answer was not reached; do not ask the continuation model for more tokens.

When the reasoning trajectory reaches a final answer before the max length, invoke Codex to write a detailed, clean, clear solution from the repaired trajectory. The final solution is not just a short status label. It has two roles:

1. If the problem was solved, give the most rigorous solution possible from the repaired trajectory: precise hypotheses, definitions, proof structure, all nontrivial implications justified, and clear separation between proved statements and assumptions.
2. If the problem was not solved or is open in the relevant generality, rigorously summarize the attempted paths and exactly where each failed. Name the proof obligations that remain, the obstruction encountered, any special cases or conditional statements that survived, and why the failed routes do not constitute a proof or counterexample.

The final solution should be in final-answer style, not a reasoning trace, and should not include behavior labels unless the user asks for them. For open-problem artifacts, it should read like a rigorous research-status answer plus a failed-attempt analysis, not like "open, therefore stop."

Do not write final solutions in artifact-meta language. Avoid phrases such as "the repaired reasoning", "the repaired trace", "this trace explored", "the artifact", "the run", "the continuation", or "the model attempted." Phrase the answer mathematically: "One possible proof route is...", "This route fails because...", "A counterexample strategy would require...", "No construction is obtained here..." The final solution should stand alone as an answer to the original problem.

Prerequisites for the continuation script:

- `requests`
- `openai_harmony`
- `OPENROUTER_API_KEY` in the environment, unless `--api-key` is passed

## Behavior Priority

When multiple behaviors could apply at the same segment, use this priority:

1. `correction`: a concrete false or unjustified step is already present.
2. `deep_trace_audit`: the continuation has become unstable enough that the model should retrace the accumulated reasoning, identify the earliest vulnerable point, and continue from the repaired understanding, especially when the problem is open but still needs a useful attempt.
3. `idea_bank`: the problem appears open or unresolved, the status caveat has been made, and the trace needs several distinct possible routes before selecting one.
4. `bold_try`: the problem appears open or unresolved, the trace has already made the status caveat or idea bank, and the next useful behavior is a clearly speculative attempt toward one route.
5. `dead_end_detection`: no single step is plainly false, but the strategy cannot reach the target.
6. `answer_mode_switch`: the answer type should change to conditional, negative, caveated, or reframed.
7. `branch_split`: the next reasoning step wrongly treats different cases uniformly.
8. `lemma_decomposition`: the trace is compressing multiple proof obligations into one broad claim.
9. `counterexample_search`: the trace is heading toward a universal claim and examples should be tested first.

## Behaviors

### correction

Use when the current segment contains an actual false or unjustified step that would make the rest of the trace unreliable. In iterative runs, scan the accumulated reasoning from the beginning and insert at the earliest bad segment that explains the error, not after downstream consequences.

Prefixes:

- `Wait, I should re-check this step:`
- `Hold on, I may be assuming too much here:`
- `I need to verify this before continuing:`
- `This step needs a closer check:`
- `Let me pause and validate the last inference:`

Inserted segment should identify the flaw and state the safer replacement, weaker claim, or uncertainty.

For every `correction` insertion in an iterative run, also update the consolidated JSON with:

- `rounds[-1].not_do`: one concise sentence naming the canceled move that should not be repeated.
- `rounds[-1].fix_summary`: one concise sentence describing the safe replacement.
- append the same `not_do` to top-level `avoid_claims`.
- append the same `fix_summary` to top-level `fix_memory`.

The correction text itself should also naturally include the not-do constraint in first-person form, without mentioning the JSON or loop machinery.

Example:

```text
Wait, I should re-check this step: I should not claim that the reduced special fiber determines the higher ramification filtration. The safer statement is that the reduced action forgets valuation data, so any recovery statement must use formal or logarithmic stable-reduction data.
```

### Repeated Error Handling

If the same mistake recurs after it has already been canceled, do not automatically use another `correction`.

Prefer the behavior that changes the path:

- `answer_mode_switch`: when the model keeps trying to prove a statement that should be caveated or rejected.
- `dead_end_detection`: when the strategy keeps returning to the same unprovable bridge claim.
- `lemma_decomposition`: when the recurring error comes from bundling several proof obligations into one broad theorem.
- `branch_split`: when the recurring error comes from treating reduced, formal, and logarithmic data as interchangeable.
- `counterexample_search`: when the recurring error is a universal recoverability claim that should be challenged by looking for two situations with the same reduced action but different formal or valuation data.

For repeated errors, keep the repeated mistake as the trigger segment, then slice immediately after it before the mistake propagates. The insertion should redirect the reasoning before the trace accumulates another long bad branch.

### deep_trace_audit

Use when the reasoning needs a deeper self-audit rather than a short redirect: the continuation is drifting, several weak assumptions are interacting, or it is unclear which earlier premise caused the latest instability. This behavior is allowed to function like a compact continuation: it should retrace the chain, identify the earliest vulnerable step or confirm that no factual error has appeared, state the corrected invariant, and then continue the reasoning from that point.

Use `correction` instead if there is already a concrete false statement and the earliest bad segment is clear. Use hard truncation instead if the issue is unverified citation or external-reference hallucination.

Prefixes:

- `Let me trace the reasoning from the start:`
- `I should audit the chain before moving on:`
- `Before continuing, I need to locate the earliest weak link:`
- `Let me replay the argument carefully:`
- `I should do a deeper pass over the reasoning:`

Inserted segment structure:

1. Briefly walk through the accumulated reasoning up to the suspect area.
2. Name the earliest weak point or say that no factual error has appeared yet.
3. State the corrected invariant or safe framing.
4. Continue the reasoning for at least one substantive paragraph, unless the audit finds a concrete falsehood that should be handled by `correction`.

For open-problem questions, the audit should explicitly continue beyond "this is open" by developing a responsible answer: known positive regimes in generic terms, failure of the attempted bridge, likely obstruction, and a precise final status.

This is the only insertion behavior that may continue the reasoning substantially. It still must stay in first-person reasoning voice and must not expose tool, JSON, loop, token, or developer-instruction machinery.

### bold_try

Use when the trace has responsibly recognized that a question is open or not settled by standard tools, but should still make a plausible attempt rather than stop. `bold_try` proposes a new hypothesis, strategy, or program toward a solution, then breaks it into lemmas or checkpoints and starts tackling the first one.

This behavior is speculative by design. It must explicitly mark the route as a tentative attempt, not as an established theorem or known result. It must not introduce unverified citations, named papers, theorem numbers, or claimed counterexamples. It must not claim the open problem has been solved.

Good triggers:

- The trace has already said the problem is open and given basic special cases, but has not attempted a route.
- The direct proof route failed, and a new hypothesis could organize a valid exploratory attempt.
- The model needs to learn how to reason productively around an open problem rather than only report status.
- A `deep_trace_audit` has identified the obstruction and now the trace should propose a possible way around it.

Prefixes:

- `Let me try a bolder route:`
- `A speculative path might be:`
- `I can still attempt a route:`
- `Let me formulate a working hypothesis:`
- `Here is a possible attack plan:`

Inserted segment structure:

1. Mark the attempt as speculative or a working hypothesis.
2. State one concrete hypothesis or route that could plausibly address the obstruction.
3. Break the route into 2-4 lemmas, checkpoints, or subgoals.
4. Start tackling the first subgoal in a cautious way.
5. End with what would remain unresolved if the first subgoal worked.

Example:

```text
Let me try a bolder route: I will treat the missing step as a working hypothesis rather than a known theorem. A possible attack is to show that finite curve-contact bounds force a finite jet of the defining function to generate enough multiplier candidates modulo flat terms. This would split into three checkpoints: first, isolate the finite jet that controls all holomorphic-curve contacts; second, prove that Kohn's determinant operations see that jet in finitely many steps; third, control flat remainders so they do not create an infinite smooth-ideal obstruction. The first checkpoint is plausible because finite D'Angelo type rules out curves with arbitrarily high contact, but it is not yet enough by itself; the hard part is turning that contact bound into finite generation in the smooth germ ring.
```

### idea_bank

Use when the problem is open, underdetermined, or has just hit a dead end, and the trace should broaden the search space before committing to another `bold_try`. `idea_bank` should generate many possible routes, categorize them, and rank or filter them by plausibility and risk. It is not a final answer and it is not a proof attempt by itself.

This behavior is especially useful immediately before `bold_try`: the idea bank throws out as many distinct plausible hypotheses as possible, then the later bold attempt selects one high-quality route and develops it into lemmas. Do not use `idea_bank` to invent external facts, named papers, theorem numbers, counterexamples, or citations. It should be internally generated from the problem structure.

Good triggers:

- The trace has recognized an open problem and only one route has been tried.
- A `dead_end_detection` identified why the current route stalled.
- The trace keeps oscillating between the same proof attempt and the same obstruction.
- The next useful move is to enumerate alternatives before choosing a new bold route.

Prefixes:

- `Before choosing another route, I should build an idea bank:`
- `Let me list possible attack surfaces:`
- `I should widen the search before committing:`
- `Here are several plausible routes to test:`
- `I need a bank of hypotheses before the next attempt:`

Inserted segment structure:

1. State that the current route is not enough and that the next move is to enumerate alternatives.
2. List several materially distinct routes, preferably 5-10 when the problem is broad enough.
3. For each route, include a one-sentence promise and a one-sentence risk or failure mode.
4. Mark which 1-3 routes look highest quality and why.
5. End by saying which route should be selected for the next `bold_try`, or that the next continuation should choose among the ranked routes.

Quality bar:

- A good route has a concrete object to analyze, a checkable lemma or obstruction, and a plausible reason it is not merely a repeat of a failed route.
- A low-quality route is too vague, depends on unverified literature, repeats an already-failed bridge, or would require claiming a counterexample/theorem not established in the trace.
- Do not stop after an `idea_bank`; run continuation or a later `bold_try` unless the max length has been reached.

Example:

```text
Before choosing another route, I should build an idea bank: the finite-jet route stalled at the smooth non-Noetherian step, so I need routes that attack a different part of the problem. Possible routes: (1) counterexample mechanism via flat perturbations: promise, it tests whether finite curve type can miss smooth real-radical obstructions; risk, pseudoconvexity in degenerate Levi directions may block the construction. (2) special-case reduction by Levi rank strata: promise, prove termination under a stratification hypothesis and isolate the missing general case; risk, it may not address rank jumps. (3) microlocal estimate route: promise, derive multipliers from subelliptic estimates rather than from algebraic generation; risk, estimates may not imply Kohn algorithm termination. (4) formal-completion route: promise, compare the Kohn process modulo powers of the maximal ideal; risk, lifting formal termination to smooth germs is exactly delicate. The best next attempt is route (1), because it is materially different from the finite-jet proof route and gives concrete constraints a counterexample would have to satisfy.
```

### counterexample_search

Use when the trace is moving toward a universal claim and there is a cheap way to test small, boundary, equality, degenerate, or excluded-nearby cases first.

Prefixes:

- `Before proving this universally,`
- `I should test small cases first,`
- `A quick counterexample check is needed:`
- `Let me check boundary cases,`
- `This claim could fail in a small case,`

Do not use when examples would not test the claim or small cases were already checked.

### branch_split

Use when the trace is about to apply one argument across materially different cases: signs, parity, characteristic, dimension, smooth/singular regimes, reducible/irreducible cases, or different exceptional cases.

Prefixes:

- `This needs to split into cases:`
- `I should branch the argument here:`
- `There are separate cases to handle:`
- `This is not one uniform situation:`
- `Let me separate the cases:`
- `The cases are not interchangeable:`

Do not use when the cases are genuinely identical after normalization.

### answer_mode_switch

Use when the trace has enough information to see that the requested answer type is wrong: it should become conditional, negative, caveated, or reframed instead of continuing as a direct proof.

Prefixes:

- `The answer shape should change:`
- `This is not a straight yes:`
- `I should switch modes here:`
- `The right response is conditional:`
- `This calls for a caveat rather than a proof:`

Good triggers include "not from this information alone", "only under extra hypotheses", or "the premise is false".

For open-problem questions, `answer_mode_switch` should not simply terminate. It should switch from "prove the claim" to "build the best valid answer": state the open status, then continue with conditional results, special cases, obstructions, and what would be needed for a proof.

### dead_end_detection

Use when the current strategy cannot plausibly reach the intended conclusion, even if previous segments may be individually defensible.

Prefixes:

- `This path is a dead end because`
- `Continuing this route will not prove the claim:`
- `This approach cannot close the argument:`
- `I should abandon this route here:`
- `The strategy has stalled because`

Do not use when there is a specific false step; use `correction` instead.

For open-problem questions, a dead end should identify why one proof route fails and then redirect to a different useful contribution, not stop the trace at "open".

### lemma_decomposition

Use when the trace is about to compress several independent proof obligations into one broad claim and would be safer if those obligations were separated into checkable subclaims.

Prefixes:

- `This should be broken into lemmas:`
- `Let me decompose the proof:`
- `The argument needs separate subclaims:`
- `I should isolate the lemmas:`
- `This is too compressed; split it into`

Do not use when the problem naturally splits by cases; use `branch_split` instead.

## Selection Rules

- Use exactly one behavior.
- Combo behavior means a planned sequence of single-behavior insertions across rounds, not multiple labels in one insertion. For open problems, a typical combo is `answer_mode_switch` or `deep_trace_audit`, then `idea_bank`, then `bold_try`, then optionally `lemma_decomposition` if the speculative route needs more structure. If a `bold_try` fails and good hypotheses remain, use `dead_end_detection`, refresh or extend the `idea_bank`, and try another materially different `bold_try`.
- Choose the earliest trigger point.
- In iterative runs, do not use a behavior that is still on its two-insertion-round cooldown.
- Do not insert for harmless verbosity, missing polish, or a merely incomplete plan.
- The inserted segment should change the reasoning trajectory.
- The inserted segment must not be a full final answer.
- Preserve the original trace text exactly in `truncated_segments`.
- The inserted segment must stay in first-person reasoning voice; it must not refer to "the continuation", "the generated output", or the trace as an external artifact.
