# MCP software validation — 18 November 2026

The existing external MCP server connected successfully, saved a readable
single-frame ND2, and completed a new short ND experiment with five frames at
20-second intervals. An XY move and return succeeded. Both objective-change
directions were exercised, with Z changes recorded rather than assumed absent.
Full study acquisition was not validated.
These are software integration checks, not evidence of specimen focus,
biological image quality, embryo coverage, or study readiness.

The subsequent [NSPARC CF validation](MCP_NSPARC_VALIDATION.md) also completed a
readable save, but its 2048×2048 ND run recorded only one time point because a
scan exceeded the configured 90-second phase. Its five-frame, 20-second cadence
was not achieved; the successful cadence result below applies to the earlier
512×512 AX test.

## Server and test boundary

- The existing global Codex registration `nis-elements-mcp` points to
  `http://127.0.0.1:8767/mcp`. No project-local registration or server installation
  was needed.
- Initial checks used live server version **0.9.0**, at external repository HEAD
  `9e5590b` with pre-existing uncommitted source changes. The later ND test used
  live version **0.9.1** after changes in the external server repository. The
  updated source SHA-256 was
  `a88db57019834b9a568edd965edd0284eee53c77489bb38a1cfa78d7a6331965`.
  A commit identifier alone does not identify that working-tree source.
- The external changes added phase Z readbacks, e-stop boundary rechecks,
  and an explicit ND output collision guard. The pre-existing dirty
  source baseline was preserved in that repository's
  `test-reports/change-review-20261118-vv2mrngl` record.
- Automated tests initially reported **68 passed, 1 deselected**; the updated
  server reported **82 passed, 1 deselected**, recorded as
  `mock-20261118-140443-c298e8a3`. These automated results do not replace the
  separately recorded microscope checks below.
- Server code remains in its own repository. No server implementation or
  instrument configuration was copied into this study repository.
- Raw recordings remain outside Git. Machine-specific paths and detailed local
  tool results are retained in the local evidence record; this note uses the
  recording's filename and checksum.

## Observed checks

| Check | Result | Evidence and limit |
|---|---|---|
| Connection and readbacks | Passed | Existing HTTP registration reached the live server. Subsequent actions used this server. |
| Single capture | Passed for software operation | Completed in 2.906 s: acquire 2.562 s, save 0.141 s, close 0.172 s; phase durations do not include all overhead. The saved file could be read offline. |
| Relative XY move and return | Passed | X readback changed 3530.5 → 3630.5 → 3530.5 µm; Y remained 304.1 µm. This validates the tested move, not every travel limit or tracking workflow. |
| Objective changes | Directions exercised; Z preservation not established | Initial 10× → 4× changed Z readback from 2584.94 to 2584.62 µm. After operator release of the software stop, 4× → 10× completed in about 5.3 s, with Z 2584.72 → 2584.68 µm (−0.04 µm during the turret phase and 0 during calibration). The earlier −0.32 µm change remains unexplained; this is not a focus-preserving round-trip pass. |
| New short ND experiment | Passed for software operation and measured cadence | `MCP_Readiness_90s` completed and saved five readable frames. The call returned after 86.6 s with raw `rc_load=0`, `rc_run=0`, and `nd_running=false`; measured frame intervals were about 20 s. See the artifact below. |
| Availability during ND run | Observed | HTTP `echo` remained responsive. `status` reported the cached in-progress ND record; this was not an independent live XYZ read. |
| Full embryo study | Not validated | No whole-embryo XYZ coverage, study cadence under a complete Z stack, temperature, light dose, lineage accuracy, or viability result was established. The 60× and longer-than-30-minute study workflow was not tested. |

At **13:56:24 EST (America/Indianapolis)**, the software e-stop was engaged pending
operator verification after the first objective/Z observation. The operator
subsequently released it before the return to 10× and the short ND test. At the
end of the later check, status reported **10×, XY=(3530.5, 304.1) µm,
Z=2584.70 µm, ND inactive and software e-stop released**. These are historical
readbacks, not a live status reading. ND Finish/Abort behavior was not exercised.
The final optical-configuration list still contained the same 14 names.

