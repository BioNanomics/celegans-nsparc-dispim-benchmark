# Preanalysis plan (v0.1; freeze before the first data run)

## Experimental unit and denominators

The independent biological unit is an **embryo**, not an imaging volume, cell, or nucleus. Frame/nucleus metrics are nested within embryo. Primary plots include embryo-level variation; do not use hundreds of nuclei as independent biological replicates.

Pilot samples: 3 embryos per group, expanded descriptive run: about 10 per group if feasible. Neither constitutes an appropriately powered equivalence or phototoxicity noninferiority trial. Pre-register more rigorous margins, allocation and power estimates before any formal claims.

## Prespecified readouts

| Outcome | Definition | Caveat |
|---|---|---|
| Nucleus detection recall | TP/(TP+FN), human-reviewed nuclei and frames | Report per stage and near/far depth, with audit policy |
| Precision | TP/(TP+FP) | Image reconstruction may change segmentation threshold |
| F1 | 2TP/(2TP+FP+FN) | Counts must share same audited frames |
| Division linkage correctness | Correctly linked / manually verified lineage events | A 180s interval may miss divisions regardless of SNR |
| Stage depth reached | Last validated stage with interpretable identities | Not simply last recorded volume |
| Developmental timing | Cell divisions / milestones relative to common observed anchor | Raw movie elapsed time is not m.p.f. |
| Hatching | Hatched / embryos with *known* hatching outcomes | Lost to follow-up != failure; also report unknown count |
| Photodose/exposure | Power at sample, scan time, illumination schedule | % laser is not an absolute photodose |
| Technical reliability | Achieved interval, incomplete volumes, focus drift | Z-scan duration must fit cadence |

All raw imaging stacks and segmentation predictions must be retained for audit. Counts and lineage link judgments require independent manual ground-truth review and documented sampling fractions.

## Staging and comparison

For analysis, define **t=0** using a comparable cell division/stage observable in every embryo (e.g. ABa/ABp division). Record start stage separately and avoid comparing embryos by acquisition start time alone. A published plot in *minutes post fertilization* must not be overlaid on an arbitrary movie clock without a validated offset.

Audit nuclear detection at <16, 16–49, 50–99, 100–199, and >=200 nuclei. Compare trajectories and milestones with matched contemporaneous controls first, then contextualize against Duncan 2019 and downloaded EmbAlign atlas data only where compatible.

## Provisional internal feasibility gates

Not literature-derived thresholds; these are targets to discuss with the team:

1. Detection **recall ≥95%** on audited frames through 100-cell stage. Show precision separately; high recall alone can hide false positives.
2. At least **90% of manually verified parent–daughter edges** correctly linked, stage-stratified.
3. Hatching and developmental timeline show **no conspicuous deterioration** relative to contemporaneous controls; a small N cannot establish safety or equivalence.
4. A full-duration 60-second experiment can actually produce the intended sequence without dropped frames, incomplete Z coverage, or excessive photodose.

A priori group comparisons: NSPARC_60s vs CONTROL viability/timing; NSPARC_180s vs NSPARC_60s trade-off between temporal accuracy and cumulative illumination; published diSPIM only contextual unless raw matched controls are obtained.

## Reporting

- Show every embryo with `embryo_id`, group, sampling settings, QC stage limit, and unprocessed fate.
- Plot cell count versus synchronized time *per embryo*, not only pooled means.
- Report embryonic hatching `n/N` and **unknown** outcomes separately. Exact/binomial confidence bounds may be added to a subsequent analysis version.
- Use effect sizes and uncertainty estimates for viability and timing, including batch effects; avoid declaring "no effect" based on non-significant differences.
- Describe difficult late-stage lineaging (movement, nuclei crowding) as limitations, not missing-at-random.
- Preserve unprocessed images and deterministic analysis code version for all plots.

## Future extension

Use EmbAlign to assign identities to manually validated centroids, but benchmark that algorithm independently. **Segmentation recall**, **tracking accuracy**, and **identity assignment accuracy** are three different quantities and must never be substituted for each other.
