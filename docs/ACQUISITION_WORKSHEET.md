# Acquisition-day worksheet

Use for each embryo/run. Enter typed values into `data/templates/acquisitions.csv` and the lab's actual electronic notebook; this Markdown page is a checklist, not a replacement for metadata.

## Before imaging

- [ ] Confirm strain ID, genotype/transgene, reporter fluorophore, organism batch and embryo stage.
- [ ] Assign `embryo_id`, mount ID, group, acquisition operator, analysis reviewer, instrument ID and software version.
- [ ] Verify embryo viability / setup-specific mounting SOP and environmental temperature control.
- [ ] Measure stage temperature near specimen (target 20°C); log actual reading and tolerance.
- [ ] Confirm objective type, NA, refractive-index medium, coverslip geometry, laser clearance.
- [ ] Calibrate power at sample and verify excitation/filter paths. Document units, not only %.
- [ ] Set XY pixel size, frame size, Z step, Z range and scan duration. Verify **entire embryo** captured throughout stage range.
- [ ] Verify full-stack cycle fits the arm's target 60 s or 180 s.
- [ ] Document NSPARC detector mode, reconstruction/deconvolution, bit depth and save type.
- [ ] Confirm ND2 storage quota, backup, free disk space and checksum process.
- [ ] Record blinded embryo allocation and pre-agreed stopping rules.

## During imaging

- [ ] Check temperature drift and focus corrections.
- [ ] Record embryo start stage and a time alignment milestone.
- [ ] Log dropped or incomplete stacks, interruptions and equipment changes.
- [ ] Monitor for abnormal development or visible photodamage; follow lab's approved stop rules.
- [ ] Save raw acquisition before running enhancement/deconvolution.

## After imaging

- [ ] Continue agreed hatching follow-up, including non-imaged controls.
- [ ] Record hatching as `1`, `0`, or **blank / unknown**, never infer death from lost follow-up.
- [ ] Calculate SHA-256 of raw ND2; register protected storage URI/path.
- [ ] Export auditable stage-stratified nuclear detection and lineage QC tables.
- [ ] Record exclusions and *all attempted* embryo IDs, including failed scans.
- [ ] Review preliminary technical metrics before next run.

## Using the MCP server (optional)

The standalone `nis-elements-mcp` server runs inside NIS-Elements as the `MCPServer` JOBS task and serves MCP at `http://127.0.0.1:8767/mcp`. Its code, install steps and validation record live in its own repository, not here. It is an aid for checks and repeatable runs; the NIS window stays the primary control, and **a person stays at the microscope for every run**.

What it cannot do for this study, and the decisions taken on 18 November 2026:

| Limit | Decision and consequence here |
|---|---|
| 60x oil objective | **Decision: allow it in the server, with safeguards.** Server 0.10.0 (commit `9516cfb` on branch `feature/0.9.1-safety-readbacks`) turns to or from the 60x oil objective only with `operator_confirmed: true`, given by the person at the microscope for that change after oil is applied. It lowers Z 200 µm first and never raises it; the person raises Z to focus. **Until 0.10.0 is deployed and validated on the microscope, change to 60x by hand in NIS.** |
| ND runs over 30 min refused | **Decision: start long runs in NIS.** The 30-minute limit stays. `Celegans_02` (60 min), `Celegans_03` and `Celegans_04` (450 min) are started from the NIS window; the server is used for the pre-run checks below. |
| Optical configuration selection is not validated for this study | Select `Celegans_BV514_NSPARC_pilot` in NIS before any capture or run. The development server offers selection, but this validation did not exercise it. |
| No Z range setting; `focus_down` only lowers | Z Reset / Top / Bottom are still set by hand on the embryo every run. |

Before the run:

- [ ] `MCPServer` job running in NIS; `echo` answers.
- [ ] `status`: XY, Z, objective and e-stop state match what you see at the scope. Re-check with `status` rather than trusting an earlier reading; a person can move the stage at any time.
- [ ] `list_experiments`: the template for this arm exists and its interval, duration, frames and Z steps match the plan. Record any mismatch. Check the saved name character for character (a stray leading space was saved on 18 November) and that the output filename is new and named for this run.
- [ ] Measure the frame (or stack) time with one `capture` at the run's settings, and confirm it fits the interval. On 18 November, two-channel 512×512 with 10x line integration and 10x averaging took 20.6 s, too slow for a 20 s interval; GFP only took 10.5 s. The server cannot read these scan settings: check them in the AX panel and in the saved file's metadata.
- [ ] Know how to stop: `estop` with `engage`, NIS's **Finish** button for a running ND run (`finish_experiment` cannot interrupt a run in progress), and the microscope's physical controls. Never press JOBS **Abort**.

During the run:

- [ ] `run_experiment` returns only when the run ends; `status` meanwhile reports the server's own record (start, expected end, elapsed time), not a live NIS reading.
- [ ] If the client's call times out (seen after 60 s), the run continues: never call `run_experiment` again. Follow `status` until `nd_running` is false; the expected end alone is not proof of completion.

After the run:

- [ ] Note in the notebook that the MCP server was used and the time range of its log, `~/nis-mcp/log.jsonl` (every call, refusals included).
- [ ] `capture` saves single images to `~/nis-mcp/captures`, outside the study storage; they are checks, not study data. Study ND2 files follow the normal checksum and storage steps above.
- [ ] Only a person releases the e-stop, by deleting `~/.nis-mcp/ESTOP`.

See the [18 November MCP validation record](MCP_VALIDATION.md) for the completed
software checks, the objective/Z observation requiring operator verification,
the completed short ND timing test, and the study checks that remain unperformed.
