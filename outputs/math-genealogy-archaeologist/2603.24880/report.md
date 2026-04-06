# Report mode: full_report

## Source ledger

- Canonical work node: `arXiv:2603.24880`.
- Observed source URL: `https://arxiv.org/abs/2603.24880`; observed version: `v1`; source type: `arxiv-abs`.
- Read in this run: arXiv abs page, localized arXiv source archive, `main.tex`, `4CT.bib`, `00README.json`.
- Localized but not read as paper-body text: PDF.
- Seed-paper bodies were not read in this run. Their titles and years were stabilized only from the target bibliography metadata in `4CT.bib`.

## Seed ranking

1. **Robertson--Sanders--Seymour--Thomas (1996/1997)** — immediate seed. The target presents RSST as the simpler proof and quadratic-time algorithmic predecessor, and says its own near-linear algorithm improves that additive-constant reduction pipeline into constant-factor reduction.
2. **Steinberger (2010)** — immediate seed. The target says it reuses Steinberger's discharging rules and imports the positive-final-charge theorem as the basis of its theorem (i).
3. **Franklin (1922)** — supporting seed. The target uses Franklin both as an earlier obstructing-cycle reduction precursor and as the source of the classic 6-regular configuration that is not D-reducible.
4. **Birkhoff (1913)** — supporting seed. The target cites Birkhoff for internal 6-connectivity of minimal counterexamples and for the Birkhoff diamond as a D-reducible configuration.
5. **Appel--Haken (1976/1977; 1989 book form)** — supporting seed. The target uses Appel--Haken as the earlier reducibility-based proof benchmark with 1482 reducible configurations.

## Pressure points

- The inherited algorithmic bottleneck is that earlier proofs and algorithms only guarantee one reducible configuration or one obstructing cycle at a time, so the problem size drops by an additive constant and the total coloring time stays quadratic.
- The inherited structural bottleneck is that positive-curvature discharging explains reducible configurations near charged vertices, but not in the large flat regions that the target needs to exploit.
- The target also insists on D-reducibility rather than arbitrary reducibility, because it wants many simultaneously usable local reductions rather than a single classical witness.

## Missing-cell analysis

- No ancestor paper body beyond the target itself was read, so every genealogy edge is target-mediated rather than independently verified from the ancestor paper.
- The run supports only first-hop ancestry from the target. It does not support second-hop edges among RSST, Steinberger, Franklin, Birkhoff, Appel--Haken, Kempe, or Heawood.
- Bibliography metadata stabilized titles, venues, and years, but it was not used as sole support for any substantive genealogy edge.

## Transfer-vs-novelty boundary

- Transfer supported by the target text: reducible-configuration and obstructing-cycle reduction as the general four-color proof template; RSST's quadratic-time additive-constant reduction strategy; Steinberger's discharging rules and positive-charge implication; Franklin's obstructing-cycle reduction; Birkhoff's D-reducible diamond and internal-6-connectivity framing.
- Novelty supported by the target text: linearly many pairwise non-touching reducible configurations or non-crossing obstructing cycles, the exploitation of flat zero-curvature regions, a near-linear `O(n log n)` coloring algorithm, and a new larger D-reducible 6-regular configuration replacing Franklin's non-D-reducible 6-regular case for this purpose.
- The evidence does not support stronger claims such as "the older papers already contained the same theorem in disguise" or "the novelty is only implementation detail."

## Blind reconstruction

The bounded reconstruction is that the paper starts from the established reducible-configuration/obstructing-cycle paradigm for four coloring, treats RSST's quadratic-time method as the immediate algorithmic baseline, imports Steinberger's discharging framework for the positive-charge regime, and then asks how to get many local reductions at once, especially in flat regions where the classical positive-curvature story is silent.

## Comparison with target

- This reconstruction agrees with the target's explicit framing that the key change is moving from one local reduction to linearly many, and from additive-constant shrinkage to constant-factor shrinkage.
- It also agrees with the target's explicit claim that theorem (i) reuses Steinberger's proof framework while the deeper flat-case results are the paper's fundamental new contributions.
- It undershoots the target whenever a finer historical story would require reading the ancestor papers themselves rather than relying on the target's descriptions of them.

## Reconstructed question

How can the classical four-color reducibility-and-obstruction framework be strengthened so that planar triangulations yield linearly many simultaneously usable local reductions, including in flat zero-curvature regions, thereby supporting near-linear-time four coloring instead of quadratic-time additive-constant recursion?

## Confidence and uncertainty

Confidence is **medium**. The report has enough support for a cautious full first-hop genealogy because the target text itself explicitly names and characterizes the main predecessors. The uncertainty is also explicit: ancestor-paper bodies were not read, so all non-target historical claims remain target-mediated and bounded.
