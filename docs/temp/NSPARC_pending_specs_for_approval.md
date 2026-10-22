# NSPARC–diSPIM benchmark: proposed additions for approval

These are proposals only. Nothing is built yet. Each one changes how data is recorded or analysed, so the analysis plan says it needs sign-off before implementation. Please mark each one **Approve / Decline / Change**.

Already built and in use (for context): lineage accuracy by stage, the feasibility-gates table, near/far depth regions, warnings for blank key fields, and the interval check.

---

## Spec 1: Raw vs processed NSPARC variants

**Why.** The protocol wants a raw (summed-detector) and a processed (pixel-reassignment) reconstruction from the same scan, scored against the same hand-checked nuclei. The nuclei table has no way to store both for one frame.

**Proposal.**
- Add a `variant` column to `nuclei_qc` (`raw` or `processed`; blank means a single, unspecified variant).
- The row key becomes `embryo_id + volume_index + depth_region + variant`.

**Rules.**
- Manual cell counts must match between variants of the same frame.
- Reports are split by variant. Gates are computed per variant and never mixed.

**Open question.** Can NIS-Elements export both reconstructions from one acquisition? The protocol says to verify this before relying on it.

**Decision:** [ ] Approve  [ ] Decline  [ ] Change: ____________

---

## Spec 2: Tracker and segmentation software provenance

**Why.** An accuracy number cannot be trusted or reproduced without the software, version and settings that produced it.

**Proposal.**
- New file `analysis_runs.csv`, one row per pipeline run: `run_id, embryo_id, tool_name, tool_version, parameters_uri, parameters_sha256, run_date, operator`.
- Add an `analysis_run_id` column to `nuclei_qc` and `lineage_qc`.

**Rules.**
- Parameters are stored as a hashed file reference, not as free text in the CSV.
- A QC row without a run id produces a warning (not an error).

**Open question.** One run per embryo, or one per embryo and variant?

**Decision:** [ ] Approve  [ ] Decline  [ ] Change: ____________

---

## Spec 3: Phototoxicity readouts beyond hatching

**Why.** Hatching is a coarse outcome. Division timing and total light dose can show harm earlier.

**Proposal.**
- *Division timing:* record division times per embryo (a new `division_times.csv`, or reuse `milestones`). Compare the 60 s and 180 s groups against CONTROL for the same divisions. Controls are not fluorescence-imaged, so their timing comes from transmitted-light milestones, and the comparison must use the same anchor event.
- *Light dose:* add `scan_time_per_volume_s` to `acquisitions`. Relative dose = power at sample × scan time per volume × number of volumes, labelled "relative, not absolute". Percent laser power is not a dose.

**Rules.**
- A blank input gives a blank dose, never 0.
- The embryo is the unit, so timing and dose are summarised per embryo.

**Open question.** Which divisions count as the common anchor?

**Decision:** [ ] Approve  [ ] Decline  [ ] Change: ____________

---

## Spec 4: Standard tracking metrics

**Why.** To compare with published work, we need the same measures it reports.

**Proposal.**
- Add an event type (`division` or `linkage`) to `lineage_qc`.
- Report division-detection accuracy (true divisions found, missed, spurious) and the fraction of tracks that are fully correct over a segment.
- Keep these separate from nucleus detection recall and from identity-assignment accuracy, as the analysis plan already requires.

**Rules.**
- Definitions are fixed before the first data run.
- Links are never counted twice in the same denominator.

**Open question.** Which published paper's definitions do we match? These must be checked against that paper before implementation.

**Decision:** [ ] Approve  [ ] Decline  [ ] Change: ____________

---

## Suggested order if approved

1. Spec 2 (cheap, and prevents gaps that cannot be recovered later)
2. The dose column from Spec 3 (cheap, and must be captured at acquisition time)
3. Spec 1 and Spec 4