## Capture artifact

`celegans_issue3_20261118_10x_dic_001.nd2`

- Size: **2,859,008 bytes**.
- SHA-256: `ae5732b2280d03050136c5b47cd9158a14cdcea71ae2886fa20aa044b1497630`.
- Dimensions: **C=5, Y=512, X=512**, with no time or Z series.
- Channels: **Blue, Green, Red, Far Red, TD**.
- The data were nearly uniform, around 40–78 counts. Readability and successful
  saving do not establish a visible worm or useful focus; those were outside
  this software-only validation.

## Short ND artifact

The operator requested a new experiment. `MCP_Readiness_90s` was created through
NIS **Save → New**; no existing ND template was overwritten. The persisted
settings index refreshed at **14:07:35 EST**, and the server then listed the new
template. Its time phase was **90 s**, with **20 s** intervals and **5 frames**;
Z, XY, channel and large-image loops were disabled. The ND call began at about
**14:08:40 EST** and returned after **86.6 s**.

`MCP_Readiness_90s_001.nd2`

- Size: **13,475,840 bytes**.
- SHA-256: `88672b726f6503517c4cf772ee0573949b9dcc233e2c4f66e50993af340dc2b4`.
- Dimensions: **T=5, C=5, Y=512, X=512**, without Z or XY series.
- Channels: **Blue, Green, Red, Far Red, TD**.
- Recorded time points: **0.10921535, 20.10921635, 40.10921735, 60.10921735,
  80.10921735 s**. Successive intervals: **20.000001, 20.000001, 20, 20 s**.
- The data remained nearly uniform, approximately 38–96 counts. This software
  test did not establish focus or specimen quality, as the operator requested.

The first-to-last frame span is **80.000002 s**. The configured 90-second phase,
the measured frame span and the 86.6-second call duration describe different
quantities; none is a substitute for another.

The native ND panel automatically advanced its next filename to the `_002.nd2`
suffix after acquisition. The saved template was not overwritten to follow that
increment. The server's conservative collision check can therefore refuse a
future rerun of the saved `_001.nd2` destination; inspect and save a new unused
destination before repeating it. An optional native XML export was cancelled
after file-dialog automation proved unreliable. The named experiment remains
saved in NIS; no XML export is supplied.

## Read-only connection recheck

Later on 18 November 2026, after the settings index was last written at
**14:44:00**, a separate read-only check used the project's `nis` MCP
registration. It called `echo`, `status`, `imaging_status`,
`list_optical_configs` and `list_experiments` one at a time. No call failed or
reported busy. No acquisition, Live view, stage/focus/objective movement,
configuration selection, illumination change, e-stop change or ND run was
performed. These are point-in-time readbacks, not a current status.

| Call | Result | Confirmed values | Unavailable or not established |
|---|---|---|---|
| `echo` | Passed | Returned the sent text unchanged. | — |
| `status` | Passed | Objective **PLAN APO λD 10x OFN25 DIC N1** (nosepiece position 1); XY=(3530.5, 304.1) µm; Z device 0 = **2584.58 µm**; ND inactive; software e-stop released. | Z device 1 returned raw `rc=-4` with 0.0 µm; that value is not treated as a position. |
| `imaging_status` | Passed | Objective readback as above; camera `Nikon_Confocal_Ax`; light path port 3 of 4; DIA LED, AX and D-LEDI shutters closed; DIC analyzer out; Perfect Focus status 3 (off, out of range). | Active optical-configuration names were blank (raw `rc=0`), so no active configuration is established. Port name was null. Live-view state is not read. Names do not prove hardware readiness. |
| `list_optical_configs` | Passed | The same **14** configuration names as before; none was selected. | — |
| `list_experiments` | Passed | **9** saved ND experiments were listed; none was loaded or run. | Durations of the two single-pass Z-stack templates are not known in advance. |

Saved experiments reported by `list_experiments`:

