# Manual spot-annotation protocol: AML18 10-minute recording

**Status:** prospective annotation protocol and blank review kit, not manual ground truth or a completed tracking result. No coordinates, identities, reviewed frames or algorithmic scores are fabricated by generating the kit.

## Source and question

The source is `Celegans_01_stack_timing1111.nd2`: 151 native time points, a single 1024 by 1024 plane, GFP/RFP/TD channels, approximately 4 s between time points and approximately 0.5066912885 micrometres per pixel. Its raw SHA-256, exact recorded elapsed timestamps and image calibration are stored in the generated frame plan. Verify that the source and frame-plan hashes agree with the kit before reviewing; do not substitute another movie with a similar filename.

The primary task is **manual two-dimensional GFP fluorescent-spot centroid annotation and visibility review** in one imaged AML18 worm. RFP and TD supply context. A fluorescent spot is not automatically an identified neuron, a nucleus undergoing division or a measurement of neuronal activity. The existing image-review montage supports selecting this movie for a feasibility case study, not a claim of complete 3D coverage or known biological identities. See [the acquired-data review](DATA_REVIEW_2026-11-18.md).

## Frozen temporal design

Frame indices are zero-based and native elapsed timestamps are used rather than replacing them with an ideal four-second clock.

| Split | Frame indices, inclusive | Number | Use |
|---|---|---:|---|
| Development | 0-59 | 60 | Annotation-rule practice, target selection, reviewer-agreement assessment and tracker/threshold fitting |
| Temporal buffer | 60-74 | 15 | Visibility and continuity review; excluded from fitting and scored evaluation |
| Evaluation | 75-150 | 76 | Locked-method evaluation on the later portion, approximately the final five minutes |

The later evaluation block may contain harder fading or visibility conditions. The split is intentionally temporal, not a random mix of neighbouring frames. All blocks belong to **one movie**, not independent biological replicates.

**Prior viewing disclosure:** frames **0, 38, 75, 112 and 150** were qualitatively previewed before this plan. Here, *held out* means withheld from tracker fitting and threshold selection; it does **not** mean the images have never been seen. Do not omit this disclosure from a later report.

With seed **20261118**, the secondary-review list is fixed at **19, 34, 47, 49, 53** (development) and **81, 90, 105, 124, 125** (evaluation). Selection uses a deterministic SHA-256 ranking of seed, split and frame index, with five frames per stratum and no image-quality input. Do not replace difficult selected frames with clearer ones. Report any frame that cannot be reviewed and why. The second reviewer should label these independently of the first reviewer's decisions. Development-frame agreement may inform annotation rules; the evaluation subset must not inform fitting or threshold choices.

Freeze and retain the plan before tracker fitting. The plan's canonical SHA-256 excludes only an optional top-level `plan_sha256` field, so that an embedded derived digest can be checked without recursion. Changing the plan, source, calibration or recorded timestamps changes the digest. Do not overwrite a frozen version or silently relabel existing annotations with a new hash.

## Start with empty observations

The annotation CSV initially contains a header only: there are no target or centroid observations yet. For a selected target/frame pair, a missing annotation row means **not reviewed**; absence must never be inferred to mean `not_visible`. Only completed human judgments produce annotation rows, using the three visibility states below. The frame-review CSV contains all 151 planned frames with `review_status=not_reviewed`, source/plan hashes populated and reviewer/time fields blank. Generating these rows does not mean anyone reviewed them.

Use stable reviewer IDs such as `R1` and `R2`. `reviewed_at` is an ISO-8601 date/time with a time zone, recorded when the human decision is made. Every observation and frame-review row retains its `source_sha256` and `plan_sha256`. Use a separate reviewer identity for independent secondary review rather than overwriting the primary decisions.

## Target selection and centroids

1. In development frames, select a small, explicit set of distinguishable GFP targets and assign temporary IDs **S01, S02, ...**. Record why they are eligible. Select before fitting; do not keep only those that later remain clear in evaluation. New targets discovered after the method is locked are exploratory and must be identified as such.
2. Review at the original image resolution and use the same channel mapping. Record primary centroids in **GFP**. RFP/TD may help explain visibility or body position; a target visible only in RFP is not automatically visible in GFP.
3. Coordinates refer to full-image pixel centres: upper-left centre is `(0, 0)`, x is column and y is row. Decimal subpixel centroids are permitted. The valid centre range is 0 through 1023 in each dimension. Cropped or resized display coordinates must be converted to these original image coordinates.
4. Image-space micrometres are derived as `x_um=x_px*pixel_um` and `y_um=y_px*pixel_um`. They are not stage coordinates. Keep pixel and micrometre coordinate pairs consistent with the plan's calibration.
5. Follow the temporary target only while correspondence is defensible. Mark ambiguity rather than forcing identity through a merge, disappearance, new structure or depth change. Do not interpolate missing coordinates or invent a smooth trajectory.

