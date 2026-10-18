# Data dictionary and storage

Copy the header-only CSVs under `data/templates` into a run-specific **private** directory. Every row must reference an `embryo_id` present in `acquisitions.csv`. Avoid patient identifiers; no human data are required. All time values are in minutes relative to an explicitly recorded stage/time anchor; document anchor and timebase in notes.

## `acquisitions.csv`: one row per attempted embryo

| Field | Definition |
|---|---|
| `embryo_id` | Unique, stable, deidentified identifier |
| `group` | `NSPARC_60s`, `NSPARC_180s`, `CONTROL` |
| `strain`, `reporter` | Genetic background and nuclear fluorophore |
| `batch_id`, `mount_id`, `operator` | Balanced blocking and operator provenance |
| `temperature_c`, `start_stage` | Measured specimen environment and start cell stage |
| `objective`, `objective_na`, `immersion` | Optical context |
| `excitation_nm`, `power_at_sample_mw`, `laser_power_percent` | Record absolute calibrated power when available; % is not dosage |
| `nsparc_mode`, `nis_elements_version` | Detector raw/processed and vendor software |
| `xy_um_per_px`, `z_um_per_plane`, `z_planes` | Sampling parameters |
| `planned_interval_s`, `measured_interval_s`, `recorded_volumes` | Planned vs achieved cadence and volume count |
| `raw_data_uri`, `raw_sha256`, `notes` | Protected storage pointer and provenance; never a shared secret |

## `embryo_outcomes.csv`: one row per embryo with attempted follow-up

- `embryo_id`, `hatched` (`1`, `0`, or blank for unknown), `hatch_t_min` (blank if unknown), `abnormal_development` (`1`, `0`, blank), `excluded` (`1`, `0`), `exclusion_reason`, `notes`.
- A `0` means *known not to have hatched within the specified follow-up window*, not unobserved. Include observation window in the notebook.

## `nuclei_qc.csv`: one row per independently reviewed 3D volume

- `embryo_id`, `volume_index` (0-based), `t_min` (stage-aligned), `manual_cell_count`, `tp`, `fp`, `fn`, `depth_region` (`all`, `near`, `far`, or another documented code).
- In each frame, **TP** = paired true nucleus detections, **FP** = automated detections with no matched nucleus, **FN** = manually verified nuclei missed. If `depth_region` is `near`/`far`, those are partitions and should not be combined with a duplicate `all` row for the same frame in pooled calculations. For the starter CLI, use one **`all`** row per `embryo_id,volume_index`. It rejects duplicate frame entries to prevent double counting.

## `lineage_qc.csv`: one row per manually audited division edge

- `embryo_id`, `event_id`, `t_min`, `stage_cell_count`, `verified` (`1`/`0`), `correct` (`1`/`0` if verified; blank otherwise).
- Two daughter edges from one division count as two independently evaluated links **only if predeclared**; record distinct `event_id` per evaluated edge. Otherwise use one event per full division and define correct as both assignments correct. Choose one unit and maintain consistently.

## `milestones.csv`: one row per observed developmental event

- `embryo_id`, `milestone`, `t_min`, `notes` (e.g., canonical division, twofold, hatch). Define clock anchor and event criteria up front.

## Storage policy

Raw `.nd2`, TIFF, OME-TIFF, large label volumes and processed result datasets go to backed-up lab storage or a data repository with appropriate access controls. Git stores metadata schemas, code, references, small deidentified human-reviewed tables if approved, and no copyrighted journal PDFs. The `.gitignore` deliberately excludes the large imaging formats, raw folders and generated results. For publicly released reproducibility data, use DOI-versioned datasets with hashes and license checks.
