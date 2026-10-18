# Lab-manager brief: NSPARC versus published diSPIM benchmark

**Decision requested:** Is our Nikon Ti2/AX + NSPARC platform sufficient to recover a reliable *C. elegans* embryo nuclear lineage over 7.5 hours, or would light-sheet imaging materially improve the experimental science?

## The replication target

Duncan and colleagues' 2019 JoVE light-sheet protocol imaged ten **BV514 `ujIs113`** embryos containing ubiquitous mCherry-histone nuclear fluorescence. They recorded 451 3D volumes per embryo at 60-second intervals over 7.5 hours at 20 °C, evaluated developmental milestones and viability, and reported no detectable phototoxicity under those conditions [1].

We will emulate the **biological readouts and cadence**, not claim equivalent optical sectioning.

## Proposed work

**Before starting:** Confirm which nuclear fluorescent reporter worms are available, with priority to **BV514** if obtainable and suitable. Inspect local Ti2/NSPARC objective clearance, 561-nm excitation availability, NIS-Elements recording modes, environmental temperature control, ND2 data storage, image acquisition duration for whole-volume scans, and hatching follow-up workflow.

**Phase A — calibration and 2-hour pilots:**
- Immobilize and image freshly mounted 2–4-cell embryos with a validated preparation preserving viability. Capture a no-exposure mounting control.
- Determine whole-embryo XY/Z sampling, exposure, laser dose at specimen, hardware channel configuration and readout time.
- Compare 60-second versus 180-second full-stack cycles and correct/failed nuclear segmentation on manually reviewed frames.
- Reject conditions that visibly arrest or damage embryos; revise before proceeding.

**Phase B — 7.5-hour feasibility:**
- Randomly allocate an initial three embryos per arm to NSPARC_60s, NSPARC_180s, and CONTROL, balanced across days/mounts.
- Record the entire embryo and key metadata; in fluorescence conditions monitor from 2–4-cell stage through approximately 7.5 hours, checking whether actual acquisition fits cadence.
- Continue hatching and developmental follow-up as consistently as possible across arms.

**Phase C — reproducibility:**
- If pilot criteria are reasonable, expand to about ten embryos per arm; document every attrition, segmentation failure, and late-development limitation.
- Use StarryNite/AceTree or another validated pipeline for nuclear centroids and identities; manually audit predefined early/mid/late stages.
- Produce summary figures and a recommendation: proceed with NSPARC; modify acquisition; or investigate diSPIM.

## Key readouts

1. **Manual nucleus detection accuracy** by stage and depth (TP/FP/FN, precision, recall/F1).
2. **Correct parent–daughter links**, after manual ground-truth review.
3. **Developmental trajectories**, with time anchored to a reproducible observed stage.
4. **Developmental perturbation:** abnormality, cell division/milestone timing, and hatching.
5. **Engineering metrics:** XY/Z sampling, achieved intervals, 3D volume duration, measured excitation power, raw vs processed NSPARC image quality.

Provisional feasibility gates: ≥95% *detection recall* through the 100-cell stage and ≥90% correctly assigned verified lineage edges, with no conspicuous viability/timing difference from matched controls. These are study-planning goals, not scientific equivalence claims.

## Decision rubric

- **Go with NSPARC:** useful lineage accuracy persists through the intended stage and viability resembles same-run controls.
- **Optimize NSPARC:** acceptable viability but high-Z/deeper nuclei are missed or 60-second stacks take too long; tune optics/exposure/Z and validate again.
- **Test diSPIM:** sufficient dose or scan speed for long-term, full-embryo coverage cannot be achieved, particularly late in development.

## Handoff requested from manager

Select reporter strain; approve mounting SOP; designate imaging operator and manual lineage reviewer; confirm ND2 storage and objective compatibility; approve sample-size/threshold adjustments; name first imaging date. File settings in `data/templates/acquisitions.csv` and record results in remaining templates.

## Reference

[1] Duncan et al., *Journal of Visualized Experiments* (2019), DOI: [10.3791/59533](https://doi.org/10.3791/59533).
