# Protocol v0.1 — experimental design, not a validated wet-lab SOP

## 1. Aim and scope

This proof-of-concept tests whether Nikon Ti2/AX + NSPARC live fluorescence confocal imaging can acquire stage-resolved *C. elegans* embryonic 4D movies of sufficient quality to reconstruct nuclear lineage histories, benchmarked contextually to published diSPIM results [Duncan 2019](https://doi.org/10.3791/59533).

Do not treat nominal nanometer-resolution claims from either manufacturer as proof of higher **biological lineage accuracy**. Registration/deconvolution and embryo mounting differ between systems.

## 2. Materials and equipment, to verify locally

- *C. elegans* embryos carrying a **ubiquitous nuclear fluorescent reporter**. Prefer **BV514 `ujIs113` (mCherry-histone)** when comparing directly to Duncan et al. 2019. Verify genotype/availability through the laboratory or CGC; **JIM113** is used in a separate 2026 EmbAlign study and is not the original 2019 strain.
- Validated live-embryo mounting chamber, buffer and temperature regulation. Avoid excess compression, evaporation and oxygen restriction; the manager must approve the chamber preparation protocol.
- Nikon Ti2/AX imaging path with installed NSPARC detector; NIS-Elements version / NSPARC saved output modes recorded.
- Objective compatible with live embryos and full Z-coverage (e.g. 40x high NA water/silicone/oil *only if mechanically and biologically appropriate*).
- 561-nm excitation and compatible filter/detector configuration **if** mCherry reporter is used.
- Secure storage for raw ND2 data, calibration logs and analysis outputs.

## 3. Experimental arms

| Arm | Full fluorescence Z-volume interval | Exposure | Purpose |
| --- | ---: | --- | --- |
| NSPARC_60s | 60 s | Repeated fluorescence | Published temporal target |
| NSPARC_180s | 180 s | Repeated fluorescence | Lower cumulative dose / weaker temporal sampling |
| CONTROL | None | No repeated fluorescence | Mounting, environment and developmental baseline |

Use random assignment of comparable 2–4-cell stage embryos. Block by imaging day, operator, strain and mounting batch. Keep an attempt log including failures and exclusions; exclude only using a prespecified, blinded rule.

Follow controls by minimally invasive transmitted-light observation, using the **same follow-up observation schedule** across groups when feasible. Brightfield illumination is not guaranteed inert; record use.

## 4. Pilot power / sampling optimization

1. Calibrate thermometer and timekeeping; document **20°C** target within measured environmental variability.
2. On representative embryos, determine full XYZ region of interest and minimum number of Z planes needed to cover entire embryo throughout early morphogenesis.
3. Suggested initial sampling **for evaluation only**: ~0.15–0.20 µm XY pixel size, 0.5–0.75 µm Z-step, 40–60 Z sections. **These are not manufacturer presets and may be under/oversampled for the selected NA and emission wavelength.** Confirm Nyquist, field-of-view, and embryo depth locally.
4. Use 561 nm for mCherry only when the laser and fluorophore are verified. Set the **lowest effective excitation power** by measuring nuclear detection quality (not by using an arbitrary percent).
5. Measure output **mW at the sample**, scan dwell/averaging, Z-stack acquisition duration, actual stack-to-stack interval and sample temperature. Record NSPARC reconstruction settings. If a Z-stack lasts >= 60 seconds, the 60-second arm is not achievable without hardware/scanning changes.
6. Collect initial 30–120 minute acquisition(s) from early-stage embryos, then reassess detection and viability; only after optimization plan 451-volume acquisitions.
7. Where NIS-Elements permits, reconstruct (a) summed detector-array and (b) pixel reassignment/deconvolved outputs **from the same acquisition**. This is a no-extra-illumination algorithmic comparison; do not assert the raw 25-channel data are available without verifying software capability.

## 5. Full-run workflow

1. Prepare fresh embryos according to a locally validated SOP; log strain, reporter, generation, mounting time, mount/chamber ID, position, batch and operator.
2. Randomize to the three arms. Register developmental starting stage independently of acquisition start time.
3. Keep acquisition temperature near **20°C** and log actual range; record focus compensation and drift/correction events.
4. For fluorescence groups, acquire a complete full-embryo stack at planned 60 s or 180 s cadence for up to 7.5 hours, prioritizing biological viability. Log dropped/incomplete volumes, interruptions and frame-level exposure configuration.
5. Record contextual transmitted-light milestones. Where stage-based comparisons require it, synchronize embryo timelines using the same explicit anchor (e.g., observed ABa/ABp division or a fixed first nuclear count), never merely raw movie start.
6. Follow hatching with a prespecified observation window and comparable observation conditions. Record non-hatching as a separate outcome from `unknown` (lost/no follow-up).
7. Save all raw acquisitions as read-only, compute SHA-256 checksums, and record file references and analysis versions. **Do not commit raw ND2 images.**

## 6. Manual validation sampling

For every embryo, stratify audit frames by observed nucleus count: <16, 16–49, 50–99, 100–199, and >=200, including near-side and far-side nuclei when distinguishable. Include division windows, motion, and hard-to-segment clusters. Predefine a sampling scheme and audit **before** reviewing experimental groups. Record TP, FP, FN against human-reviewed ground truth; record lineage events separately as verified correct/incorrect. A segmentation event must not be counted twice in the same denominator.

Because lineage accuracy depends on temporal sampling, don't interpret the 180-second arm's reduced tracking fidelity as an optical detection defect.

## 7. Safety and decision points

Standard *C. elegans* practices, biosafety rules, laser safety, mounting, handling and chemical disposal remain the laboratory's responsibility. If photodamage, heating, arrest or sustained deterioration is observed, stop or reduce exposure under the lab's approved SOP.

A successful pilot supports instrument suitability **for the selected reporter, strain, mounting and developmental stage**, not proof of absent phototoxicity or diSPIM-equivalent microscopy. Refer to `ANALYSIS_PLAN.md`.
