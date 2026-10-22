# NIS-Elements pilot setup sheet (DRAFT, fill in at the microscope)

Purpose: prepare the Nikon Ti2/AX + NSPARC session so that every setting the analysis needs is captured the first time. Follows `docs/PROTOCOL.md` (sections 4 and 5) and `docs/ACQUISITION_WORKSHEET.md`.

Rules for this sheet:
- **Nothing here is a validated setting.** Blank means "to be determined in the pilot". Do not copy numbers from other labs or papers.
- Menu and dialog names below are generic. **Confirm each on your own NIS-Elements install** and correct this sheet if they differ.
- The column in `[brackets]` is the `acquisitions.csv` field that the value goes into.
- Never write a guessed value. Leave it blank; a blank is "unknown" and the software will warn about it.

---

## 0. Before the session (no embryos yet)

- [ ] Reporter strain confirmed with the lab manager (target BV514 `ujIs113`, mCherry-histone). `[strain]` `[reporter]`
- [ ] Mounting method approved by the lab manager (Duncan 2019 used poly-L-lysine on a no. 1.5 coverslip with M9, but that is context, not our SOP). `[mount_id]`
- [ ] Stage-top temperature measured with a calibrated thermometer, target 20 °C. Reading: ______ `[temperature_c]`
- [ ] NIS-Elements version: ______ `[nis_elements_version]`
- [ ] Objective: ______ NA: ______ immersion: ______ `[objective]` `[objective_na]` `[immersion]`
- [ ] 561 nm laser available and filter/detector path verified. `[excitation_nm]`
- [ ] Storage ready: free disk space ______, backup location ______, `.nd2` saved read-only afterwards.
- [ ] Output folder for the run created with `python -m celegans_benchmark init-run --run-dir <private folder>`.

## 1. NSPARC checks (answer these first; they decide the protocol)

- [ ] Which NSPARC output modes does this install offer? List: ______
- [ ] Can **raw (summed detector)** and **processed (reassigned / deconvolved)** outputs be produced from the *same* scan? Yes / No. `[nsparc_mode]`
  - If yes: this is the case for the "raw vs processed" spec in `docs/temp/NSPARC_pending_specs_for_approval.md`.
  - If no: note it in the proposal; the comparison would need two scans.
- [ ] Scan type used (galvano / resonant) and its effect on stack time: ______
- [ ] Bit depth and save format: ______

## 2. Fit test: does one Z stack fit in the interval?

The 60 s arm is impossible if a stack takes 60 s or longer.

1. Pick a test embryo/sample and set the Z range so the **whole embryo** is covered at every stage.
2. Record: Z range ______ µm, step ______ µm `[z_um_per_plane]`, planes ______ `[z_planes]`, pixel size ______ µm `[xy_um_per_px]`.
3. Time ONE full stack with a stopwatch or the NIS timestamp: ______ s.
4. Compare:
   - 60 s arm: stack time must be clearly below 60 s (leave room for focus correction). Fits? Yes / No
   - 180 s arm: stack time below 180 s. Fits? Yes / No
5. If the 60 s arm does not fit, **stop and tell the lab manager.** Do not shorten Z coverage silently; options are fewer planes, a larger step, or a smaller field of view, each of which changes the sampling and must be recorded.

Also check sampling against the optics (Nyquist for your NA and 561 nm emission) with the lab manager. The protocol's 0.15–0.20 µm XY and 0.5–0.75 µm Z are only starting values to evaluate.

## 3. Excitation power (the dose record)

- [ ] Measure power **at the sample** with a power meter, in mW. Value: ______ `[power_at_sample_mw]`
- [ ] Laser power setting in NIS (percent): ______ `[laser_power_percent]` (a percent is not a dose; keep both)
- [ ] Pixel dwell / averaging / scan speed: ______
- [ ] Choose the **lowest power that still gives usable nuclear detection**, judged by detection quality, not by an arbitrary percent.
- [ ] Short test acquisition (30–120 min) of early embryos, then reassess detection and viability before any long run.

## 4. ND acquisition setup (confirm names on your install)

For each fluorescence embryo:

- [ ] Time loop: interval = ______ s (60 or 180) `[planned_interval_s]`; duration = ______ min (up to 450 min for 7.5 h); expected volumes = ______
- [ ] Z loop: range, step and planes as measured in section 2
- [ ] XY positions: one per embryo (multi-position); record which position is which `embryo_id`
- [ ] Focus: use the Ti2 Perfect Focus System if available; record offset and any manual corrections. Notes: ______
- [ ] Channel: 561 nm / mCherry, NSPARC detector, mode from section 1
- [ ] Save: `.nd2` to the controlled storage folder, file name contains the `embryo_id`
- [ ] Do NOT apply enhancement or deconvolution to the only copy. Save raw first.

