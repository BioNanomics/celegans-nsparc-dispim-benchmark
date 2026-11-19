"""Reproduce three manuscript figures from existing ND2 files and sampled QC.

No NIS connection is made. Only selected source frames are read. The raw SHA-256
values in provenance are prior baselines, not fresh whole-file verifications.
Existing output directories are refused so reviewed figures are not overwritten.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from mpl_toolkits.axes_grid1.anchored_artists import AnchoredSizeBar
import nd2
import numpy as np
from PIL import Image


REPO = Path(__file__).resolve().parents[1]
CANDIDATE = "Celegans_01_stack_timing1111.nd2"
OVERNIGHT = "Celegans_01_stack_overnightslip-1112.nd2"
CHANNELS = ("GFP", "RFP", "TD")
QC_METRICS = (
    ("GFP_p99_9_minus_median_relative_first5", "GFP contrast", "#247a43", "-"),
    ("RFP_p99_9_minus_median_relative_first5", "RFP contrast", "#a74b21", "--"),
    ("TD_normalized_laplacian_variance_relative_first5", "TD sharpness", "#244f8d", "-."),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def one_row(rows: list[dict[str, str]], column: str, name: str) -> dict[str, str]:
    matches = [row for row in rows if row[column] == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one {column}={name} record, found {len(matches)}")
    return matches[0]


def read_source(path: Path, expected_t: int, inventory: dict[str, str],
                baseline: dict[str, str], indices: list[int] | None = None,
                target_minutes: list[int] | None = None) -> tuple[dict, dict, dict]:
    before = signature(path)
    if before[0] != int(baseline["size_bytes"]) or before[0] != int(inventory["size_bytes"]):
        raise ValueError(f"Source byte size differs from its baseline: {path.name}")
    if baseline["raw_sha256"].lower() != inventory["prior_raw_sha256"].lower():
        raise ValueError(f"Inventory and prior manifest disagree: {path.name}")
    with nd2.ND2File(path) as reader:
        if dict(reader.sizes) != {"T": expected_t, "C": 3, "Y": 1024, "X": 1024}:
            raise ValueError(f"Unexpected axes/shape for {path.name}: {dict(reader.sizes)}")
        names = [channel.channel.name for channel in reader.metadata.channels]
        if names != list(CHANNELS):
            raise ValueError(f"Expected GFP/RFP/TD in stored order: {path.name}")
        native_indices = {}
        for seq_index, coordinates in enumerate(reader.loop_indices):
            t = coordinates.get("T", 0)
            if t in native_indices:
                raise ValueError(f"Multiple sequence planes at T={t}: {path.name}")
            native_indices[t] = seq_index
        if sorted(native_indices) != list(range(expected_t)):
            raise ValueError(f"Missing native time indices: {path.name}")
        times = np.array([
            reader.frame_metadata(native_indices[t]).channels[0].time.relativeTimeMs / 1000
            for t in range(expected_t)
        ], dtype=np.float64)
        if not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
            raise ValueError(f"Invalid recorded timebase: {path.name}")
        elapsed = times - times[0]
        if target_minutes is not None:
            indices = [int(np.argmin(np.abs(elapsed / 60 - minute))) for minute in target_minutes]
        if not indices or len(set(indices)) != len(indices):
            raise ValueError("Selected native frames must be distinct")
        voxel = reader.voxel_size()
        pixel = float(voxel.x)
        if not np.isfinite(pixel) or pixel <= 0 or not np.isclose(pixel, voxel.y):
            raise ValueError(f"Expected calibrated isotropic XY pixels: {path.name}")
        # The LUT is fixed once, from the original first frame of this movie.
        first = np.asarray(reader.read_frame(native_indices[0])).copy()
        ranges = {}
        for c, name in enumerate(CHANNELS):
            lo, hi = map(float, np.percentile(first[c], [1, 99.8]))
            if not hi > lo:
                raise ValueError(f"Degenerate first-frame LUT for {path.name}/{name}")
            ranges[name] = {"display_lo": lo, "display_hi": hi}
        frames = {
            t: first if t == 0 else np.asarray(reader.read_frame(native_indices[t])).copy()
            for t in indices
        }
        capturing = reader.text_info.get("capturing", "")
        match = re.search(r"NSPARC Mode:[ \t]*([^\r\n]+)", capturing)
        mic = reader.metadata.channels[0].microscope
        info = {
            "source_name": path.name,
            "source_bytes": before[0],
            "source_mtime_ns_before": before[1],
            "baseline_raw_sha256": baseline["raw_sha256"].lower(),
            "raw_sha256_freshly_verified": False,
            "raw_sha256_note": "Copied from the recorded November 17 baseline; raw bytes not rehashed by this producer",
            "native_shape": dict(reader.sizes),
            "channels": names,
            "pixel_um": pixel,
            "scale_bar_um": 100,
            "scale_bar_native_pixels": 100 / pixel,
            "objective": mic.objectiveName,
            "objective_na": mic.objectiveNumericalAperture,
            "saved_nsparc_mode": match.group(1).strip() if match else "not recorded",
            "display_lut": ranges,
            "display_transform": "One fixed native first-frame 1st/99.8th-percentile linear grayscale LUT per channel; no per-frame rescaling",
            "selected_native_frames": [
                {"frame_index": t, "sequence_index": native_indices[t],
                 "recorded_time_s": float(times[t]), "elapsed_s": float(elapsed[t]),
                 "elapsed_min": float(elapsed[t] / 60)} for t in indices
            ],
            "timebase_note": "Recorded ND2 acquisition timestamps; not an independently calibrated exposure clock",
            "all_selected_images_full_field": True,
            "rois_or_manual_labels_added": False,
        }
    if signature(path) != before:
        raise ValueError(f"Source size or modification time changed while reading: {path.name}")
    return info, frames, ranges


def scale_bar(ax, pixel_um: float) -> None:
    bar = AnchoredSizeBar(
        ax.transData, 100 / pixel_um, "100 µm", "lower right",
        pad=0.22, color="white", frameon=True, size_vertical=4,
        fontproperties=FontProperties(size=9), label_top=True, sep=3,
    )
    bar.patch.set(facecolor="black", edgecolor="none", alpha=0.68)
    ax.add_artist(bar)


def montage(info: dict, frames: dict, ranges: dict, rows: tuple[str, ...],
            size_inches: tuple[float, float], out: Path) -> None:
    selected = info["selected_native_frames"]
    fig, axes = plt.subplots(len(rows), len(selected), figsize=size_inches, squeeze=False)
    fig.subplots_adjust(left=0.055, right=0.998, bottom=0.008, top=0.958,
                        wspace=0.022, hspace=0.025)
    for row, name in enumerate(rows):
        c = CHANNELS.index(name)
        for column, selection in enumerate(selected):
            ax = axes[row, column]
            limits = ranges[name]
            ax.imshow(frames[selection["frame_index"]][c], cmap="gray",
                      vmin=limits["display_lo"], vmax=limits["display_hi"],
                      interpolation="nearest", origin="upper")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            if row == 0:
                ax.set_title(f'{selection["elapsed_min"]:.0f} min', fontsize=10, pad=5)
            if column == 0:
                ax.set_ylabel(name, fontsize=10, labelpad=7)
            scale_bar(ax, info["pixel_um"])
    fig.savefig(out, dpi=300, facecolor="white", bbox_inches=None,
                metadata={"Software": "scripts/make_paper_figures.py"})
    plt.close(fig)


def qc_figure(csv_path: Path, out: Path) -> dict:
    rows = csv_rows(csv_path)
    if len(rows) != 185:
        raise ValueError(f"Expected 185 sampled overnight rows, found {len(rows)}")
    time = np.array([float(row["elapsed_min"]) for row in rows], dtype=np.float64)
    frame_indices = [int(row["t_index"]) for row in rows]
    if len(set(frame_indices)) != len(rows) or not np.all(np.diff(time) > 0):
        raise ValueError("QC rows must have unique frame indices and increasing elapsed time")
    values = {key: np.array([float(row[key]) for row in rows]) for key, *_ in QC_METRICS}
    if not np.isfinite(time).all() or not all(np.isfinite(v).all() for v in values.values()):
        raise ValueError("QC CSV contains non-finite values")
    early = int(np.argmin(np.abs(time - 180)))
    fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.0))
    fig.subplots_adjust(left=0.095, right=0.96, bottom=0.19, top=0.80, wspace=0.30)
    handles = []
    for key, label, color, style in QC_METRICS:
        for ax in axes:
            line, = ax.plot(time, values[key], label=label, color=color,
                            linestyle=style, linewidth=1.25)
        handles.append(line)
    ylim = max(1.08, max(float(v.max()) for v in values.values()) * 1.035)
    for ax, label, limit, ticks in zip(
        axes, ("A  First 180 min", "B  Full 15 h"), (time[early], time[-1]),
        ((0, 60, 120, 180), (0, 300, 600, 900)),
    ):
        ax.set_title(label, loc="left", fontsize=10, fontweight="bold", pad=7)
        ax.axhline(1, color="#adb6ba", linewidth=0.7, zorder=0)
        ax.set_xlim(0, limit)
        ax.set_ylim(0, ylim)
        ax.set_xticks(ticks)
        ax.set_yticks([0, 0.5, 1])
        ax.set_xlabel("Elapsed time (min)", fontsize=9)
        ax.tick_params(labelsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dce2e4", linewidth=0.45)
    axes[0].set_ylabel("Relative to baseline", fontsize=9)
    fig.legend(handles, [x[1] for x in QC_METRICS], loc="upper center", ncols=3,
               frameon=False, fontsize=9, bbox_to_anchor=(0.53, 1.005),
               handlelength=2.5, columnspacing=1.2)
    fig.savefig(out, dpi=300, facecolor="white", bbox_inches=None,
                metadata={"Software": "scripts/make_paper_figures.py"})
    plt.close(fig)
    return {
        "source_csv": csv_path.relative_to(REPO).as_posix() if csv_path.is_relative_to(REPO) else csv_path.name,
        "source_csv_sha256": digest(csv_path), "sampled_rows": len(rows),
        "original_time_points": 5401,
        "frame_indices": frame_indices,
        "normalization": "Exact tracked values relative to the mean of the first five original frames",
        "metrics": [x[0] for x in QC_METRICS],
        "early_panel_last_checkpoint_min": float(time[early]),
        "full_panel_last_checkpoint_min": float(time[-1]),
        "processing": "No recalculation of metrics, smoothing, confidence intervals or fitted curves; line segments connect sampled values",
        "biological_replicates": "One existing movie; samples are not independent animals",
    }


def build(raw_root: Path, out: Path, snapshot: Path, baseline_path: Path) -> dict:
    if out.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    inventory = csv_rows(snapshot / "inventory.csv")
    baseline = csv_rows(baseline_path)
    paths = {name: raw_root / name for name in (CANDIDATE, OVERNIGHT)}
    before = {name: signature(path) for name, path in paths.items()}
    info1, frames1, lut1 = read_source(
        paths[CANDIDATE], 151, one_row(inventory, "filename", CANDIDATE),
        one_row(baseline, "file_name", CANDIDATE), indices=[0, 75, 150],
    )
    info2, frames2, lut2 = read_source(
        paths[OVERNIGHT], 5401, one_row(inventory, "filename", OVERNIGHT),
        one_row(baseline, "file_name", OVERNIGHT), target_minutes=[0, 15, 60, 180],
    )
    out.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "savefig.bbox": None, "axes.linewidth": 0.6})
    specs = {
        "fig1_aml18_candidate.png": (6.5, 6.6),
        "fig2_overnight_images.png": (6.5, 3.6),
        "fig3_overnight_qc.png": (6.5, 3.0),
    }
    montage(info1, frames1, lut1, CHANNELS, specs["fig1_aml18_candidate.png"], out / "fig1_aml18_candidate.png")
    montage(info2, frames2, lut2, ("TD", "GFP"), specs["fig2_overnight_images.png"], out / "fig2_overnight_images.png")
    qc = qc_figure(snapshot / "overnight_samples.csv", out / "fig3_overnight_qc.png")
    sources = [info1, info2]
    for info in sources:
        after = signature(paths[info["source_name"]])
        if after != before[info["source_name"]]:
            raise ValueError("Source changed during figure production; do not use the partial output")
        info["source_size_mtime_unchanged_during_production"] = True
        info["source_mtime_ns_after"] = after[1]
    figures = {}
    for name, inches in specs.items():
        with Image.open(out / name) as image:
            figures[name] = {"sha256": digest(out / name), "size_inches": list(inches),
                             "dpi_nominal": 300, "width_px": image.width,
                             "height_px": image.height, "bytes": (out / name).stat().st_size}
    provenance = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/make_paper_figures.py", "script_sha256": digest(Path(__file__)),
        "baseline_manifest": baseline_path.name, "baseline_manifest_sha256": digest(baseline_path),
        "inventory_csv_sha256": digest(snapshot / "inventory.csv"),
        "sources": sources, "qc_figure": qc, "figures": figures,
        "environment": {"python": platform.python_version(), "nd2": nd2.__version__,
                        "numpy": np.__version__, "matplotlib": matplotlib.__version__},
        "limits": ["Full-field display montages, not neuron annotations or lineage results",
                   "Fixed per-channel LUTs are display transforms, not quantitative intensity scales",
                   "Image contrast/sharpness changes do not establish death or the cause of blur",
                   "Raw baseline hashes are recorded, not freshly recomputed by this producer"],
        "reproduce": ["python", "scripts/make_paper_figures.py", "--raw-root", "<raw-storage-folder>",
                      "--out", "<new-output-folder>"],
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return provenance


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, default=REPO / "data/reviews/2026-11-18")
    parser.add_argument("--baseline-manifest", type=Path, default=REPO / "data/manifests/nd2_sha256_2026-11-17.csv")
    args = parser.parse_args(argv)
    try:
        result = build(args.raw_root, args.out, args.snapshot_dir, args.baseline_manifest)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    for name, record in result["figures"].items():
        print(f"{name}: {record['width_px']}x{record['height_px']} px, {record['sha256']}")


if __name__ == "__main__":
    main()
