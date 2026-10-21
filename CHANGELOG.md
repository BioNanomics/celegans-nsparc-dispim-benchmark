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
- `report` writes `run_info.json`: tool version, git commit, settings, SHA-256 of each input CSV and the warnings raised. Input folder paths are not recorded.
- CI now runs on Windows as well as Ubuntu.

### Changed
- Data dictionary updated for the depth-region rules.
- `depth_region` values other than `all`, `near` and `far` are rejected.

### Compatibility
- Data using only `depth_region = all` produces the same results as 0.1.0.
