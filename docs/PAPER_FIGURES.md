# Figures and next research decisions

Updated 18 November 2026. The manuscript combines a planned embryo study with
completed, non-study imaging rehearsals. The AML18 annotation kit is prepared;
manual labels and tracking results are still pending.

## Figures to include now

| Figure | Scientific question | Evidence and interpretation |
|---|---|---|
| 1: 10-minute AML18 field | Is there usable image information for a small 2D spot-correspondence case study? | Full-field GFP/RFP/TD at 0, 5 and 10 minutes. This is a qualitatively selected candidate, without target identities or tracking overlays. |
| 2: overnight image series | How does the recorded image appearance change early in the long run? | Full-field TD/GFP at 0, 15, 60 and 180 minutes from the 15-hour CF recording. Fixed per-channel display ranges reveal loss of contrast/detail without establishing its cause. |
| 3: overnight quality curves | How large is the change in the recorded quality proxies, and when is it observed? | The existing 185-frame sample, normalized to the first-five-frame mean. Early and full-duration panels show the same recording, not independent replicates. |

The two image figures use metadata-derived 100 micrometre scale bars and retain
the full recorded field. Display limits are the first frame's 1st/99.8th
percentiles, fixed separately for each channel across time. Channels and recording
modes are not matched intensity comparisons. The QC curves use recorded data,
not a fitted decay model or a measure of survival.

The eight-hour stack montage remains supporting material. Its coarse maximum
projections do not demonstrate the crowded nuclear resolution or depth coverage
required for the planned embryo study. A viewer screenshot can illustrate the
software in a presentation, but the manuscript figures should show the actual
image evidence and measurements.

## Source and figure reproducibility

The manuscript's figure environments and full captions are in
[paper/main.tex](paper/main.tex). Figure PNGs and the generation provenance are in
[figures/paper_2026-11-18/](figures/paper_2026-11-18/).

`scripts/make_paper_figures.py` regenerates the figures from the original saved
ND2 files and the existing portable overnight sample table. Use a new output
folder to preserve this snapshot. Raw ND2 files stay outside Git; the figure PNGs
are covered by the existing Git LFS rule for `docs/figures/`.

## Update Overleaf

1. Replace the Overleaf `main.tex` with the reviewed repository source.
2. Create a folder named `figures` in the Overleaf project and upload
   `fig1_aml18_candidate.png`, `fig2_overnight_images.png` and
   `fig3_overnight_qc.png` into it.
3. Recompile and check all three figures, their captions and references.
4. Mirror the source and assets before merging: the nightly sync treats Overleaf
   as the manuscript source. Local GitHub builds find the PNGs in
   `docs/figures/paper_2026-11-18/` through the second graphics search path.

The locally built review PDF and an Overleaf upload ZIP are generated artifacts
under `results/paper_figure_review/output/`; they are excluded from Git. The
tracked `docs/manuscript.pdf` is left for the existing build workflow.

## What should become the next results figure?

First review frames 0-9 of the 10-minute movie with temporary selected-spot IDs.
Use this small development subset to check whether the annotation rules are
practical. Then complete the frozen 151-frame design, with the prescribed
secondary review and an explicit record of uncertain/non-visible intervals.
Do not replace hard evaluation frames with clearer ones.

The next results figure should combine reviewed image examples with selected-spot
visibility coverage, localization errors in micrometres and correspondence
failures over evaluable transitions. Lock the matching rule and tracker settings
using development data before evaluating the later temporal block. Show gaps and
uncertainty rather than joining them into an invented trajectory.

A small, selected set of annotated spots cannot establish whole-field detector
precision/recall or the total number of neurons. Those outcomes would require
exhaustive reference annotation in explicitly defined frames/regions and a
matching rule. Keep the present claim to selected-target correspondence, and
report its denominators and selection limits.

Before another long acquisition, validate a short focus-stability experiment on
the actual mount. The current overnight images and quality curves identify a
problem to investigate; they do not establish drying, bleaching, optical drift
or death as its cause. The whole-embryo lineage project remains a separate stage
requiring the appropriate reporter, XYZ coverage, validated cadence and controls.
