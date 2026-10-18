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