CONTROL embryos get **no** repeated fluorescence. Follow them by transmitted light on the same observation schedule across groups when possible, and note any brightfield use in `notes`.

## 5. During the run

- [ ] Temperature checked at start and every ______ min: readings ______ `[temperature_c]`
- [ ] Watch for dropped or incomplete stacks, focus drift and visible damage; note times in `notes`
- [ ] Stop rule agreed with the lab manager (arrest, blebbing, heating): ______
- [ ] Start stage and the time-alignment anchor recorded `[start_stage]` (use one observable event, e.g. ABa/ABp division, never raw movie start)

## 6. After the run

1. Record the **achieved** interval from the NIS metadata/timestamps: ______ s `[measured_interval_s]` and volumes recorded `[recorded_volumes]` (the software warns if it exceeds the plan by more than 5%).
2. Checksum the raw file and paste it in:
   `python -m celegans_benchmark checksum --file <path to .nd2>` -> `[raw_sha256]`, path in `[raw_data_uri]`
3. Make the file read-only and back it up.
4. Fill `embryo_id`, `group`, `batch_id`, `operator` `[embryo_id]` `[group]` `[batch_id]` `[operator]`
5. Validate: `python -m celegans_benchmark validate --data-dir <run folder>`, and fix or explain every WARNING.
6. Verify later with: `python -m celegans_benchmark verify-raw --data-dir <run folder> --raw-root <raw folder>`.

## 7. Go / stop decisions for the pilot

- Stack does not fit the 60 s interval -> stop, tell the lab manager.
- Embryos arrest or look damaged -> stop or reduce exposure under the lab's approved SOP; reassess.
- Detection poor even at the highest acceptable power -> record it; this is a valid finding, not a failure to hide.
- Everything fits and embryos look normal -> proceed to the 3-embryo-per-arm pilot, then decide on full-length runs.

## 8. Quick map: where each CSV column comes from

| Column | Source |
|---|---|
| strain, reporter, batch_id, mount_id, operator | lab notebook / strain list |
| temperature_c | calibrated thermometer reading |
| start_stage | observed at start |
| objective, objective_na, immersion | objective barrel / NIS |
| excitation_nm, laser_power_percent | NIS acquisition settings |
| power_at_sample_mw | power meter at the sample |
| nsparc_mode, nis_elements_version | NIS settings / About dialog |
| xy_um_per_px, z_um_per_plane, z_planes | NIS acquisition settings |
| planned_interval_s | time loop setting |
| measured_interval_s, recorded_volumes | NIS metadata after the run |
| raw_data_uri, raw_sha256 | storage path + `checksum` command |

## Open questions to settle with the lab manager before the first session

- Final mounting SOP and chamber.
- Stop rules and the maximum acceptable exposure.
- Whether raw and processed NSPARC can be exported from one scan.
- Who images, who reviews, and the first imaging date.

---

## Session log: 2026-10-22 (no sample; settings read from NIS only, no laser used)

### Instrument as found

| Item | Value |
|---|---|
| Software | NIS-Elements AR 6.20.02, build 2065, 64-bit |
| System | Nikon AX confocal on Ti2, NSPARC detector ("AX NSPARC" light path) |
| Lasers | 405, 488, 561, 640 nm |
| NSPARC modes | SR Mode, CF Mode; "Live Deconvolution for SR Mode" option; virtual pinhole slider |
| Objectives on nosepiece | 4x, 10x, 20x, 60x (Plan Apo λD 60x oil, OFN25, DIC N2), 100x (Plan Apo λD 100x oil), 20x |
| 60x NA | not yet recorded (read from objective barrel) |
| Focus | Perfect Focus System (PFS) present |

### Optical experiment created

- Name: `Celegans_BV514_NSPARC_pilot` (created with Add > Based on Dyes, then Save As; other experiments untouched).
- One channel: mCherry, 561 nm excitation, detection 570-616 nm. No transmitted (TD) channel.
- Fast (hardware-driven) experiment, single pass. CF Mode. 60x.
- Scanning bidirectional, integrating 1, dwell 1, scan area 512.
- Laser power left at the default (3.0%); to be set with a sample.

### Frame times read from NIS (60x, no scanning performed)

| Setup | Scanning | Scan area | Frame time |
|---|---|---|---|
| Previous 4-channel setup | Bidirectional | 1024 | 3.9 s |
| Previous 4-channel setup | Bidirectional | 512 | 2.0 s |
| Previous 4-channel setup | Unidirectional | 512 | 4.0 s |
| mCherry only | Unidirectional | 2048 | 5.8 s |
| **mCherry only (current)** | **Bidirectional** | **512** | **0.49 s** |

