# C. elegans NSPARC–diSPIM Benchmark

**BioNanomics | Experimental protocol and reproducible analysis scaffold**  
**Status:** Proposed / not yet executed. No biological data or validation results are included.

## Research question

Can a Nikon Ti2/AX confocal microscope equipped with **NSPARC** provide sufficiently accurate, low-phototoxicity 4D tracking of *Caenorhabditis elegans* embryonic nuclei to reproduce useful aspects of published **dual-view inverted selective-plane illumination microscopy (diSPIM)** cell-lineage experiments?

NSPARC's 25-element detector improves photon collection and image-scanning microscopy reconstruction; it **does not** change confocal illumination into a light sheet. This project tests *biological fitness for purpose*, not whether the instruments are optically equivalent.

## Published target

Duncan et al. (2019, [DOI:10.3791/59533](https://doi.org/10.3791/59533)) acquired 10 **BV514** `ujIs113` embryos with ubiquitous mCherry-histone nuclear labeling, at **20 °C**, **one 3D volume per embryo per minute**, over **7.5 hours** (**451 volumes**). They assessed developmental timing and embryo viability, finding no detectable phototoxicity under their reported conditions.

That study is a **published observational benchmark**, not matched raw data collected on our microscope. Any direct instrument-level claim requires a head-to-head experiment with comparable embryos, reporters, sampling, optical objectives, mounting, and analysis pipelines.

## Study outline

| Condition | Imaging | Goal |
|---|---|---|
| **NSPARC_60s** | Whole-embryo nuclear Z stack every 60 s | Match published temporal cadence |
| **NSPARC_180s** | Whole-embryo nuclear Z stack every 180 s | Lower-dose control; test tracking trade-off |
| **CONTROL** | Same strain, mount and temperature, without repeated fluorescence excitation | Establish baseline development and viability |

Start with a **3-embryo-per-arm feasibility pilot** (short acquisition, then full-duration verification). Expand to approximately **10 embryos per arm** to characterize variation. This is **not powered to demonstrate equivalence or safety**; see [analysis plan](docs/ANALYSIS_PLAN.md). Randomize embryos across groups within imaging days and retain all attempted acquisitions, failures, and exclusions.

The study ends with an answer to: *How far into embryogenesis can NSPARC recover high-confidence nuclear identities and divisions at a useful temporal cadence without altering normal development?*

## What this repository contains

- [Brief for lab manager](docs/LAB_MANAGER_BRIEF.md)
- [Step-by-step experimental protocol](docs/PROTOCOL.md)
- [Published benchmarks and downloadable atlas resources](docs/BASELINES.md)
- [Analysis design and provisional feasibility gates](docs/ANALYSIS_PLAN.md)
- [Data dictionary and image storage plan](docs/DATA_DICTIONARY.md)
- [Acquisition-day checklist](docs/ACQUISITION_WORKSHEET.md)
- [Reproducibility and next integrations](docs/REPRODUCIBILITY.md)
- [Empty CSV templates](data/templates/)
- [`src/celegans_benchmark/`](src/celegans_benchmark/) — dependency-free CSV validation, descriptive metrics, and optional figures
- [`tests/`](tests/) and GitHub Actions CI

## Get started

1. Review the scientific protocol with the *C. elegans* lab manager; verify the available nuclear reporter strain and instrument capabilities.
2. Copy all `data/templates/*.csv` into a private run folder (or run `python -m celegans_benchmark init-run --run-dir <folder>`, which never overwrites existing CSVs), then fill in real acquisition and QC records. **Do not add identifying or unpublished image data to a public Git repository.**
3. Export/manual-curate nuclei into the documented CSV format. Raw Nikon `.nd2` images stay in controlled storage (not Git).
4. Run the analysis:

```bash
python -m pip install -e .
python -m celegans_benchmark validate --data-dir examples/synthetic
python -m celegans_benchmark report --data-dir examples/synthetic --output-dir results/demo
python -m unittest discover -s tests -v
```

The `examples/synthetic` directory is **fabricated demo data only**, clearly labeled; no published biological measurements are inferred from it. Optional figure output uses Matplotlib: `pip install -e '.[plots]'`, then append `--plot` to `report`.

### Other commands

```bash
# Create an empty run folder from the templates (refuses if it already contains CSVs)
python -m celegans_benchmark init-run --run-dir D:\private\run1

# SHA-256 of a large raw file (read in chunks); paste it into raw_sha256 in acquisitions.csv
python -m celegans_benchmark checksum --file D:\raw\embryo01.nd2

# Compare recorded checksums with the files (blank values are "not recorded", not failures)
python -m celegans_benchmark verify-raw --data-dir D:\private\run1 --raw-root D:\raw
```

`validate` and `report` print `WARNING` lines (exit code unchanged) when an imaged embryo has a blank `power_at_sample_mw`, `raw_sha256` or `nsparc_mode`, or when `measured_interval_s` is slower than `planned_interval_s` by more than `--interval-tolerance` (default 0.05 = 5%).

`report` also writes stage-resolved lineage accuracy (`lineage_stage_qc.csv`), near/far depth QC (`depth_qc.csv`) and the provisional feasibility gates (`feasibility_gates.csv`, `feasibility_gates_by_embryo.csv`). Gate status is `pass`, `fail` or `not_evaluable` (no data is never a failure). The provisional targets can be changed with `--recall-threshold` (0.95), `--lineage-threshold` (0.90) and `--recall-through-cells` (100).

## Success measures

The primary pilot readouts are **manually validated nuclear detection** (precision and recall by cell-count stage), **correct division parent–daughter links**, **hatching rate**, **developmental timing**, **volume acquisition cadence**, and **maximum validated lineage depth**. Proposed thresholds (95% detection recall through 100 cells, 90% correct verified links, no obvious group-specific viability/timing defects) are **internal feasibility targets**, not claimed diSPIM standards.

See [documented limitations](docs/ANALYSIS_PLAN.md) before interpreting differences as evidence of phototoxicity. The first comparison to published diSPIM is contextual, not a statistically controlled optical equivalence test.

## Scientific references

- Duncan LH et al. 2019. *Isotropic Light-Sheet Microscopy and Automated Cell Lineage Analyses to Catalogue C. elegans Embryogenesis with Subcellular Resolution.* [JoVE](https://www.jove.com/t/59533/isotropic-light-sheet-microscopy-automated-cell-lineage-analyses-to) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7255390/)
- Tran MP et al. 2026. *Inference of Lineage-Resolved Cell Identities in Uncompressed C. elegans Embryos.* [Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC13242636/) · [EmbAlign repository](https://github.com/shahlab-ucla/EmbAlign) · [dataset archive](https://doi.org/10.5281/zenodo.20089241)
- [StarryNite](https://github.com/zhirongbaolab/StarryNite), [AceTree](https://github.com/zhirongbaolab/AceTree), [LIVEtools](https://github.com/johnmurraylab/LIVE_tools), [WormGUIDES Atlas](https://wormguides.org/wormguides-atlas/)

## Project policy

No patient information, animal experimental raw data, proprietary instrument configuration, or unpublished results should be committed without lab review. **A public license has not yet been selected.** See [LICENSE-DECISION.md](LICENSE-DECISION.md) before public reuse or release.
