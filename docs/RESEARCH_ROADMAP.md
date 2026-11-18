# Research roadmap

Updated 18 November 2026. This roadmap separates work possible with the available AML18 recordings from the future whole-embryo lineage benchmark. It does not change the existing biological protocol, analysis thresholds or microscope presets.

## Current position

MCP connection, capture and short time-lapse tests have been documented. The existing 17-file recording collection has now received a metadata and sampled-image review; see [the data review](DATA_REVIEW_2026-11-18.md). Those recordings contain useful rehearsals and image-quality problems, but no completed BV514 embryo pilot or validated embryonic lineage result.

**The immediate research question is:** in the best existing AML18 movie, how consistently can a reviewer and a simple tracking method locate the same visible fluorescent structures in two dimensions, and when does their identity become uncertain or unobservable?

A moving fluorescent spot is not automatically an identified neuron. A single-plane movie cannot establish a complete three-dimensional cell population, embryonic nuclear divisions, hatching or organism viability.

## Phase 1: make one existing movie auditable

Start with `Celegans_01_stack_timing1111.nd2`: 151 frames over 10 minutes, one plane, GFP/RFP/TD, 4 s recorded intervals. The data review's montage supports choosing it for annotation; the full movie still needs review.

1. Verify the raw filename, saved mode, axes, pixel size and checksum reference. Preserve the original ND2; export only derived working copies with recorded software/channel mapping.
2. Review every frame using consistent display ranges and the paired TD view. Log overlap, target exit, defocus, weak signal and other uncertain periods. Give each annotation a visibility state rather than interpolating silently.
3. Define what is being measured before tracking: a 2D worm outline/centroid, or a small set of fluorescent spot centroids. Do not mix those units or treat body motion as neuronal activity.
4. Write a short annotation rule for spot splitting/merging, ambiguous matches, out-of-plane loss and reappearance. Allow `uncertain` and `not_visible`. Do not assign biological neuron names without independent identification evidence.
5. Freeze a held-out evaluation frame list, including easy and difficult intervals, **before** tuning. Set matching tolerances in calibrated micrometres. A second reviewer should independently check a subset and record disagreements.

**Deliverable:** a portable annotation table, frame-selection record, annotation rules and a small reviewed image panel. State the number of targets, evaluable frames, uncertain frames and reasons. These are observational annotations, not embryonic ground truth.

## Phase 2: evaluate a small tracking baseline

Choose one segmentation/spot-linking method and record its version and exact parameters. Use development frames for parameter tuning and the frozen held-out frames for evaluation; keep the two sets distinct. Do not add several methods before a simple baseline can be audited.

Report separately:

- Detection precision and recall on evaluable annotated frames, including the matching rule and denominator.
- Localization error in micrometres for matched spots.
- Identity switches and track breaks over manually reviewed transitions, with explicit denominators.
- Visibility/evaluable-frame coverage and durations lost to ambiguity or depth, rather than a score restricted to easy visible frames.

A correct detection is not proof of a correct cross-frame link. Abstaining on an ambiguous match is preferable to inventing continuity. One selected movie and its many frames are not independent biological replicates, and choosing this best movie does not characterize the entire collection. Report it as a bounded feasibility case study. Test a locked method on another recording before making a broader generalization.

**Decision:** if repeatable annotations and a defensible baseline are possible, this becomes an AML18 tracking-feasibility result. If visibility prevents evaluation, the useful finding is the failure condition and the acquisition requirement it exposes.

## Phase 3: fix the acquisition question before an overnight run

The 15-hour movie already shows that recording many frames is insufficient. Its sampled TD sharpness is about half the initial baseline by 15 minutes, with PFS recorded off/out of range. The cause has not been isolated.

On a fresh specimen, use a short, supervised pilot to evaluate mounting, focus stability and visibility at the intended settings. Record temperature, objective/medium, acquisition mode, illumination settings, measured power at the sample when available, Z coverage, actual scan duration and any focus corrections. Use a specimen-appropriate approved mounting method; do not equate a sealed coverslip or an unchanged objective coordinate with maintained specimen focus.