Estimate for one Z stack at 0.49 s per slice: 40 slices ~20 s, 60 slices ~30 s, before Z-move and focus overhead. If that holds, the 60 s arm fits. **Not yet measured; confirm with a timed stack on a sample.**

### Findings to discuss with the lab manager

1. **No 40x objective is installed.** The protocol suggests e.g. a 40x water/silicone objective; the realistic options here are the 60x oil or 100x oil. Is an oil objective acceptable for live embryos in aqueous buffer?
2. **Pixel size.** At 60x, 512, zoom 1, pixels are 0.58 µm; the protocol suggests 0.15-0.20 µm. Plan: zoom ~3x on the embryo (field ~100 µm), which keeps 512 x 512 and should keep the frame time.
3. **The laser "TD" (transmitted) channel uses the 561 nm laser.** CONTROL embryos must be followed with the lamp (DIC/brightfield), not the laser TD channel.
4. **Detection window 570-616 nm** covers the mCherry peak but not its long tail; revisit if nuclei are dim.
5. **NSPARC mode:** CF vs SR, and whether both can be saved from one scan, is still open.

### Templates to prepare (ND Acquisition)

| # | Name | Purpose | Time | Z | Volumes |
|---|---|---|---|---|---|
| 1 | `Celegans_BV514_NSPARC_pilot` | Optical setup | - | - | - |
| 2 | `Celegans_01_stack_timing` | Time one Z stack (fit test) | none | whole embryo | 1 |
| 3 | `Celegans_02_pilot_short_60s` | Short trial first (protocol step 6) | 60 s for 60 min | whole embryo | 61 |
| 4 | `Celegans_03_NSPARC_60s_full` | NSPARC_60s arm | 60 s for 450 min | whole embryo | 451 |
| 5 | `Celegans_04_NSPARC_180s_full` | NSPARC_180s arm | 180 s for 450 min | same Z as #4 | 151 |
| 6 | `Celegans_05_followup_brightfield` | CONTROL and hatching follow-up for all groups (lamp only, no laser) | same schedule for every group (lab decision) | single plane or a few | - |

Set during the first imaging session: Z range and step, zoom/crop, laser power, PFS offset, XY positions.

### Templates saved (verified 2026-10-22 by reading NIS's stored ND settings)

ND Acquisition templates, all saving ND2 to `D:\Qurratul_Celegans\TimelapsePath` (outside the git repo):

| Template | Interval | Duration | Stacks | Z step | Close shutter when idle | PFS |
|---|---|---|---|---|---|---|
| `Celegans_01_stack_timing` | no time loop | - | 1 | 0.75 µm | - | off |
| `Celegans_02_pilot_short_60s` | 60 s | 60 min | 61 | 0.75 µm | on | off |
| `Celegans_03_NSPARC_60s_full` | 60 s | 450 min | 451 | 0.75 µm | on | off |
| `Celegans_04_NSPARC_180s_full` | 180 s | 450 min | 151 | 0.75 µm | on | off |
| `Celegans_05_followup_brightfield` | not created yet: needs the manager's follow-up schedule (lamp only, no laser) | | | | | |

Notes:
- **In every template Z Top = Bottom = 488.04 µm, i.e. ONE slice.** This is a placeholder from setting up without a sample. The real range must be set on the embryo each run (see checklist below).
- `Celegans_01_stack_timing` is stored twice (older and newer copy); harmless, the older one can be removed.
- Another group's stored setup (LilyOTV) was left untouched.
- A test acquisition ran by accident at 19:17 without a sample (561 nm laser on briefly); it wrote `Celegans_01_stack_timing.nd2` (one blank slice). Not data; do not use.
- Danger found and fixed: the ND panel initially held a leftover Z range ~5.9 mm above the current focus (from another experiment). It was cleared with Reset. Always check Relative Positions before running.

### Run checklist (every imaging session, before pressing Run)

1. Select optical experiment `Celegans_BV514_NSPARC_pilot`; confirm one channel (mCherry, 561 nm), 512, bidirectional, integrating 1.
2. Load the ND template for the arm (`Celegans_02/03/04`).
3. In Z: press **Reset**, then focus on the top of the embryo and press **Top**, the bottom and press **Bottom**. Check Range (~30 µm), Steps (~41 at 0.75 µm) and that Relative Positions are small (tens of µm, never thousands).
4. Set zoom/crop to the embryo (target ~0.2 µm pixels) and the lowest usable laser power; record power at the sample in mW.
5. Decide PFS on/off with the sample and record it.
6. Change the filename to include the `embryo_id`.
7. Time one stack first (`Celegans_01_stack_timing`) and confirm it fits the interval before a long run.
