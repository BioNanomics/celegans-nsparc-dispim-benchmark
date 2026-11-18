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

What it cannot do for this study (decide each gap with the lab manager before relying on the server):

| Limit | Consequence here |
|---|---|
| Objectives limited to 4x and 10x | The 60x embryo objective is changed by hand in NIS. |
| ND runs over 30 min refused | `Celegans_02` (60 min), `Celegans_03` and `Celegans_04` (450 min) are started from NIS. |
| Optical configuration selection is not validated for this study | Select `Celegans_BV514_NSPARC_pilot` in NIS before any capture or run. The development server offers selection, but this validation did not exercise it. |
| No Z range setting; `focus_down` only lowers | Z Reset / Top / Bottom are still set by hand on the embryo every run. |

Before the run:

- [ ] `MCPServer` job running in NIS; `echo` answers.
- [ ] `status`: XY, Z, objective and e-stop state match what you see at the scope. Re-check with `status` rather than trusting an earlier reading; a person can move the stage at any time.
- [ ] `list_experiments`: the template for this arm exists and its interval, duration, frames and Z steps match the plan. Record any mismatch.
- [ ] Know how to stop: `estop` with `engage`, NIS's **Finish** button for a running ND run (`finish_experiment` cannot interrupt a run in progress), and the microscope's physical controls. Never press JOBS **Abort**.

During the run:

- [ ] `run_experiment` returns only when the run ends; `status` meanwhile reports the server's own record (start, expected end, elapsed time), not a live NIS reading.

After the run:

- [ ] Note in the notebook that the MCP server was used and the time range of its log, `~/nis-mcp/log.jsonl` (every call, refusals included).
- [ ] `capture` saves single images to `~/nis-mcp/captures`, outside the study storage; they are checks, not study data. Study ND2 files follow the normal checksum and storage steps above.
- [ ] Only a person releases the e-stop, by deleting `~/.nis-mcp/ESTOP`.

See the [18 November MCP validation record](MCP_VALIDATION.md) for the completed
software checks, the objective/Z observation requiring operator verification,
the completed short ND timing test, and the study checks that remain unperformed.