| Experiment | Loops | Configured time phase |
|---|---|---|
| ND Acquisition C. Elegans | Z (0 steps, 0.75 µm) | Single pass; duration unknown |
| Mike Bechill Biofilm Multi-Hour Capture | Time, Z, lambda | 86,400 s; 1,800 s interval; 49 frames |
| Celegans_02_pilot_short_60s | Time, Z | 3,600 s; 60 s interval; 61 frames |
| Celegans_01_stack_timing | Time | 90 s; 20 s interval; 5 frames |
| Celegans_03_NSPARC_60s_full | Time | 27,000 s; 60 s interval; 451 frames |
| Celegans_04_NSPARC_180s_full | Time, Z | 27,000 s; 180 s interval; 151 frames |
| AML18_rehearsal_stack_timing_10x | Z (41 steps, 0.75 µm) | Single pass; duration unknown |
| MCP_Readiness_90s | Time | 90 s; 20 s interval; 5 frames |
| MCP_Readiness_NSPARC_90s | Time | 90 s; 20 s interval; 5 frames |

The XY and objective readbacks match the end state recorded above. Z device 0
read 2584.58 µm, compared with the earlier 2584.70 µm. This check does not
explain that difference or establish focus.

## Single capture with current settings

At **15:25:16 EST** a single test capture was taken through the `nis` MCP
registration using the acquisition settings already active in NIS. No
configuration, preset, laser, gain, pinhole, resolution, illumination,
objective, stage or focus setting was selected or changed. No Live view or ND
experiment was started, and the e-stop was not changed.

Fresh pre-capture checks reported: e-stop released, ND inactive and capture
state idle. The objective was **PLAN APO λD 10x OFN25 DIC N1**, and the camera
was `Nikon_Confocal_Ax`. XY was (3530.5, 304.1) µm and Z device 0 was
2584.58 µm. Light path port 3 was selected. DIA LED, AX and D-LEDI shutters
read closed, the DIC analyzer was out and Perfect Focus was off (out of range).
The active optical-configuration names were blank (raw `rc=0`), so the
acquisition configuration used is **not identified** by the server.

`capture` was called once with `include_stats=false`. It returned `running`,
and the same `capture_id` was polled with `capture_status` until it completed.
No second capture was issued.

| Phase | Time |
|---|---|
| Queue wait | 0.015 s |
| Acquire | **140.032 s** |
| Save | 0.172 s |
| Close | 0.296 s |
| Total | **140.515 s** |

Raw `rc_capture`, `rc_save` and `rc_close` were all 0, and `saved` was true.
The completion readback of the imaging state was unchanged from the
pre-capture check.

`claude_test_20261118_152516.nd2`

- Size: **25,358,336 bytes**.
- SHA-256: `43d841230f0cf693353f62d9fccaf03ad80a0d9c6d15be980c5586232db4dd20`.
- Opened offline with `nd2` 0.11.3, the reader the project already uses.
- Dimensions: **C=3, Y=2048, X=2048**, `uint16`, with no time or Z series.
- Channels: **GFP, RFP, TD**.
- Pixel size: **0.378 µm**.
- Pixel values spanned only **0–58 counts** across all channels. The file is
  readable, but it shows no evidence of specimen signal, focus or useful
  exposure. The shutter readbacks before and after capture do not establish
  whether illumination was delivered during the scan.

The 140-second acquisition of one 2048×2048 frame agrees with the
[NSPARC CF validation](MCP_NSPARC_VALIDATION.md): a scan exceeded a 90-second
phase there. At these settings one frame takes longer than the study's planned
60-second interval. This capture is a software check, not study data.

## 90-second timelapse request stopped at preflight

After the single capture, a new 90-second timelapse was requested: a newly
saved `MCP_Readiness_90s_<timestamp>` experiment with a **20-second interval
and five time points**, keeping the current acquisition settings. It was
**stopped at preflight**. No experiment was created, saved, loaded or run, and
no acquisition setting was changed.

Fresh preflight checks did not fail:

| Check | Result |
|---|---|
| `status` | 10x DIC N1 objective; XY=(3530.5, 304.1) µm; Z device 0 = 2584.64 µm; ND inactive; e-stop released. |
| `imaging_status` | Unchanged from the single capture: camera `Nikon_Confocal_Ax`, light path port 3, all shutters read closed, analyzer out, Perfect Focus off. Active configuration names were still blank. |
| `capture_status` | Idle; the previous capture's completed record showed **140.032 s** to acquire. |
| `list_experiments` | The same 9 experiments; no `MCP_Readiness_90s_<timestamp>` experiment existed. |

