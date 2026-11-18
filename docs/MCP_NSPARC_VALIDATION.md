# NSPARC MCP software check — 18 November 2026

The MCP server captured and saved a readable NSPARC CF image. The repeat ND
readiness test also **completed at 2048×2048**, as explicitly chosen by the
operator, but saved **one time point**. Functional acquisition and saving passed;
the configured five-frame, 20-second cadence was **not achieved**. A scan of
approximately 139.5 seconds exceeded the entire configured 90-second phase.
No focus, stage, or objective command was issued for this NSPARC check.

## Completed single capture

- Native NIS acquisition selection: AX NSPARC, existing `C. elegans AML-18`
  acquisition setup, GFP/RFP/TD channels, current 10× objective.
- File: `celegans_issue3_20261118_nsparc_preview_001.nd2`.
- Dimensions: C=3, Y=2048, X=2048; **25,358,336 bytes**.
- SHA-256: `151edc0facff9249b76fbb75e86920c21a27781e9a4b68beee9c99d67b94137a`.
- Saved acquisition metadata explicitly states **Detector mode: NSPARC** and
  **NSPARC Mode: CF**. The shared `AX`/`Nikon_Confocal_Ax` camera name alone
  would not establish this.
- Capture ID: `c7f09d7040e144748a2795b7fd29d83c`.
- MCP phase timings: queue 3.234 s, native acquisition 140.031 s, save 0.172 s,
  close 1.125 s; total 144.562 s. The pending capture was polled, never retried.
- NIS displayed **139.5 s Frame Time**, consistent with the measured native
  acquisition time. Its saved settings included 10× line integration, 10×
  averaging, 1.0 µs dwell, and 2048×2048 resolution.

This proves readable saving with the configured NSPARC CF path. It does not
validate SR mode, useful neuronal signal, focus, or physical optical routing.
The AX baseline used different resolution and averaging, so the timings are
not a matched detector benchmark.

## Completed ND test: functional save, cadence not achieved

A distinct acquisition-setup copy named `MCP_NSPARC_CF_512_READINESS` was
created with NIS's **Experiment Setup → Duplicate**. The original
`C. elegans AML-18` preset was preserved. Although the copy's name contains
`512`, the operator subsequently chose to **keep 2048×2048**. The actual scan
resolution was **2048×2048**; no reduction to 512×512 was made. After the run,
only this new copy was renamed to **`MCP_NSPARC_CF_2048_READINESS`** to match
the resolution used throughout. A final read-only NIS accessibility check
confirmed that name as the selected acquisition preset and the setup dialog
closed. The original `C. elegans AML-18` preset remained preserved.

The distinct ND template `MCP_Readiness_NSPARC_90s` was created through native
NIS **Save → New**: 90-second time phase, 20-second interval, five configured
time points, Z/XY/Lambda loops off, and a new unused ND2 output. The persisted
settings index was written at **14:44:00 EST**, and MCP verified that saved
template. The output filename is `MCP_Readiness_NSPARC_90s_001.nd2`; its
machine-specific location remains in the local evidence record.

The native ND run used the existing MCP server, version **0.9.1**, with no
server source change for this test. It returned after approximately **143.5 s**,
with raw `rc_load=0`, `rc_run=0` and `nd_running=false`. The saved output was
opened offline only after completion.

- File: `MCP_Readiness_NSPARC_90s_001.nd2`.
- Size: **25,448,448 bytes**.
- SHA-256: `62d47736d16139e810ac5237a749650cf01411c3aef4c0ac4cffa7ce81e48548`.
- Dimensions: **C=3, Y=2048, X=2048**, with **no T or Z dimension**.
- Channels: **GFP, RFP, TD**.
- Saved acquisition metadata explicitly reports **Detector mode: NSPARC** and
  **NSPARC Mode: CF**.
- Actual result: **one recorded time point**, so no inter-frame interval can be
  measured. The configured five time points and 20-second spacing were not
  delivered at these scan settings. This is not a cadence pass or a count of
  missing organisms; no biological outcome is inferred.

At the end of this check, status reported **10×, XY=(3530.5, 304.1) µm,
Z=2584.60 µm, software e-stop released and ND inactive**. These are historical
readbacks, not a live status reading. Focus and neuronal signal were not
validated. The multi-channel file is intentionally not passed to the study's
single-channel `run-check` command or relabeled to force compatibility.

The earlier proposal to reduce scan size was superseded by the operator's
2048×2048 choice. No undocumented camera-format setter was used. Installed
documentation says `CameraFormatSet(2, ...)` uses 2 for Quality/Capture mode;
it is not a documented 512-pixel index.

One panel shortcut inserted an unsaved event into the earlier AX test movie.
The movie was closed using **Close**, without saving the event. Its raw-file
SHA-256 remained `88672b726f6503517c4cf772ee0573949b9dcc233e2c4f66e50993af340dc2b4`.

Local, Git-ignored evidence contains the original files' locations, full saved
acquisition descriptions, signal summaries, checksums and the NSPARC MCP log
excerpt. Final checks found the saved ND checksum unchanged, the earlier AX
test movie checksum unchanged, and no server-source or test-source change
for this NSPARC check. No additional acquisition was made for the rename.
Raw files remain
outside the study repository. No XML export or biological result is claimed
here. A future timing test must use a schedule compatible with the measured
scan duration or explicitly approved changes in acquisition settings. Full
embryo XYZ coverage and the longer study workflow remain unvalidated.
