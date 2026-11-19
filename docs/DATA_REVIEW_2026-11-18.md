# Acquired-data review: 18 November 2026

The existing recordings support instrument and image-quality research, and one short movie is a useful starting point for manual annotation. They do not yet establish embryonic cell-lineage tracking or a controlled biological effect of illumination.

## Scope and provenance

The review inspected **17 original ND2 files**, totalling **73,330,962,432 bytes** (73.33 GB decimal; 68.3 GiB), without moving or changing them. Metadata opened for every file, and sampled pixel reads succeeded for every file. Sampling read at most five time points per file, including all Z planes at those time points; it was not a complete pixel-integrity scan. The 15-hour recording received an additional review of 185 selected time points.

All 17 filenames and byte sizes matched the 17 November checksum manifest. Their sizes and modification times were unchanged during inspection. **The raw SHA-256 values were not recomputed in this review**: matching size and modification time are not a fresh cryptographic integrity check.

Portable review records are [inventory.csv](../data/reviews/2026-11-18/inventory.csv), [overnight_samples.csv](../data/reviews/2026-11-18/overnight_samples.csv) and [provenance.json](../data/reviews/2026-11-18/provenance.json). The earlier [checksum manifest](../data/manifests/nd2_sha256_2026-11-17.csv) records the raw locations. Raw images remain in their original storage outside Git.

Timing below is the ND2 file's recorded acquisition timebase. Agreement between its frame metadata and events is not an independent physical exposure-clock calibration. All-time-point starts were checked, but image appearance was sampled. A stable recorded cadence does not establish specimen health, complete biological coverage or valid identities.

## Main recordings

Intervals are measured from the native metadata. Z denotes planes per time point, not a guarantee that the whole organism is covered. All six recordings below report the 10x / NA 0.45 objective.

| Recording (`.nd2`) | Duration; time points | Z planes; channels | Median interval | Saved NSPARC mode | Appropriate use |
|---|---|---|---|---|---|
| `Celegans_01_stack_timing1111` | 10 min; 151 | 1; GFP, RFP, TD | 4 s | Live Deconvolution | First candidate for visible-spot and worm-outline annotation |
| `Celegans_01_stack_timing4hours` | **2 h**; 1,801 | 1; GFP, RFP, TD | 4 s | Live Deconvolution | Signal and whole-field change over time; its filename overstates duration |
| `Celegans_01_stack_timing4hr-2002` | 4 h; 3,601 | 1; GFP, RFP, TD | 4 s | Live Deconvolution | Descriptive signal/movement deterioration and QC limitations |
| `Celegans_01_stack_overnightslip-1112` | 15 h; 5,401 | 1; GFP, RFP, TD | 10 s | CF | Focus and signal-loss troubleshooting, especially the early segment |
| `AML18_rehearsal_timelapse_60s_60min_v2` | 1 h; 61 | 41; channel named mCherry | 60 s | CF | Rehearsal of Z-volume timing and storage |
| `AML18_rehearsal_timelapse_60s_8h_overnight` | 8 h; 481 | 41; channel named mCherry | 60 s | CF | Long-duration volume-recording rehearsal at these settings |

The remaining files include single-stack and short setup tests. Across all 17 files, saved descriptions record **11 CF, 5 Live Deconvolution and 1 SR** acquisitions. These modes must remain separate in analysis; the collection is not uniformly CF. A saved dye/channel name such as `mCherry` is not independent confirmation of the strain or fluorophore in the specimen.

One short file, `Celegans_01_stack_timing002.nd2`, records a planned 20 s interval but observed intervals of approximately 40.08-40.11 s. Both exceed the planned interval by more than 5%. Thus the collection should not be described as having exact or successful timing in every run. The review inventory compares intervals against the recorded plan where one is available; older cached summaries used a threshold relative to their observed median instead.

## Best starting movie: the 10-minute recording

![Sampled GFP, RFP and TD views from the 10-minute recording](figures/acquired_data_review_2026-11-18/single_worm_10min.png)

