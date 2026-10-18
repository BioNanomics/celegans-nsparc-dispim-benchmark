# Published baselines and data sources

## Primary experimental benchmark — Duncan et al. (2019)

**Citation:** Duncan LH, Moyle MW, Shao L, et al. *Isotropic Light-Sheet Microscopy and Automated Cell Lineage Analyses to Catalogue Caenorhabditis elegans Embryogenesis with Subcellular Resolution.* J Vis Exp. 2019;148:e59533. DOI: [10.3791/59533](https://doi.org/10.3791/59533). [Full text at PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7255390/) | [JoVE](https://www.jove.com/t/59533/isotropic-light-sheet-microscopy-automated-cell-lineage-analyses-to).

**Directly reported:**

- 10 embryos, *strain* **BV514** carrying **`ujIs113`** ubiquitous mCherry-histone reporter.
- At **20°C**, from 2-cell to 2-fold stage, **1 3D volume per embryo per minute**.
- **7.5 hours**, **451 volumes/embryo** (including acquisition endpoints).
- No detectable phototoxicity under the documented conditions, as assessed by developmental timing and hatching.
- Dual-view registration and fusion (~330 nm isotropic spatial resolution under described conditions).

**Comparison use:** primary benchmark for target acquisition cadence, duration and stage coverage, and qualitative developmental viability. The paper is *not* a statistically controlled head-to-head measurement against Nikon NSPARC. The 451-point time series and cross-modality detection accuracy are not provided as directly comparable numerical benchmarks in the main paper; **do not invent a curve**.

## Downloadable computational benchmark — EmbAlign (2026)

**Citation:** Tran MP, Peinado N, Zhao Z, Shah PK. *Inference of Lineage-Resolved Cell Identities in Uncompressed C. elegans Embryos.* microPublication Biology. 2026. [Paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13242636/), [repository](https://github.com/shahlab-ucla/EmbAlign), [archived dataset](https://doi.org/10.5281/zenodo.20089241).

- Public code and processed data for lineage-resolved 3D nuclear coordinates in uncompressed embryos.
- An alignment method that assigns cell identities to nuclei using spatial and developmental reference data; paper reports ~96.9% within its reported evaluation through 190 cells.
- Their **JIM113** validation embryos were collected on **single-view** ASI diSPIM, so do **not** conflate these with Duncan's **BV514 dual-view** acquisition or 96.9% with detector segmentation performance.
- Downstream option: align curated NSPARC nuclear coordinate CSVs to templates after validating segmentation, orientation, and stage. Note the pipeline is sensitive to missing/extra nuclei.

Processed data are *not* necessarily raw microscopy volumes. Fetch only from verified upstream repositories/archives and respect source attribution and licenses. This scaffold **does not bundle upstream data**.

## Other references

- [WormGUIDES Atlas](https://wormguides.org/wormguides-atlas/) — 4D lineage/spatial references; carefully match time coordinate and embryo orientation.
- [StarryNite](https://github.com/zhirongbaolab/StarryNite) — nucleus detection/lineaging toolkit, with acquisition-specific parameters.
- [AceTree](https://github.com/zhirongbaolab/AceTree) — human lineage review and correction.
- [LIVEtools](https://github.com/johnmurraylab/LIVE_tools) — downstream lineage comparison and visualization.
- [WormGUIDES diSPIM overview](https://wormguides.org/dispim/) — different multi-hour fast-imaging demonstrations; avoid mixing original iSPIM/diSPIM reports with the 2019 ten-embryo benchmark.

## What to request before claiming "matches diSPIM"

1. Access to archived comparable raw data (if available) or matched specimens to run on a diSPIM.
2. Same or calibrated strain/reporter, developmental stage and embryo mounting/compression.
3. A comparison pipeline with independently manually reviewed truth sets and blinding.
4. Equivalent criteria for phototoxicity and hatching follow-up.
5. Explicit timing normalization and volume interval/photodose measured, not assumed.

Without these, report **"consistent with the published biological benchmark"** rather than **"NSPARC equals diSPIM"**.