**Reason for stopping:** the current settings took about 140 s to acquire one
2048×2048 frame. That cannot support a 20-second interval, and five frames
cannot fit in a 90-second phase. The [NSPARC CF validation](MCP_NSPARC_VALIDATION.md)
recorded only one time point under similar conditions. The request did not
allow acquisition settings to be changed, so the run was not attempted.

Z device 0 read 2584.64 µm, compared with 2584.58 µm at the single capture. No
stage or focus command was issued, and this check does not explain the
difference.

To repeat this test, a person must choose faster acquisition settings in NIS.
Options include a smaller scan size (512×512 took about 2.6 s per frame in the
earlier AX test), a faster scan mode or fewer channels. Measure the new frame
time with one capture first. Then create the new experiment with
**Save → New** and verify it with `list_experiments` before running it.
Alternatively, lengthen the interval to suit the measured frame time; that
would not be the five-frame, 20-second test requested.

## Single capture after operator change to 512×512

The operator then switched NIS to a **512×512** scan in the NIS window; the
server did not change any setting. At **15:42:23 EST** one further test capture
was taken through the `nis` MCP registration with the settings then active.
No configuration, preset, laser, gain, pinhole, illumination, objective, stage
or focus setting was selected or changed by the server. No Live view or ND
experiment was started, and the e-stop was not changed.

Fresh pre-capture checks reported: e-stop released, ND inactive and capture
state idle. The objective was **PLAN APO λD 10x OFN25 DIC N1**. XY was
(3530.5, 304.1) µm and Z device 0 was 2584.64 µm. Camera, light path, shutter,
analyzer and Perfect Focus readbacks were unchanged from the previous capture.
The active configuration names were still blank. The server does not read scan
size, so the resolution change is confirmed from the saved file.

`capture` was called once with `include_stats=false`. It returned `running`,
and the same `capture_id` was polled until it completed. No second capture was
issued.

| Phase | Time |
|---|---|
| Queue wait | 0.031 s |
| Acquire | **20.594 s** |
| Save | 0.156 s |
| Close | 0.250 s |
| Total | **21.031 s** |

Raw `rc_capture`, `rc_save` and `rc_close` were all 0, and `saved` was true.

`claude_test_20261118_154223.nd2`

- Size: **1,765,376 bytes**.
- SHA-256: `5bf9f447a3db903eca0ffcc1aee1a907616d8301165abe5769b5e78c6e891c0d`.
- Opened offline with `nd2` 0.11.3.
- Dimensions: **C=3, Y=512, X=512**, `uint16`, with no time or Z series.
- Channels: **GFP, RFP, TD**.
- Pixel size: **1.513 µm**.
- Pixel values spanned only **0–55 counts** across all channels. As before, the
  file is readable but shows no evidence of specimen signal, focus or useful
  exposure.

Reducing the scan from 2048×2048 to 512×512 cut acquisition from 140.0 s to
**20.6 s**, about 6.8 times faster. One frame still takes **slightly longer than
a 20-second interval**, before any NIS overhead between frames. The
five-frame, 20-second, 90-second timelapse therefore remains unsupported at
these settings and was not run.

The earlier 512×512 AX capture acquired in 2.562 s. Another setting therefore
still lengthens each scan. Possible causes include scan mode, averaging or
integration, line count, or NSPARC processing; no readback identifies which.
Before repeating the timelapse, either reduce that setting in NIS and measure a
new capture, or choose a longer interval that suits the measured frame time.

## Single capture after reported scan reduction

The operator reported reducing the scan settings in NIS. At **15:44:51 EST**
one further test capture was taken through the `nis` MCP registration with the
settings then active. The server selected and changed nothing, started no Live
view or ND experiment, and did not change the e-stop.

