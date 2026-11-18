"""Read-only ND2 inventory and sampled-image review; outputs go to --out.

All time-point start metadata are inspected. Pixel inspection is limited to at
most five evenly spaced time points per file (all Z planes at those points).
No full-file checksum, full-pixel scan, organism count, or viability test is made.
"""
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict
import csv
import json
import math
import re
import traceback
import argparse

import nd2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def finite(value):
    try:
        return float(value) if math.isfinite(float(value)) else None
    except (ValueError, TypeError):
        return None

def sharpness(image):
    x = image.astype(np.float64)
    if not np.isfinite(x.mean()) or x.mean() <= 0:
        return None
    lap = -4*x[1:-1, 1:-1]+x[:-2, 1:-1]+x[2:, 1:-1]+x[1:-1, :-2]+x[1:-1, 2:]
    return finite(lap.var() / x.mean()**2)

def review_inventory(raw_root, manifest, out):
    """Inspect all headers/timestamps and at most five pixel time points per file.

    Z previews are projections, not proof of complete 3D anatomy. Source files
    remain read-only. A baseline checksum is copied, never represented as newly
    verified. Per-frame configured positions may be static; device event tags
    are retained separately. Native timestamps are not an independent clock.
    """
    ROOT, OUT = Path(raw_root), Path(out)
    REPO = Path(__file__).resolve().parents[1]
    baseline = {}
    if manifest:
        with Path(manifest).open(encoding="utf-8-sig", newline="") as stream:
            baseline = {row["file_name"]: row for row in csv.DictReader(stream)}
    records, timing_rows = [], []
    for path in sorted(ROOT.glob("*.nd2")):
        item = {"name": path.name, "path": str(path), "bytes": path.stat().st_size,
                "modified_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "full_hash_verified_today": False, "pixel_check": "at most 5 time points, all Z planes at each"}
        old = baseline.get(path.name)
        item.update({"in_baseline_manifest": old is not None,
                     "bytes_match_manifest": int(old["size_bytes"]) == item["bytes"] if old else None,
                     "baseline_sha256": old["raw_sha256"] if old else None})
        try:
            with nd2.ND2File(path) as f:
                sizes = dict(f.sizes)
                if sizes.get("V", 1) != 1 or set(sizes) - {"T", "Z", "C", "Y", "X", "V"}:
                    raise ValueError("Only one-position T/Z/C/Y/X files are supported")
                nt, nz = sizes.get("T", 1), sizes.get("Z", 1)
                names = [c.channel.name for c in f.metadata.channels]
                mic = f.metadata.channels[0].microscope
                voxel = f.voxel_size()
                loops = f.loop_indices
                by_t = {}
                for index, coords in enumerate(loops):
                    if coords.get("V", 0) != 0:
                        continue
                    by_t.setdefault(coords.get("T", 0), []).append(index)
                if sorted(by_t) != list(range(nt)):
                    raise ValueError("Time indices are not contiguous or do not match metadata")
                if any(len(group) != nz for group in by_t.values()):
                    raise ValueError("A time point does not contain the declared number of Z planes")
                time_loop = next((x for x in f.experiment if x.type == "TimeLoop"), None)
                plan_s = time_loop.parameters.periodMs / 1000 if time_loop else None
                starts, spans, z_positions = [], [], []
                for t in sorted(by_t):
                    group = by_t[t]
                    m = f.frame_metadata(group[0]).channels[0]
                    start = m.time.relativeTimeMs / 1000
                    last = f.frame_metadata(group[-1]).channels[0].time.relativeTimeMs / 1000 if len(group)>1 else start
                    z = finite(m.position.stagePositionUm.z)
                    starts.append(start)
                    spans.append(last - start)
                    if z is not None:
                        z_positions.append(z)
                    timing_rows.append({"file": path.name, "t_index": t, "start_s": start,
                                        "first_to_last_plane_start_s": last-start,
                                        "first_plane_recorded_z_um": z, "plane_records": len(group)})
                dts = np.diff(starts)
                if not np.all(np.isfinite(starts)):
                    raise ValueError("Recorded timestamps contain nonfinite values")
                capturing = f.text_info.get("capturing", "")
                events = f.events()
                event_ranges = {}
                event_keys = {key for row in events for key in row}
                for key in sorted(event_keys):
                    if not any(term in key for term in ("Z Coord", "Ti2 ZDrive", "Laser Power", "Gain", "PFS")):
                        continue
                    values = [finite(row.get(key)) for row in events]
                    values = [value for value in values if value is not None]
                    if values:
                        event_ranges[key] = {"min": min(values), "max": max(values), "first": values[0],
                                             "last": values[-1], "distinct_values": len(set(values))}
                item.update({"metadata_readable": True, "sizes": sizes, "channels": names,
                             "objective": mic.objectiveName, "objective_na": mic.objectiveNumericalAperture,
                             "voxel_um": {"x": voxel.x, "y": voxel.y, "z": voxel.z},
                             "planned_interval_s_from_metadata": plan_s,
                             "duration_min": (starts[-1]-starts[0])/60 if starts else None,
                             "time_points": nt, "z_planes": nz, "positions": sizes.get("V", 1),
                             "sequence_count": f.attributes.sequenceCount,
                             "interval_median_s": float(np.median(dts)) if len(dts) else None,
                             "interval_min_s": float(dts.min()) if len(dts) else None,
                             "interval_max_s": float(dts.max()) if len(dts) else None,
                             "intervals_over_plan_5pct": int((dts>plan_s*1.05).sum()) if plan_s and len(dts) else None,
                             "nonmonotonic_intervals": int((dts<=0).sum()),
                             "plane_start_span_median_s": float(np.median(spans)) if nz>1 else None,
                             "plane_start_span_note": "First-to-last plane START only; excludes last exposure and return, not complete stack duration",
                             "first_plane_z_range_um": max(z_positions)-min(z_positions) if z_positions else None,
                             "frame_metadata_position_note": "May be static configured position, not dynamic encoder readback; consult device_event_ranges",
                             "device_event_ranges": event_ranges,
                             "device_event_range_note": "All event rows; Z ranges include intentional Z scanning in Z-stack files, not just drift",
                             "saved_text_info": f.text_info,
                             "experiment": [asdict(x) for x in f.experiment],
                             "nsparc_cf_recorded": "Detector mode: NSPARC" in capturing and "NSPARC Mode: CF" in capturing})
                item["detector_mode"] = re.search(r"Detector mode:[ \t]*([^\r\n]+)", capturing).group(1).strip() if "Detector mode:" in capturing else None
                item["nsparc_mode"] = re.search(r"NSPARC Mode:[ \t]*([^\r\n]+)", capturing).group(1).strip() if "NSPARC Mode:" in capturing else None
                item["xy_um_per_px"] = voxel.x
                sample_ts = sorted(set(int(round(q*(nt-1))) for q in (0, .25, .5, .75, 1)))
                sample_images, sample_stats = {}, []
                for t in sample_ts:
                    frames = [f.read_frame(i) for i in by_t[t]]
                    image = np.maximum.reduce(frames)
                    if image.ndim == 2:
                        image = image[None]
                    sample_images[t] = image
                    for c, name in enumerate(names):
                        a = image[c]
                        sample_stats.append({"t_index": t, "elapsed_min": (starts[t]-starts[0])/60,
                                             "channel": name, "min": int(a.min()), "max": int(a.max()),
                                             "mean": float(a.mean()), "p99_9": float(np.percentile(a, 99.9)),
                                             "fraction_at_saturation": float((a >= (1 << f.attributes.bitsPerComponentSignificant)-1).mean()),
                                             "normalized_laplacian_variance": sharpness(a) if name.upper() in {"TD","DIC","BF","TRANS"} else None})
                item["sampled_pixel_statistics"] = sample_stats
                item["sampled_time_points"] = sample_ts
                item["sampled_pixels_readable"] = True
                fig, axes = plt.subplots(len(names), len(sample_ts), squeeze=False,
                                         figsize=(3.1*len(sample_ts), 3.1*len(names)+.6))
                for c, name in enumerate(names):
                    first = sample_images[sample_ts[0]][c]
                    lo, hi = np.percentile(first, [1, 99.8])
                    if hi <= lo:
                        hi = lo+1
                    for j, t in enumerate(sample_ts):
                        ax = axes[c, j]
                        ax.imshow(sample_images[t][c], cmap="gray", vmin=lo, vmax=hi)
                        if c == 0:
                            ax.set_title(f"{(starts[t]-starts[0])/60:.1f} min", fontsize=9)
                        ax.set_xticks([]); ax.set_yticks([])
                        if j==0:
                            ax.set_ylabel(name, fontsize=10)
                note = "Z maximum projection" if nz>1 else "Single plane"
                fig.suptitle(f"{path.name}\n{note}; fixed first-frame contrast per channel; sampled inspection", fontsize=10)
                fig.tight_layout(rect=(0,0,1,.94))
                preview = OUT / (path.stem + "_sampled.png")
                fig.savefig(preview, dpi=125)
                plt.close(fig)
                item["sampled_preview"] = str(preview)
                stat = path.stat()
                item["size_and_mtime_unchanged_since_inspection"] = (
                    stat.st_size == item["bytes"] and
                    datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() == item["modified_utc"])
                if not item["size_and_mtime_unchanged_since_inspection"]:
                    raise RuntimeError("Raw file changed during inspection; do not treat this result as complete")
                previous = REPO / "results/timelapse_analysis" / path.stem / "summary.json"
                item["existing_full_series_qc"] = str(previous) if previous.is_file() else None
                print(f"OK {path.name}: {nt}T {nz}Z {names} duration={item['duration_min']:.2f}min", flush=True)
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            item["traceback"] = traceback.format_exc()
            print(f"ERROR {path.name}: {item['error']}", flush=True)
        records.append(item)
        (OUT / "inventory.json").write_text(json.dumps({"generated_at": datetime.now().astimezone().isoformat(),
            "root": str(ROOT), "method": __doc__, "nd2_version": nd2.__version__, "files": records},
            indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    fields = ["name","bytes","metadata_readable","sampled_pixels_readable","time_points","z_planes","positions",
              "duration_min","planned_interval_s_from_metadata","interval_median_s","interval_min_s","interval_max_s",
              "intervals_over_plan_5pct","nonmonotonic_intervals","plane_start_span_median_s","objective","objective_na",
              "detector_mode","nsparc_mode","xy_um_per_px","nsparc_cf_recorded","bytes_match_manifest","full_hash_verified_today","size_and_mtime_unchanged_since_inspection","existing_full_series_qc","error"]
    with (OUT / "inventory.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(records)
    with (OUT / "time_points.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["file","t_index","start_s","first_to_last_plane_start_s","first_plane_recorded_z_um","plane_records"])
        writer.writeheader(); writer.writerows(timing_rows)
    print(f"DONE {len(records)} files; {sum(x['bytes'] for x in records):,} bytes; raw files untouched", flush=True)

    return records


def review_overnight(path, out, sample_minutes=5):
    """Sample apparent signal/TD sharpness; not survival or isolated bleaching."""
    PATH, OUT = Path(path), Path(out)
    if sample_minutes < 1:
        raise ValueError("sample_minutes must be positive")
    rows, previews = [], {}
    with nd2.ND2File(PATH) as f:
        if f.sizes.get("Z", 1) != 1 or f.sizes.get("V", 1) != 1:
            raise ValueError("Overnight sampling requires a single plane and position")
        names = [c.channel.name for c in f.metadata.channels]
        if names != ["GFP", "RFP", "TD"]:
            raise ValueError("Overnight sampling currently requires GFP, RFP, TD in that order")
        nt = f.sizes.get("T", 1)
        if nt < 5:
            raise ValueError("At least five time points are needed for the baseline")
        times = np.array([f.frame_metadata(i).channels[0].time.relativeTimeMs/1000 for i in range(nt)])
        times -= times[0]
        if np.any(np.diff(times) <= 0):
            raise ValueError("Recorded timestamps must increase")
        duration_min = float(times[-1] / 60)
        preview_minutes = [m for m in [0, 15, 30, 60, 120, 180] if m <= duration_min+1e-6]
        preview_ids = {int(np.argmin(abs(times-minute*60))): minute for minute in preview_minutes}
        selected = sorted(set(range(5)) | {nt-1} | set(preview_ids) | {
            int(np.argmin(abs(times-minute*60))) for minute in range(0, int(duration_min)+1, sample_minutes)})
        print(f"Reading {len(selected)} selected frames of {nt}", flush=True)
        for t in selected:
            frame = f.read_frame(t)
            row = {"t_index": t, "elapsed_min": float(times[t]/60)}
            for c, name in enumerate(names):
                x = frame[c].astype(np.float64)
                bg, p999 = np.percentile(x, [50, 99.9])
                row[name+"_median"] = float(bg)
                row[name+"_p99_9_minus_median"] = float(p999-bg)
                row[name+"_max"] = int(x.max())
                if name == "TD":
                    row["TD_normalized_laplacian_variance"] = sharpness(x)
            rows.append(row)
            if t in preview_ids:
                # read_frame may expose file-backed memory; retained images must own
                # their pixels before the reader closes.
                previews[preview_ids[t]] = frame.copy()

    metrics = ["GFP_p99_9_minus_median", "RFP_p99_9_minus_median", "TD_normalized_laplacian_variance"]
    baseline_rows = [r for r in rows if r["t_index"] < 5]
    if any(finite(r[k]) is None for r in baseline_rows for k in metrics):
        raise ValueError("Cannot normalize an unevaluable initial signal/sharpness baseline")
    baselines = {k: float(np.mean([r[k] for r in baseline_rows])) for k in metrics}
    if any(not math.isfinite(value) or value <= 0 for value in baselines.values()):
        raise ValueError("Cannot normalize a nonpositive initial signal/sharpness baseline")
    for r in rows:
        for k in metrics:
            r[k+"_relative_first5"] = r[k]/baselines[k] if finite(r[k]) is not None else None
    with (OUT / "overnight_samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

    fig, axes = plt.subplots(1, 2, figsize=(11,4.5))
    for ax, limit, title in zip(axes, [min(180, duration_min), duration_min],
                               ["Early recording", "Full recorded span"]):
        for k, label, color in zip(metrics, ["GFP apparent signal", "RFP apparent signal", "TD sharpness proxy"],
                                   ["#087f5b", "#b04a16", "#3155a5"]):
            ax.plot([r["elapsed_min"] for r in rows], [r[k+"_relative_first5"] for r in rows],
                    color=color, label=label, lw=1.4)
        finite_values = [r[k+"_relative_first5"] for r in rows for k in metrics
                         if finite(r[k+"_relative_first5"]) is not None]
        ax.set(xlim=(0,limit), ylim=(0,max(1.1, max(finite_values)*1.05)),
               xlabel="Elapsed time (min)", ylabel="Relative to first five frames", title=title)
        ax.grid(alpha=.15)
    axes[1].legend(fontsize=8, loc="upper right")
    fig.suptitle("Sampled fluorescence and TD sharpness proxies", fontsize=12)
    fig.text(.5,.01,f"{sample_minutes}-minute samples plus preview frames; fluorescence = p99.9 minus median. These proxies do not identify cause or establish death.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0,.045,1,.94))
    fig.savefig(OUT/"overnight_sampled_qc.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(3, len(preview_minutes), squeeze=False, figsize=(16,8.7))
    for c, name in enumerate(names):
        lo, hi = np.percentile(previews[0][c], [1,99.8])
        for j, minute in enumerate(preview_minutes):
            ax=axes[c,j]
            ax.imshow(previews[minute][c], cmap="gray", vmin=lo, vmax=max(hi,lo+1))
            if c==0:
                ax.set_title(f"{minute} min", fontsize=10)
            if j==0:
                ax.set_ylabel(name, fontsize=11)
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Early recorded frames\nFixed first-frame contrast per channel; saved single-plane samples", fontsize=12)
    fig.tight_layout(rect=(0,0,1,.93), h_pad=1.5)
    fig.savefig(OUT/"overnight_early_samples.png", dpi=150)
    plt.close(fig)

    chosen=[]
    for minute in sorted(set([m for m in [0,5,15,30,60,120,180] if m <= duration_min] + [duration_min])):
        r=min(rows,key=lambda x: abs(x["elapsed_min"]-minute))
        chosen.append({k:r[k] for k in ["t_index","elapsed_min"]+[v+"_relative_first5" for v in metrics]})
    report={"file":str(PATH), "generated_at":datetime.now().astimezone().isoformat(), "sampled_frames":len(rows),
            "total_frames":nt, "sampling":f"every {sample_minutes} minutes plus first five, preview and last frames; not all pixels/time points",
            "baseline_first5":baselines,"checkpoints":chosen,
            "limits":["Whole-field proxies depend on image content, motion, focus and noise.",
                      "Signal loss is not isolated photobleaching and does not establish death.",
                      "Stable recorded stage values do not rule out optical/sample drift."]}
    (OUT/"overnight_sampled_qc.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(report,indent=2))

    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, help="Existing checksum inventory; hashes are not recomputed")
    parser.add_argument("--out", type=Path, required=True, help="A new output directory; existing directories are refused")
    parser.add_argument("--overnight", help="Optional plain ND2 filename in raw-root for denser GFP/RFP/TD sampling")
    parser.add_argument("--sample-minutes", type=int, default=5)
    args = parser.parse_args(argv)
    if not args.raw_root.is_dir() or not list(args.raw_root.glob("*.nd2")):
        parser.error("raw-root must contain at least one ND2 file")
    if args.manifest and not args.manifest.is_file():
        parser.error("manifest does not exist")
    if args.sample_minutes < 1:
        parser.error("sample-minutes must be positive")
    if args.out.exists():
        parser.error("out already exists; choose a new directory to preserve earlier results")
    if args.overnight and (Path(args.overnight).name != args.overnight or not (args.raw_root/args.overnight).is_file()):
        parser.error("overnight must be a plain filename present in raw-root")
    args.out.mkdir(parents=True)
    records = review_inventory(args.raw_root, args.manifest, args.out)
    if args.overnight:
        review_overnight(args.raw_root/args.overnight, args.out, args.sample_minutes)
    return 0 if all(r.get("sampled_pixels_readable") and not r.get("error") for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
