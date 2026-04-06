This notebook-style monologue is a grounded reconstruction from the frozen ledger and completed report. It does not add new facts beyond adjudicated ledger claims. This is a plausible reconstruction, not a factual claim about the authors' private thoughts.

I start from the target's own framing, because that is the only safe place to start here. The paper tells me that RSST is the immediate algorithmic baseline: a simpler proof, a quadratic-time coloring method, and a one-reduction-at-a-time regime. That gives the first fixed point.

Then Steinberger enters in a different way. The target says it uses exactly Steinberger's discharging rules, and that theorem (i) is a more specific version of Steinberger's positive-charge theorem. So I should treat Steinberger not just as background, but as imported machinery.

Franklin and Birkhoff sit a little further back in the picture, but still on the first hop. The target uses Franklin for obstructing-cycle reduction and for the old 6-regular configuration that is not D-reducible. It uses Birkhoff for internal 6-connectivity of minimal counterexamples and for the Birkhoff diamond as an early D-reducible witness.

Appel and Haken appear here mostly as scale and proof-tradition pressure. The target contrasts its own stronger aim with their use of 1482 reducible configurations. I should not say more than that, because in this run I did not read the Appel--Haken papers themselves.

Plausible reconstruction: the paper is pressing on the place where the older story seems too local. One reducible configuration, or one obstructing cycle, is enough for correctness, but not enough for near-linear time. The real pressure is to extract many usable local reductions at once, including in the flat regions where the classical positive-curvature story is not already doing the work. This is a plausible reconstruction, not a factual claim about the authors' private thoughts.

That makes the novelty boundary look fairly sharp. The inherited framework is reducibility, obstruction, discharging, and Kempe-style recursive reduction. The target's new move is to turn that framework into a linearly-many-reductions regime and then into an `O(n log n)` coloring algorithm.

I should also keep the boundary visible. I have a bounded first-hop genealogy, not a deeper mathematical family tree. I do not have warrant here to narrate how Franklin relates to Birkhoff, or how Kempe and Heawood should be threaded into the causal spine, because that would require ancestor-paper reading that this run did not do.
