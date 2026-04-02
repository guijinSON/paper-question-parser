# Grounded monologue template

## Purpose

`monologue.md` is a long first-person renderer that comes only after `report.md` and `report.json` are complete.

It is a second-pass output over the frozen adjudicated ledger and the completed report. It does not perform fresh evidence synthesis, add new factual content, or reopen adjudication.

## Required opening boundary

The monologue must begin with a mathematician-style disclaimer that keeps the voice bounded. It must say, in substance, all of the following:

- this notebook-style monologue is a grounded reconstruction from the frozen ledger and completed report
- it does not add new facts beyond adjudicated ledger claims
- `This is a plausible reconstruction, not a factual claim about the authors' private thoughts.` whenever any speculative reconstruction appears

## Voice shape

- first person singular
- mathematically informed notebook voice
- exploratory but disciplined
- no publicity prose, motivational essay framing, or polished retrospective summary of the target
- no claim to direct access to the authors' intentions, feelings, or private reasoning unless such a claim already exists in the adjudicated ledger

## Sentence-level grounding rule

Each sentence must fall into one of these buckets:

1. direct rendering of an adjudicated ledger claim
2. explicit connective paraphrase that does not add facts and stays within the completed report's structure
3. explicitly marked plausible reconstruction that stays visibly hypothetical

If a sentence does not fit one of those buckets, it is out of bounds.

## Speculation marker rule

Whenever the monologue moves from adjudicated content into a hypothetical bridge, it must mark that move with phrases such as:

- `Plausible reconstruction:`
- `A plausible reconstruction is:`
- `This is a plausible reconstruction, not a factual claim about the authors' private thoughts.`

The renderer must not let speculative interpretation sound like settled historical fact.

## Forbidden moves

- adding any fact that is not already adjudicated in `claim-ledger.json`
- upgrading `supported synthesis` to `fact`
- upgrading `speculative interpretation` to settled conclusion
- reviving excluded, blocked, unread, conflict-marked, or downgraded claims as notebook narration
- making the monologue precede the report
- presenting hypothetical private-author reasoning as factual history
