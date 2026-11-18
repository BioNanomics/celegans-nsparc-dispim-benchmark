# Acquired-data review snapshot: 18 November 2026

This is a derived, reviewable snapshot of 17 existing recordings, not new
experimental data or a complete integrity scan. The raw ND2 files remain at the
locations in [the prior manifest](../../manifests/nd2_sha256_2026-11-17.csv).

- `inventory.csv`: one row per ND2 file; dimensions, saved processing mode,
  recorded timing, sampled-image coverage, baseline checksum and review limits.
- `overnight_samples.csv`: 185 selected time points from
  `Celegans_01_stack_overnightslip-1112.nd2`, not all 5,401 frames. Samples include
  the first five frames, five-minute checkpoints and the last frame. Previews
  use a subset of these same checkpoints.
- `provenance.json`: generating script hash, dependency versions, source-manifest
  hash, figure/data hashes, baseline definitions and limits.

`prior_raw_sha256` is copied from the November 17 manifest. It was **not**
recomputed by this review. A matching byte size and unchanged modification time
do not constitute fresh SHA-256 verification.

Recorded ND2 timestamps share the native acquisition-time cache; they are not
two independently calibrated clocks. `median_plane_start_span_s` excludes the
last exposure and return overhead. Device-event Z ranges for stack recordings
include intentional scanning and must not be interpreted as focus drift.

The overnight fluorescence proxy is p99.9 minus median. The TD sharpness proxy
is four-neighbour Laplacian variance divided by squared mean intensity. Both
are normalized to the mean of the first five frames. These whole-field image
measures do not isolate bleaching, establish organism death or identify the
cause of blur. No nucleus, neuron or lineage annotations are supplied.

## Reproduce the offline calculations

Use the project's optional `nd2` and `plots` dependencies. From the repository
root, substituting the raw-storage location and a **new** output directory:

```powershell
python scripts/review_acquired_data.py --raw-root 'D:\Qurratul_Celegans\TimelapsePath' --manifest data/manifests/nd2_sha256_2026-11-17.csv --out results/review_new --overnight Celegans_01_stack_overnightslip-1112.nd2
```

The script refuses an existing output directory. It reads local ND2 files and
does not connect to NIS or command microscope hardware. Detailed local outputs
under `results/` remain ignored by Git. This curated snapshot retains filenames
and measured values without new machine-specific absolute paths.

See the [data review](../../../docs/DATA_REVIEW_2026-11-18.md) for interpretation
and the [research roadmap](../../../docs/RESEARCH_ROADMAP.md) for next steps.