Fresh pre-capture checks reported: e-stop released, ND inactive and capture
state idle. The objective was **PLAN APO λD 10x OFN25 DIC N1**. XY was
(3530.5, 304.1) µm and Z device 0 was 2584.66 µm, 0.02 µm higher than at the
previous capture with no stage or focus command issued. Other imaging readbacks
were unchanged, and the active configuration names were still blank.

`capture` was called once with `include_stats=false`. It returned `running`,
and the same `capture_id` was polled until it completed. No second capture was
issued.

| Phase | Time |
|---|---|
| Queue wait | 0.032 s |
| Acquire | **20.609 s** |
| Save | 0.156 s |
| Close | 0.250 s |
| Total | **21.047 s** |

Raw `rc_capture`, `rc_save` and `rc_close` were all 0, and `saved` was true.

`claude_test_20261118_154451.nd2`

- Size: **1,765,376 bytes**.
- SHA-256: `93a7e9db961a015e2e805773008357a3a0b15d206c3f20208a4ec9345a8e441d`.
- Opened offline with `nd2` 0.11.3.
- Dimensions: **C=3, Y=512, X=512**, `uint16`, with no time or Z series.
- Channels: **GFP, RFP, TD**. Pixel size: **1.513 µm**.
- Pixel values spanned only **0–54 counts**; no specimen signal is evident.

**The reported reduction was not in effect for this capture.** Acquisition
time was unchanged (20.609 s against 20.594 s). The capture settings recorded
in the ND2 metadata were identical to the previous 512×512 capture:

| Setting | Recorded value |
|---|---|
| Detector / NSPARC mode | NSPARC / CF |
| Scanner / scan mode | Galvano Unidirectional / Band |
| Resolution / dwell time | 512 × 512 / 2.0 µs |
| Line Integrating | **10x** |
| Averaging (GFP, RFP) | **10x** each |
| Lasers | 488 nm power 35.2; 561 nm power 11.8 |
| TD gain / pinhole | 24.6 / 19.6 µm |
| Zoom | 1.14 |

Tenfold line integration and tenfold averaging across two fluorescence
channels are the likely main contributors to the 20-second frame. Reducing them
to 1x would be expected to shorten a frame substantially, but only a measured
capture can establish the new time. The change may have been made in an ND
experiment or another panel rather than the active AX scan settings, or not yet
applied. Before the next capture, confirm the reduced values in the active AX
acquisition panel; the server cannot read them before capture.

## Single-channel capture and responsiveness during acquisition

The operator found no "1x" option for line integration or averaging, and set
the active AX scan to **GFP only**. At **15:49:11 EST** one further test capture
was taken through the `nis` MCP registration with the settings then active.
The server selected and changed nothing, started no Live view or ND experiment,
and did not change the e-stop.

Fresh pre-capture checks reported: e-stop released, ND inactive and capture
state idle. The objective was **PLAN APO λD 10x OFN25 DIC N1**. XY was
(3530.5, 304.1) µm and Z device 0 was 2584.64 µm. Other imaging readbacks were
unchanged, and the active configuration names were still blank.

`capture` was called once with `include_stats=false` and returned `running`.
About 1 s into acquisition, `echo` returned its text unchanged and
`capture_status` reported `running` in the `acquire` phase. **The server stayed
responsive during the capture.** The same `capture_id` was followed until it
completed. No second capture was issued.

| Phase | Time |
|---|---|
| Queue wait | 0.016 s |
| Acquire | **10.500 s** |
| Save | 0.125 s |
| Close | 0.187 s |
| Total | **10.828 s** |

Raw `rc_capture`, `rc_save` and `rc_close` were all 0, and `saved` was true.

`claude_test_20261118_154911.nd2`

- Size: **692,224 bytes**.
- SHA-256: `72b5e90ff040f373f37e64171e3e36168227c5a3895027394588a620c47c3399`.
- Opened offline with `nd2` 0.11.3.
- Dimensions: **Y=512, X=512**, `uint16`, one channel and no time or Z series.
- Channel: **GFP**. Pixel size: **1.513 µm**.
- Pixel values spanned only **0–18 counts**; no specimen signal is evident.

