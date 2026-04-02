report_mode: full_report

## Source ledger

- Target arXiv abs: `read` only at the abstract/metadata level.
- Target localized PDF: `quoted`; this supplied the readable paper body.
- Target localized source (`main.tex`): `quoted`; this stabilized the introduction wording and citation context.
- Target bibliography (`main.bbl`): `read`; this stabilized cited-work identity and titles.
- PS24 arXiv abs: `quoted`; used as the single outward reinforcement check.
- Lar21 MIT handle: `discovered` only; it was not directly read in this run.

## Seed ranking

1. **Lar21** - `immediate seed`.
   The target makes Large's exact-Lagrangian flow category the motivating non-framed case, first in the introduction and then again in the geometric example.

2. **AB24** - `technique ancestor`.
   The paper explicitly starts from the framed-flow-category machine of Abouzaid-Blumberg and generalizes that machinery outside the framed regime.

3. **Dou05** - `supporting seed`.
   Douglas is the named framework source for twisted stable homotopy theory on the target side of the equivalence.

4. **PS24** - `supporting seed`.
   Tangential pairs give the concrete bridge for varying tangential structure while keeping the same Floer input, and the outward reinforcement check agrees with that reading.

5. **Fur02** - `negative ancestor`.
   It is worth recording because the target presents it as a possible early signal for the agenda, but the wording is tentative and the underlying source stayed unread here.

## Pressure points

- The framed theory is too restrictive for the motivating exact-Lagrangian case because the Lagrangian difference map can obstruct framing.
- Earlier examples point toward three outputs - Thom-spectrum modules, spectral local systems, and filtered spectral diagrams - so there is pressure for one common formalism instead of three parallel ones.
- Tangential data has to be tunable, not fixed, which is why the tangential-pair strand matters in the supporting genealogy.

## Missing-cell analysis

- Lar21, Dou05, and Fur02 were not directly read as primary texts in this bounded run, so those edges rest on target-side framing rather than direct downstream quotation.
- No depth-2 ancestor survived adjudication because the run did not read enough downstream source text to support a stronger backward chain.
- The Furuta-origin thread remains downgraded because the target itself says "perhaps" and the preprint stayed unread.

## Transfer-vs-novelty boundary

- **Transferred:** AB24 supplies the framed-flow-category machine; Lar21 supplies the exact-Lagrangian flow-category input and its non-framed pressure; Dou05 supplies the twisted-stable-homotopy framework; PS24 supplies the tangential-structure tuning mechanism.
- **Novel:** the target's distinctive move is the mu-structured synthesis that identifies structured flow categories with twisted presheaves.

## Blind reconstruction

Start from the exact-Lagrangian Floer case where framing fails, keep the flow-category input anyway, package orientation, local-system, and filtration behavior through a single mu-structure, and require that the resulting stable category match the twisted-presheaf category suggested by those inputs.

## Comparison with target

- **Agrees:** this reconstruction lands very close to the target's own framing of the problem and the theorem.
- **Undershoots:** it does not reconstruct the deeper internal technical machinery of the later sections, because the run stayed bounded to readable framing evidence plus one reinforcement check.
- **Conflicts:** none surfaced in the adjudicated ledger.

## Reconstructed question

Can one keep non-framed Floer flow-category inputs, let orientation/local-system/filtration data interact through a single `mu : C -> U/O`, and still recover the correct stable target category as twisted presheaves?

## Confidence and uncertainty

Overall confidence is **medium**. Target access is strong because the paper body and source archive were directly read, and the main depth-1 seeds are explicitly named by the target. Confidence is capped because most downstream seed texts were not directly read, so the genealogy is strongest on immediate conceptual parents and weaker on deeper historical ancestry.
