# Genealogy selection rules

## Purpose

Build a bounded backward genealogy for one target paper without treating every cited work as historically decisive.

## Allowed ancestor-role taxonomy

Every included ancestor node must carry exactly one primary role label chosen from this V1 taxonomy:

- `immediate seed`: a target-cited work that directly supplies a problem statement, construction, theorem, or framing the target clearly builds on.
- `supporting seed`: a target-cited work that materially supports the target's setup, notation, background, or reduction path but is not itself the main conceptual launch point.
- `deep ancestor`: an earlier work reached through backward chaining that is needed to explain where a seed came from, not merely that the target cited it.
- `technique ancestor`: a work included because it supplies a method, lemma pattern, proof technology, or transfer trick that later sources explicitly carry forward.
- `author-local clue`: a bounded clue from author-local material such as a talk page, project note, thesis page, or publication list that helps prioritize what to inspect, but does not by itself establish a core genealogy edge.
- `negative ancestor`: a candidate work that was considered and recorded because the evidence shows it should not be promoted to a positive seed or ancestor role.

Do not invent additional ancestor roles in V1.

## Inclusion requirements for every ancestor edge

Every ancestor edge must record all of the following before it can enter the core genealogy:

1. the upstream node and downstream node being connected
2. the chosen ancestor role
3. an explicit written inclusion reason explaining why this edge matters
4. explicit source support naming the concrete source or sources that justify the edge

If the runtime cannot state both an inclusion reason and source support, the edge is unsupported and must be excluded or retained only as a `negative ancestor` entry.

## Core evidence rules

- Prefer the target bibliography and readable backward-chain sources as the basis for core genealogy edges.
- Do not equate `cited by target` with `historically decisive`.
- Do not promote blog posts, summaries, survey blurbs, author pages, or commentary into sole support for an `immediate seed`, `supporting seed`, `deep ancestor`, or `technique ancestor` edge.
- `author-local clue` material may guide search priority or reinforce an already-supported edge, but it cannot by itself create a core seed or ancestor edge.
- Use `negative ancestor` when the evidence shows a tempting candidate is merely background, only name-checked, contradicted by stronger sources, or unsupported beyond commentary.

## Bounded backward-chaining protocol

Start from the target paper and move backward only through explicit evidence-bearing links.

### Depth limits

- Depth 0: the target paper.
- Depth 1: candidate `immediate seed` and `supporting seed` nodes taken from the target bibliography or from readable target text.
- Depth 2: candidate `deep ancestor` or `technique ancestor` nodes reached from a depth-1 source's own readable references or direct textual discussion.
- Depth 3: allowed only when the extra hop is necessary to explain a depth-2 ancestor and the chain still has strong direct evidence.
- Stop when another hop would exceed depth 3.

### Evidence-quality limits

Stop recursion early when any candidate edge depends on weak support such as:

- commentary without readable primary-source backing
- abstract-only or metadata-only access where paper-body evidence is required
- unresolved identity or version drift for the proposed ancestor node
- a second consecutive hop whose edge reason is only inferential rather than text-supported
- a chain that can no longer name a concrete transmitted problem, result, or technique

Depth alone is not enough. A shallower edge still stops if its evidence quality is too weak.

## One outward reinforcement check

One outward check beyond the target bibliography is allowed when available.

Use it only to reinforce, qualify, or demote an already-evidenced candidate edge. Examples include a survey, review, thesis introduction, or author-local page that discusses the same relationship.

External reinforcement cannot by itself create unsupported genealogy edges. If the target bibliography and backward-chain evidence do not already support the edge, the outward check may surface a clue or a `negative ancestor`, but not a core positive ancestor edge.

## Selection discipline by role

- Choose `immediate seed` only when the target or a directly read seed source makes the dependence look central rather than incidental.
- Choose `supporting seed` when the work matters to setup or execution but the target does not treat it as the main conceptual parent.
- Choose `deep ancestor` only when a backward step explains how a depth-1 source itself was formed.
- Choose `technique ancestor` only when the method transmission is explicit enough to name the inherited technique.
- Choose `author-local clue` when the source is useful for prioritization or contextual reinforcement but lacks enough direct evidentiary force for a core edge.
- Choose `negative ancestor` when explicit review is important because the candidate might otherwise be overclaimed.

## Current scope boundary

These rules define genealogy selection only. They do not yet define the full claim-ledger schema, conflict adjudication fields, or final report rendering.