Recorded capture settings: NSPARC CF, Galvano Unidirectional, Band scan mode,
512 × 512, 2.0 µs dwell, **Line Integrating 10x**, GFP **Averaging 10x**,
488 nm power 35.2, zoom 1.14. Only the channel count changed from the previous
capture, which halved acquisition time from 20.6 s to 10.5 s.

A 10.5-second frame leaves about 9.5 s within a 20-second interval. A
five-frame, 20-second run therefore appears feasible, but only a measured ND
run can confirm that inter-frame NIS overhead fits. This single-channel shape is
accepted by `run-check`, which requires one channel and one position.

Together with the earlier captures, this covers the issue's capture criterion:
the ND2 files were readable, and the server stayed responsive during
acquisition. It does not establish specimen signal or focus.

## Single-channel 90-second ND run checked with `run-check`

The operator created a new experiment in NIS with **Save → New**, using the
GFP-only scan settings above. `list_experiments` then listed it, and the
settings index had been written at **15:53:08 EST**:

- Saved name: `" MCP_Readiness_90s_1ch"`. **The saved name has a leading
  space**, and the run used it exactly as saved.
- Time loop only: **90 s** duration, **20 s** interval, **5** frames. Z, XY,
  lambda and large-image loops were disabled.
- Output: `MCP_Readiness_NSPARC_90s_002.nd2`. The file did not exist before the
  run, so nothing was overwritten. The name follows the earlier NSPARC template
  rather than a `_1ch` name and should not be mistaken for an NSPARC
  2048×2048 result.
- Autofocus state is not reported by the server; it relies on the operator's
  setup.

Fresh preflight checks reported: e-stop released, ND inactive, capture idle,
**PLAN APO λD 10x OFN25 DIC N1**, XY=(3530.5, 304.1) µm and Z device 0 =
2584.64 µm. No other experiment was edited or run.

`run_experiment` was called **once** at **15:53:50 EST**. The client's tool call
timed out after 60 s while the run continued. `status` confirmed the run was
active (elapsed 63 s, then 85, 89 and 90 s), and the run was **not reissued**.
At 90 s the server still reported the run active; the next `status`, after
15:55:53, reported `nd_running=false`. Elapsed runtime was therefore between
90 s and about 123 s. The server does not report an exact end time, and the
cached expected end of 15:55:20 was not treated as completion. Afterwards XY
was unchanged and Z device 0 read 2584.66 µm.

`MCP_Readiness_NSPARC_90s_002.nd2`

- Size: **2,904,064 bytes**.
- SHA-256: `07b5a33bde4558d85a8bdeada39f4d6466d5838386d73e10bb4af597bf51a16c`.
- Opened offline with `nd2` 0.11.3.
- Dimensions: **T=5, Y=512, X=512**, `uint16`, one channel, with no Z or XY
  series.
- Channel: **GFP**. Recorded scan settings: 512 × 512, 2.0 µs dwell,
  Line Integrating 10x, Averaging 10x.
- Recorded time points: **0.249, 20.249, 40.249, 60.249, 80.249 s**.
  Successive intervals: **20.000001, 20.000001, 20.0, 20.0 s**.
- Pixel values spanned only **0–17 counts**; no specimen signal is evident.

The project's `run-check` was run with `--planned-interval 20`. The package was
not installed in the available Python, so it was run from source with
`PYTHONPATH=src`; nothing was installed. It exited with code 0:

| Result | Value |
|---|---|
| Time points | 5 |
| Slices per stack | 1 |
| Interval mean / min / max | 20.0 / 20.0 / 20.0 s |
| Late intervals | 0 |
| Estimated missing stacks | 0 |
| Stack duration; stack fits interval | Unknown (single plane) |
| Signal 99.9th percentile, first / last | 6.0 / 6.0 counts (100%) |

**This run met the requested five frames at 20-second intervals.** It covers
the issue's criterion of one short saved ND experiment run end to end and
checked with `run-check`. It validates software timing only. Specimen signal,
focus, Z-stack timing, the 60x workflow and runs longer than 30 minutes remain
untested.

## Decisions on the remaining gaps

Decisions taken on 18 November 2026 for the two gaps in issue #3:

- **60x oil objective: allow it in the server, with safeguards.** Server
  0.10.0 (commit `9516cfb`, mock suite 94 passed) turns to or
  from the 60x oil objective only with `operator_confirmed: true`, lowers Z
  200 µm before the turret turns and never raises it. The 100x oil objective
  and configuration-driven changes off oil stay refused. It is deployed on the
  microscope and passed dry checks (below); **refocus with oil has not been
  validated**, so 60x is still brought into focus by hand in NIS.
- **Long runs: start in NIS.** The 30-minute `run_experiment` limit stays. The
  60-minute pilot and 7.5-hour study templates are started from the NIS window,
  with MCP used for pre-run checks.

Both server changes were merged to `main` in `nis-elements-mcp` PR #3 (merge
commit `28a589f`; CI passed on Ubuntu and Windows, Python 3.11 and 3.13). The
0.9.1 source, on which the earlier microscope checks ran, is commit `fe2df82`
(mock suite 82 passed); 0.10.0 is `9516cfb` (94 passed), and its dry checks are
recorded in `afc7187`. The live server now runs 0.10.0 from `main` (file SHA-256
`1690c1f349e7cf1a5ea7c60268a4a7eb5b384793ebf3b0803748ba7ee9e050bb`).

### 0.10.0 microscope checks (dry)

0.10.0 was deployed to the live server before step 4's e-stop at 16:27:47 EST
(`initialize` reported 0.10.0) with the operator present, the sample seated and no ND run.
XY stayed (3530.5, 304.1) µm throughout. Details are in the server README
(commit `afc7187`).

| Step | Result |
|---|---|
| 1. 60x without `operator_confirmed` | **Refused**; nothing moved (10x, Z 2584.68 µm) |
| 2. 10x → 60x, confirmed | **Passed**: Z 2584.72 → 2384.68 µm before the turret, then position 1 → 3; Z not raised afterwards (2384.58 µm). **Run without oil**, although the confirmation stated oil was applied |
| 3. Manual refocus with oil contact | **Not tested**: raising a dry oil objective toward the dish risks contact |
| 4. Confirmed 60x → 10x with e-stop engaged | **Refused**; nothing moved. The operator released the e-stop |
| 5. 60x → 10x, confirmed | **Passed**: Z 2384.60 → 2184.60 µm before the turret, then position 3 → 1; Z not raised afterwards (2184.42 µm) |

Turret-phase Z deltas were −0.10 and −0.20 µm, similar to the earlier
unexplained objective-change shifts. The MCP client kept the 0.9.1 tool schema
after reconnecting, so steps 2, 4 and 5 were sent to the same server as direct
JSON-RPC calls over HTTP. The server cannot detect oil; step 2 shows it relies
on the person's confirmation. The 10x was left about 400 µm below its earlier
focus.

Remaining before closing the issue:

1. Repeat the 60x refocus with oil and a sample: measure the Z raise needed
   to reach oil contact against the 200 µm clearance.
2. A pilot acquisition using the worksheet's MCP checklist, with a specimen.

## Pilot pre-run check (no embryo)

The pilot acquisition was started with the worksheet's MCP pre-run checks, then
**stopped because no embryo was ready**. Nothing was run. The read-only checks
passed:

| Check | Result |
|---|---|
| `echo` | Answered |
| `status` | 10x, Z 2184.42 µm (about 400 µm below the earlier 10x focus after the 60x checks), XY (3530.5, 304.1) µm, e-stop released, ND inactive |
| `imaging_status` | AX camera, port 3, shutters closed, Perfect Focus off; active configuration names blank |
| `list_experiments` | `Celegans_02_pilot_short_60s`: 60 min, 60 s interval, 61 frames, Z-stack **1 step at 0.75 µm** |
| Output file | `Celegans_02_pilot_short_60s.nd2` did not exist; ample free disk space |

Problems found before any pilot run:

1. The saved pilot Z-stack (1 step) does not match the [protocol](PROTOCOL.md)'s
   40–60 Z sections at 0.5–0.75 µm covering the whole embryo.
2. Single-plane frame time with 10x line integration and 10x averaging was
   10.5 s, so a 40-plane stack would take about 7 minutes, far over 60 s.