## Visibility and frame-review rules

| `visibility` | Coordinate requirement | Other requirement |
|---|---|---|
| `visible` | x/y pixel and derived micrometre coordinates required | Reviewer ID and review time required |
| `uncertain` | Coordinates optional; if supplied, both axes and their derived values are supplied together | Reason, reviewer ID and review time required |
| `not_visible` | All coordinate fields blank | Reason, reviewer ID and review time required |

Useful reasons include low contrast, defocus, out of plane, out of field, overlap, merged spots and ambiguous correspondence; add free-text detail when needed. These describe the observation. They do not establish bleaching, death or a biological identity.

There is no `not_reviewed` placeholder visibility row in the annotation table. Frame review is recorded separately from per-target visibility. `review_status` is `not_reviewed`, `reviewed` or `needs_review`. Explicitly marking a frame reviewed requires a reviewer ID and timestamp. A reviewed frame need not have a visible selected target; an empty annotation table is not evidence of absence. A selected-target table is also **not a count of all nuclei**.

## CSV contracts

Per-target annotation columns, in order:

```text
source_sha256,plan_sha256,reviewer_id,target_id,frame_index,time_s,split,channel,visibility,x_px,y_px,x_um,y_um,reason,notes,reviewed_at
```

Whole-frame review columns, in order:

```text
source_sha256,plan_sha256,reviewer_id,frame_index,time_s,split,review_status,notes,reviewed_at
```

The plan-generation module defines these schemas and the frame design. It does not itself validate completed human labels, read images or produce manual truth. Preserve original reviewer exports and any later reconciliation separately, recording the reason for each correction. Do not treat a duplicate reviewer/frame/target row as an additional independent observation.

## Before evaluating a tracker

The selected S01, S02, ... targets are a partial reference set, not an exhaustive
annotation of the field. Primary outcomes are selected-target recovery/visibility
coverage, localization error conditional on a valid match, and correspondence
failures over manually evaluable transitions. Algorithm detections outside this
selected set have unknown reference status and must not be counted as false
positives merely because they lack a selected-target label. Whole-field detector
precision/recall requires a separate exhaustive reference in predefined
frames/regions, with its own matching rule and denominator.

Use the frozen selected-target roster to define these denominators:

- Annotation coverage: reviewed target/frame pairs divided by all planned pairs;
  missing rows remain not reviewed.
- Visibility coverage: visible, uncertain and not-visible judgments among
  reviewed pairs, with counts, reasons and durations. Report unreviewed pairs
  separately.
- Selected-target recovery: correctly matched predictions divided by visible,
  unambiguous selected-target observations under the locked matching rule.
- Localization: median and interquartile distance in micrometres for correctly
  matched visible observations, alongside matched and missed counts. This error
  is conditional on a successful match.
- Correspondence: correct links divided by human-confirmed eligible adjacent-frame
  transitions; report identity switches, breaks and abstentions separately.

The fixed secondary-review frame list supports visibility and centroid agreement.
Independent link agreement requires separately prespecified consecutive-frame
pairs or short contextual clips; isolated frames do not validate correspondence.

Leave `matching_tolerance_um` **null** in the frozen frame plan. No scientifically justified matching distance is known yet. Estimate reviewer agreement on the development subset, define a matching rule and tolerance from that evidence, then lock the analysis parameters **before evaluation**. Store that decision in a versioned analysis-parameter record with its own hash; do not edit this plan in place to fill the null field or choose a tolerance from the evaluation scores.

Use development data to fit one simple baseline. Do not use buffer or evaluation results to select thresholds, repair the tracker or cherry-pick targets. Evaluation annotations may be recorded manually, but they must not be fed back into fitting. Any change after evaluation creates a new, explicitly exploratory development round; it does not preserve the original held-out claim.

A later report should separate detection, localization and identity-link errors and show evaluable-frame coverage, uncertain/not-visible intervals, reviewer disagreement and reasons. State denominators and the temporary target definition. With one chosen movie, neither the 151 frames nor the many fluorescent spots are independent biological replicates. The bounded outcome is whether this recording permits auditable 2D visibility and spot correspondence, not embryonic lineage reconstruction or general NSPARC performance.

The raw ND2 stays unchanged and outside Git. Nothing in this offline review authorizes microscope movement, acquisition, illumination changes or preset edits.
