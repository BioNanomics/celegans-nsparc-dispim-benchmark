# Changelog

All notable changes to the analysis scaffold. Versions follow semantic versioning.
Results are always descriptive; no entry here implies biological findings.

## [0.2.0] - 2026-10-21

### Added
- Report: `lineage_stage_qc` (verified and correct lineage links per group and nuclei-count stage).
- Report: provisional feasibility gates (`feasibility_gates`, `feasibility_gates_by_embryo`) for detection recall through 100 cells and verified-link correctness. Thresholds are settings (`--recall-threshold`, `--lineage-threshold`, `--recall-through-cells`). No data gives `not_evaluable`, never `fail`.
- Near/far depth regions in `nuclei_qc` (key is now embryo + volume + depth_region); a frame is one `all` row or a `near` + `far` pair, never both. Frames are counted once and staged by their total cell count. New `depth_qc` report table.
- `init-run` command to create a run folder from the templates without overwriting existing CSVs (cross-platform replacement for `scripts/init_run.sh`).
- `checksum` (chunked SHA-256) and `verify-raw` (compare `raw_sha256` with the file at `raw_data_uri`) commands.
- Warnings (stderr, exit code unchanged) for blank `power_at_sample_mw`, `raw_sha256` or `nsparc_mode` on imaged embryos, and for a measured interval slower than planned beyond `--interval-tolerance` (default 5%).
- `--version` flag.
- `select-frames` command: chooses audit frames per stage in advance from a `time_point,spots` file with a fixed seed, writes the list (never overwritten) and prints its SHA-256 so the choice can be shown to precede the audit.
- `check-audit` command: compares tp+fp of each audited frame of one embryo with the tracker's spot count for that frame (near+far summed). Mismatches exit 1; frames without a known count are `not_checkable`, not failures.
- `report` writes `run_info.json`: tool version, git commit, settings, SHA-256 of each input CSV and the warnings raised. Input folder paths are not recorded.
- `report` writes `summary.md`, a one-page readable summary (groups, hatching with unknowns shown separately, feasibility gates, stage tables, per-embryo table, warnings). `--label` adds a data-label banner; example data in a `synthetic` folder is labeled FABRICATED automatically.
- Scale test (`tests/test_scale.py`): runs the full pipeline on a seeded, FABRICATED study-sized dataset (30 embryos, up to 451 volumes, mixed `all` and near/far frames) and checks the report against independent recomputation from the CSVs.
- CI now runs on Windows as well as Ubuntu.

### Changed
- Data dictionary updated for the depth-region rules.
- `depth_region` values other than `all`, `near` and `far` are rejected.

### Compatibility
- Data using only `depth_region = all` produces the same results as 0.1.0.