Change one acquisition factor at a time where feasible. Include a comparable minimally illuminated reference when testing whether repeated excitation alters the specimen, and distinguish that biological question from optical focus drift. Keep the whole field and the selected target's review separate. Do not infer harm from a foreground-mask decline or assume that increasing pixel count corrects defocus.

**Deliverable:** a short movie whose image-quality and visibility measures stay interpretable, together with a measured scan/stack cycle and a record of corrections. Prespecify acceptable visibility, drift and cadence for the intended analysis before a longer run. If these do not hold, retain the failure and revise the acquisition recipe; do not relabel it as an overnight tracking success.

## Phase 4: the future embryo benchmark

Proceed only when a suitable **ubiquitous nuclear reporter** and early embryos are available. The current AML18 neuronal reporter is not a substitute. The [protocol](PROTOCOL.md) targets BV514 `ujIs113` mCherry-histone; any substitution requires verifying expression, fluorophore, developmental suitability and a documented protocol decision.

Before the biological pilot:

- Verify the objective, sampling and full embryo XYZ coverage on the actual mount. Set Z limits on each embryo and measure the complete stack cycle, including final exposure and return, at the final settings. The old 10x rehearsal is not a measurement of the proposed 60x recipe.
- Confirm that the measured cycle fits the arm's interval with a defined overhead margin. The latest single-plane RFP timing of 1.688 s implies about 69 s for 41 planes even before Z motion; this estimate is not a completed stack test. Do not reduce coverage silently to fit 60 s.
- Fix mounting/environment, a common developmental time anchor, the transmitted-light follow-up schedule, stopping rules, hatching observation window, manual audit policy and software provenance.
- Keep optimization runs separate from the cohort used to evaluate a frozen recipe. Prespecify any changes rather than choosing thresholds after seeing outcomes.

Then run the planned feasibility arms: 60 s volumes, 180 s volumes and contemporaneous controls without repeated fluorescence. Start with about three embryos per arm, blocked/randomized across preparation days, and retain all attempts and exclusions. Expand only after reviewing feasibility and the precision required for the next claim. The embryo is the independent biological unit; small cohorts do not establish absence of phototoxicity or equivalence to diSPIM.

Assess developmental timing and hatching against the matched controls, reporting unknown follow-up separately. Audit nuclear detection, parent-daughter links and identity assignment as different outcomes. Published diSPIM remains a contextual benchmark unless matched specimens, raw data and a comparable evaluation are obtained. These decisions belong in the [analysis plan](ANALYSIS_PLAN.md), not only in a script.

A useful later comparison is to subsample every third volume of a 60 s movie to study the effect of temporal sampling on tracking. This holds that acquisition fixed; it does **not** replace the true 180 s imaging arm when studying illumination and development.

## Manuscript and repository decisions

The paper should label existing observations as non-study rehearsals and keep embryo results pending. Use association language for signal/movement changes and describe focus-loss causes as hypotheses until controlled measurements separate them. Preserve acquisition mode and sampling differences; saved CF, SR and Live Deconvolution recordings are not interchangeable.

Raw ND2 files stay outside Git with a storage pointer and checksum. Keep derived metadata, annotations, figure provenance and analysis code portable and linked. Record software/parameters before analyses, and preserve every attempted acquisition rather than only the clearest field.

**Overleaf coordination:** the manuscript source is synchronized from Overleaf. Any branch-local changes to `docs/paper/main.tex` must be mirrored to the authoritative Overleaf source **before merge**, otherwise a later sync can overwrite them. This roadmap does not itself mirror or publish manuscript changes.

## Immediate work item

Complete the 151-frame AML18 manual visibility/spot annotation, freeze a held-out frame list and review one tracking baseline. Use that result to decide the next acquisition requirement. Keep the embryo benchmark as a separate, explicitly gated stage.