`Celegans_01_stack_timing1111.nd2` shows a dominant, largely separated worm with visible fluorescent structures and a corresponding TD outline at the inspected times. This makes it the first **candidate**, not an already validated tracking dataset. Another smaller structure is present in the field, and a single plane can lose structures in depth. Recorded XY sampling is approximately 0.507 micrometres per pixel.

The first task is manual review of all 151 frames. Record the worm outline or centroid where visible, then annotate a small set of clearly visible fluorescent spots with uncertain and not-visible states. Do not name neurons from position or reporter brightness alone, infer nuclear divisions, or force a continuous identity through ambiguous frames. Any spot-tracking result should be evaluated on held-out frames chosen before tuning and should report the fraction of frames in which each target can actually be assessed. See the [research roadmap](RESEARCH_ROADMAP.md).

## The 15-hour recording loses useful image quality early

![Early sampled views from the 15-hour recording](figures/acquired_data_review_2026-11-18/overnight_early.png)

![Sampled signal and TD sharpness during the 15-hour recording](figures/acquired_data_review_2026-11-18/overnight_qc.png)

The additional review sampled every five minutes plus the first five frames: **185 of 5,401 time points**. Its baseline is the mean of the first five frames. The fluorescence proxy is the image's 99.9th percentile minus its median, and TD sharpness is variance of the Laplacian divided by squared mean intensity. These are whole-field image proxies, not organism-level outcomes.

| Elapsed time | Relative TD sharpness | Relative GFP proxy | Relative RFP proxy |
|---|---:|---:|---:|
| 5 min | 0.783 | 0.729 | 0.653 |
| 15 min | **0.500** | 0.374 | 0.294 |
| 30 min | 0.330 | 0.187 | 0.152 |
| 60 min | 0.231 | 0.100 | 0.104 |
| 180 min | 0.208 | 0.033 | 0.047 |
| 900 min | 0.176 | 0.020 | 0.019 |

The sampled series is consistent with substantial early deterioration; it does not identify the exact onset between samples. Recorded device events span **0.34 micrometres in Z** (2454.66-2455.00 micrometres), while PFS status is recorded as **3, off/out of range**. These event values are more informative than treating a repeated configured Z coordinate as a dynamic focus measurement. They still cannot isolate drying, sample displacement, optical drift, temperature, movement or bleaching as the cause.

The 15-hour recording is useful for defining a focus-stability problem and evaluating QC measures. It is not evidence of successful 15-hour single-worm or neuronal tracking. Image deterioration or loss of movement does not establish death.

## What the stack recordings add

![Sampled maximum projections from the 8-hour, 41-plane rehearsal](figures/acquired_data_review_2026-11-18/stack_8h.png)

The 8-hour record contains 481 time points with 41 planes at a median 60 s recorded interval. The median first-to-last **plane-start** span is about 27.90 s. That span excludes the final plane's acquisition and the return movement; it is not a measurement of the full stack cycle. Its approximately 1.719 micrometres per pixel XY sampling and moving worm population do not validate crowded embryonic nuclei or a final 60x acquisition recipe. Maximum projections are inspection aids, not replacements for reviewing each plane when counting nuclei.

## Interpretation and next decision

The available specimen is AML18, documented as carrying neuronal fluorescent reporters. This supports a bounded project on **visibility and short-term tracking of fluorescent structures in an imaged worm**, with explicit uncertainty. It cannot substitute for a ubiquitous nuclear reporter in the proposed whole-embryo lineage study.

Prior full-series signal and movement summaries remain descriptive. Signal decline combines intensity changes, changing foreground selection, focus and motion through the field or plane. Fluorescence masks are intensity-derived, so using masks does not remove bleaching or defocus as a confound. Comparisons between the recordings also differ in specimen/mount, channel set, sampling and reconstruction mode; they are not a controlled dose-response or CF-versus-SR experiment.

Next, complete the 10-minute movie's manual annotation and a held-out visibility/spot-linking evaluation. Develop a specimen-specific focus-stability pilot before another long acquisition. The future embryo benchmark requires the appropriate reporter, complete XYZ coverage, a measured stack cycle at the final settings, contemporaneous controls and documented developmental outcomes. MCP checks and ND2 saving are technical milestones; they do not replace those biological measurements.
