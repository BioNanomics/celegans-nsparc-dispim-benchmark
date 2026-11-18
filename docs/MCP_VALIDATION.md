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
