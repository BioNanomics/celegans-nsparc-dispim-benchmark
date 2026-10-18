# Reproducibility and interoperability plan

## Data lineage

1. Register the **original raw ND2 acquisition** (read-only file path/URI and SHA-256) and acquisition settings.
2. Export reproducible TIFF/OME-TIFF copies where needed, recording conversion software version and channel axes. Do not silently overwrite originals.
3. Preserve separate segmentation masks/nucleus centroids, tracker lineage links, manually corrected traces, and instrument-level reconstructions.
4. Create stage-stratified manual ground truth independent of automated processing where possible.
5. Feed curated per-volume TP/FP/FN and per-lineage event decisions into this repository's `nuclei_qc.csv` and `lineage_qc.csv`.
6. Generate summary and figures from committed code; preserve package/environment lockfile when implementation stabilizes.

## Practical software choices

- Nikon NIS-Elements: acquisition and export; confirm available NSPARC modes with installed release.
- [StarryNite](https://github.com/zhirongbaolab/StarryNite): existing automated segmentation and lineage tracing, subject to format/parameter validation.
- [AceTree](https://github.com/zhirongbaolab/AceTree): manual auditing and lineage correction.
- [LIVEtools](https://github.com/johnmurraylab/LIVE_tools): multi-embryo lineage analysis, accepts CD CSV with `time,cell,x,y,z,blot`.
- [EmbAlign](https://github.com/shahlab-ucla/EmbAlign): independent lineage identity assignment to validated nuclear centroids; not part of the installed starter CLI.
- [WormGUIDES Atlas](https://wormguides.org/wormguides-atlas/): stage/lineage reference; honor time alignment and embryo geometry.

## Methodological safeguards

- Optical reconstruction may change segmentation precision without changing biological ground truth; audit raw and processed variants using the same manually verified nuclei.
- Report TP/FP/FN stage by stage and group by group; report embryo-level distributions to avoid pseudoreplication.
- Analyze lineage accuracy, nucleus detection and cell-identity assignment separately.
- Image-data public release requires permission, licensed redistribution rights and appropriate provenance. Never ship original microscopy data inside a Git repository simply for convenience.
- Use a fixed list of evaluation frames determined **before** viewing results to avoid cherry-picking.
