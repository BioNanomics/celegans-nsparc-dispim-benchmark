# AML18 1111: manual annotation kit, version 1

**Status: prepared, not annotated.** `annotations.csv` starts with a header
only, and all 151 rows in `frame_review.csv` start `not_reviewed`. No tracked
neuron identities, manual ground truth or algorithm scores are implied.

The source is `Celegans_01_stack_timing1111.nd2`, with GFP/RFP/TD channels,
151 single-plane time points and calibrated 1024 by 1024 source coordinates.
The raw file stays at its location in the
[checksum manifest](../../manifests/nd2_sha256_2026-11-17.csv).

- `plan.json` freezes the source hash, native elapsed timestamps, temporal
  development/buffer/evaluation blocks, secondary-review list, prior-viewing
  disclosure and fixed display transform. Its canonical digest is recorded in
  the annotation and frame-review tables.
- `annotations.csv` contains one row per actual reviewer/target/frame decision,
  when those decisions are made. Temporary spot IDs are not biological names.
- `frame_review.csv` records whole-frame review separately from target
  visibility. Initial placeholder rows are not positive or negative detections.
- `session_provenance.json` identifies the exporter and the freshly verified
  source. The initial counts describe kit creation, not future annotation work.

Follow the [annotation protocol](../../../docs/SPOT_ANNOTATION_PROTOCOL.md).
Use a separate primary/secondary reviewer identity, preserve original exports,
and reconcile disagreements separately. The second reviewer must work without
viewing the first reviewer's labels, for example using a separate browser
profile and their own exports. Changing the reviewer ID alone does not make a
previously viewed label independent.

## Prepare the local viewer

The prepared session on this PC is in
`results/aml18_annotation_session_v1_ready` (generated assets, excluded from Git).
While its local server is running, open <http://127.0.0.1:8791/>. To restart it
from the repository root without rebuilding the images:

```powershell
.\.venv\Scripts\python.exe -m http.server 8791 --bind 127.0.0.1 --directory results/aml18_annotation_session_v1_ready
```

For the first review, enter reviewer `R1`, select a distinguishable GFP spot in
the development frames, and assign a temporary ID such as `S01`. Record the
annotation, then explicitly mark the frame reviewed and advance. Use uncertain
or not visible with a reason when correspondence is unclear. Export both CSVs.

Use the optional annotation dependencies (`python -m pip install -e ".[annotation]"`)
if needed. From the repository root:

```powershell
python scripts/prepare_spot_annotation.py --nd2 'D:\Qurratul_Celegans\TimelapsePath\Celegans_01_stack_timing1111.nd2' --manifest data/manifests/nd2_sha256_2026-11-17.csv --out results/aml18_annotation_session_new
```

The exporter refuses an existing output directory, checks the full source
SHA-256 against the baseline, and creates all 151 time points with three
lossless PNG display planes each. Source coordinates are retained without
resizing. The saved ND2 contains Live Deconvolution data; display images are
fixed, linear first-frame contrast mappings to 8 bits, not raw photon values.
Check the generated plan digest against this frozen plan before combining
labels from independently prepared sessions.

Serve only the generated session folder on loopback, keeping the original
ND2 and unrelated folders outside the server's document root:

```powershell
python -m http.server 8791 --bind 127.0.0.1 --directory results/aml18_annotation_session_new
```

Open `http://127.0.0.1:8791/`. Images load on demand with a bounded browser cache.
Use GFP for centroid marks and RFP/TD for context. A marker is saved only after
the annotation action; marking a frame reviewed is a separate decision.

Export annotation and frame-review CSVs during and after a session. A browser
draft is not a committed repository file or a substitute for an exported backup.
Verify source/plan hashes before replacing these blank tables with reviewed
exports. The viewer does not send labels to an external service or operate NIS.