3. The protocol's BV514 strain is mCherry-histone, so the pilot should use the
   RFP / 561 nm channel; the earlier single-channel tests used GFP.
4. The pilot needs the 60x oil objective, focused by hand.
5. The 60-minute run must be started in NIS (30-minute MCP limit).

The pilot acquisition remains open until an embryo is mounted.

## RFP-only frame time without integration or averaging

To check whether the 60 s arm is feasible before embryo day, the operator set
the active AX scan to **RFP only, line integration off and averaging off**.
At **16:50:23 EST** one capture was taken on the 10x with no specimen. Fresh
checks reported e-stop released, ND inactive and capture idle. The server
selected and changed nothing.

| Phase | Time |
|---|---|
| Queue wait | 0.062 s |
| Acquire | **1.688 s** |
| Save | 0.125 s |
| Close | 0.640 s |
| Total | **2.531 s** |

Raw `rc_capture`, `rc_save` and `rc_close` were all 0, and `saved` was true.

`claude_test_20261118_165023.nd2`

- Size: **688,128 bytes**.
- SHA-256: `be9a7d9e0d445274f3e68d96daa42497da908452b510a2af6eb457bb26544fdd`.
- Opened offline with `nd2` 0.11.3.
- Dimensions: **Y=512, X=512**, `uint16`, one channel (**RFP**), 1.514 µm pixels.
- Pixel values **0–5 counts**, as expected without a specimen.
- Recorded settings: NSPARC CF, Galvano Unidirectional, Band, 2.0 µs dwell,
  561 nm power 11.8, emission 582–618 nm, zoom 1.14. **Line Integrating and
  Averaging no longer appear in the metadata**, confirming the change took
  effect (earlier files recorded 10x for each).

Acquisition was about six times faster than the 10.5 s GFP frame with 10x
integration and averaging. Estimated stack times from 1.688 s per plane,
**excluding Z movement between planes**:

| Planes | Estimate | Fits 60 s? |
|---|---|---|
| 30 | ≈ 51 s | Yes, with little margin |
| 41 | ≈ 69 s | Probably not |
| 60 | ≈ 101 s | No |

These are estimates only. The next step is a measured 41-plane Z-stack run in
NIS from a newly saved experiment with a new output filename: the
`AML18_rehearsal_stack_timing_10x` template's saved output file already exists.
At 60x, 512 × 512 at this zoom gives roughly 0.25 µm pixels, coarser than the
protocol's 0.15–0.20 µm; a larger frame or higher zoom changes the timing and
must be measured again at the final settings.

## Future study checks and analysis

Before any further hardware action, repeat fresh `status` and `imaging_status`
checks with the operator, and compare the readbacks with the microscope. Select
and inspect the intended optical configuration in NIS. The live development
server offers configuration selection, but that operation was not validated
or used in this check. Confirm a unique output destination separately.

The earlier `Celegans_01_stack_timing` candidate was not run: its saved output
filename already existed. Creating the distinct readiness experiment avoided
overwriting that template or reusing its output. Re-read saved experiments and
inspect their settings in NIS before future use; a persisted template is not
proof of the current acquisition setup.

The study's `run-check` command accepts one channel and one position. It rejects
both five-channel artifacts above. The short ND cadence was checked directly
from its recorded frame times without fabricating a single-channel input.
A single-channel, single-plane time series can
provide interval checks, but stack duration and stack-fit results remain unknown.
A lone image cannot establish cadence. Keep those unknown results explicit;
do not split or relabel the raw capture to imply an XYZ test passed.

For a genuine single-channel nuclear-reporter time/Z acquisition, follow the
existing offline workflow:

```powershell
python -m celegans_benchmark run-check --nd2 <raw-file.nd2> --planned-interval <seconds> --out <new-local-report-folder>
```

Record the checksum, planned versus measured settings and any interruptions.
The short rehearsal does not replace the [acquisition worksheet](ACQUISITION_WORKSHEET.md)
or the [study protocol](PROTOCOL.md). The 60-minute and 450-minute study templates
exceed the server's 30-minute run limit and require the documented native NIS
workflow.
