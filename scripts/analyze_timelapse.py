"""Per-frame QC of ND2 time-lapses: timing, per-channel signal/bleaching, motion, montage.

Handles any mix of T, Z, C axes (Z is max-projected). The transmitted-light channel
(name containing "TD" or "DIC") is used only for motion. Outputs go to --out/<file stem>/:
per_frame.csv, summary.json, signal.png, motion.png, montage.png.

Usage:
    python scripts/analyze_timelapse.py --out D:/.../analysis file1.nd2 [file2.nd2 ...]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

import numpy as np
import nd2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TRANS_NAMES = ("TD", "DIC", "BF", "TRANS")
FG_K = 6.0  # foreground = pixels above median + FG_K * MAD (per frame, per channel)


def channel_names(f: nd2.ND2File) -> list[str]:
    try:
        return [c.channel.name for c in f.metadata.channels]
    except Exception:  # pragma: no cover - unusual metadata
        return [f"ch{i}" for i in range(f.sizes.get("C", 1))]


def time_points(f: nd2.ND2File, n_t: int) -> list[float]:
    """Start time (s) of each T index, from the event log."""
    ev = f.events()
    starts: dict[int, float] = {}
    for i, e in enumerate(ev):
        t_idx = int(e.get("T Index", i))
        t = float(e["Time [s]"])
        starts[t_idx] = min(t, starts.get(t_idx, t))
    if len(starts) >= n_t:
        keys = sorted(starts)[:n_t]
        return [starts[k] for k in keys]
    # fallback: per-plane metadata
    n_z = f.sizes.get("Z", 1)
    return [f.frame_metadata(t * n_z).channels[0].time.relativeTimeMs / 1000 for t in range(n_t)]


def as_cyx(frame: np.ndarray, axes: list[str]) -> np.ndarray:
    """Turn one time point (axes without T) into (C, Y, X), max-projecting Z."""
    a = np.asarray(frame)
    if "Z" in axes:
        a = a.max(axis=axes.index("Z"))
        axes = [x for x in axes if x != "Z"]
    if "C" not in axes:
        a = a[None]
    return a


def fg_stats(img: np.ndarray) -> tuple[float, float, float, float, float]:
    x = img.astype(np.float32).ravel()
    bg = float(np.median(x))
    mad = float(np.median(np.abs(x - bg))) or 1.0
    mask = x > bg + FG_K * mad
    p999 = float(np.percentile(x, 99.9))
    if mask.any():
        fg = float(x[mask].mean() - bg)
        integ = float((x[mask] - bg).sum())
    else:
        fg = integ = 0.0
    return p999, bg, fg, float(mask.mean()), integ


def shift_between(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Translation (dy, dx) of b relative to a by phase correlation."""
    a = a - a.mean()
    b = b - b.mean()
    r = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r /= np.abs(r) + 1e-9
    c = np.abs(np.fft.ifft2(r))
    dy, dx = np.unravel_index(np.argmax(c), c.shape)
    h, w = c.shape
    return float(dy - h if dy > h // 2 else dy), float(dx - w if dx > w // 2 else dx)


def retention(t_min: np.ndarray, v: np.ndarray, at_min: float) -> float | None:
    if t_min[-1] < at_min:
        return None
    start = np.mean(v[:5])
    i = int(np.searchsorted(t_min, at_min))
    win = v[max(0, i - 2): i + 3]
    return float(np.mean(win) / start) if start > 0 else None


def half_time(t_min: np.ndarray, v: np.ndarray) -> float | None:
    start = np.mean(v[:5])
    # smooth over ~5 frames to avoid single noisy frames
    k = 5
    if len(v) < k:
        return None
    sm = np.convolve(v, np.ones(k) / k, mode="valid")  # sm[i] centred on v[i + k // 2]
    below = np.nonzero(sm <= start / 2)[0]
    return float(t_min[below[0] + k // 2]) if below.size else None


def exp_tau(t_min: np.ndarray, v: np.ndarray) -> float | None:
    """Single-exponential time constant (min) from a log-linear fit (no offset)."""
    ok = v > 0
    if ok.sum() < 10:
        return None
    slope = np.polyfit(t_min[ok], np.log(v[ok]), 1)[0]
    return float(-1 / slope) if slope < 0 else None


def analyze(path: Path, out_root: Path, step: int) -> dict:
    out = out_root / path.stem
    out.mkdir(parents=True, exist_ok=True)
    with nd2.ND2File(str(path)) as f:
        sizes = dict(f.sizes)
        n_t = sizes.get("T", 1)
        axes = [k for k in sizes if k != "T"]
        names = channel_names(f)
        if "C" not in sizes:
            names = names[:1]
        trans = [i for i, n in enumerate(names) if n.upper() in TRANS_NAMES]
        fluor = [i for i in range(len(names)) if i not in trans]
        times = np.array(time_points(f, n_t))
        ev = f.events()
        laser = {}
        for n in names:
            vals = {e.get(f"{n} - Laser Power [%]") for e in ev} - {None}
            gains = {e.get(f"{n} - Gain [%]") for e in ev} - {None}
            laser[n] = {"laser_power_pct": sorted(vals), "gain_pct": sorted(gains)}
        mic = f.metadata.channels[0].microscope
        objective = f"{mic.objectiveName} (NA {mic.objectiveNumericalAperture})"
        vx = f.voxel_size()
        data = f.to_dask() if n_t > 1 else None

        idx = list(range(0, n_t, step))
        if idx[-1] != n_t - 1:
            idx.append(n_t - 1)
        rows = []
        prev_td = None
        drift_y = drift_x = 0.0
        montage_ts = sorted({idx[int(round(q * (len(idx) - 1)))] for q in (0, 0.25, 0.5, 0.75, 1)})
        montage = {}
        for t in idx:
            fr = as_cyx(data[t] if data is not None else f.asarray(), axes)
            row = {"t_index": t, "time_s": round(float(times[t] - times[0]), 3)}
            for c in fluor:
                p, bg, fg, area, integ = fg_stats(fr[c])
                n = names[c]
                row.update({f"{n}_p99_9": p, f"{n}_bg_median": bg, f"{n}_fg_mean_minus_bg": fg,
                            f"{n}_fg_area_frac": area, f"{n}_fg_integrated": integ})
            if trans:
                td = fr[trans[0]][::4, ::4].astype(np.float32)
                if prev_td is not None:
                    row["TD_activity"] = float(np.mean(np.abs(td - prev_td)) / (np.mean(prev_td) + 1e-9))
                    dy, dx = shift_between(prev_td, td)
                    drift_y += dy * 4 * vx.y
                    drift_x += dx * 4 * vx.x
                else:
                    row["TD_activity"] = ""
                row["TD_drift_y_um"], row["TD_drift_x_um"] = round(drift_y, 2), round(drift_x, 2)
                prev_td = td
            rows.append(row)
            if t in montage_ts:
                montage[t] = fr

    # --- per-frame CSV
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(out / "per_frame.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    # --- timing
    dts = np.diff(times)
    med = float(np.median(dts)) if dts.size else None
    timing = {
        "n_time_points": n_t,
        "duration_min": round(float(times[-1] - times[0]) / 60, 2),
        "interval_median_s": round(med, 3) if med is not None else None,
        "interval_min_s": round(float(dts.min()), 3) if dts.size else None,
        "interval_max_s": round(float(dts.max()), 3) if dts.size else None,
        "late_intervals_gt5pct": int((dts > med * 1.05).sum()) if dts.size else 0,
    }

    t_min = np.array([r["time_s"] for r in rows]) / 60
    ch_summary = {}
    for c in fluor:
        n = names[c]
        entry = {}
        for metric in ("p99_9", "fg_mean_minus_bg"):
            v = np.array([r[f"{n}_{metric}"] for r in rows], dtype=float)
            entry[metric] = {
                "start": round(float(np.mean(v[:5])), 1),
                "end": round(float(np.mean(v[-5:])), 1),
                "retained_end": round(float(np.mean(v[-5:]) / np.mean(v[:5])), 3) if np.mean(v[:5]) else None,
                "retained_30min": retention(t_min, v, 30),
                "retained_60min": retention(t_min, v, 60),
                "retained_120min": retention(t_min, v, 120),
                "half_time_min": half_time(t_min, v),
                "exp_tau_min": exp_tau(t_min, v),
            }
        a = np.array([r[f"{n}_fg_area_frac"] for r in rows], dtype=float)
        entry["fg_area_frac_start_end"] = [round(float(a[:5].mean()), 4), round(float(a[-5:].mean()), 4)]
        ch_summary[n] = entry
    motion = {}
    if trans:
        act = np.array([r["TD_activity"] for r in rows[1:]], dtype=float)
        motion = {
            "TD_activity_median": round(float(np.median(act)), 4) if act.size else None,
            "TD_activity_p95": round(float(np.percentile(act, 95)), 4) if act.size else None,
            "net_drift_um": [rows[-1]["TD_drift_y_um"], rows[-1]["TD_drift_x_um"]],
            "note": "activity = mean |frame diff| / mean intensity between analysed frames; "
                    "drift = summed whole-field phase-correlation shift (worms moving, not stage).",
        }
    summary = {
        "file": str(path), "sizes": sizes, "channels": names, "objective": objective,
        "pixel_um": round(vx.x, 4), "frame_step_analysed": step, "settings": laser,
        "timing": timing, "signal": ch_summary, "motion": motion,
        "foreground_rule": f"pixel > median + {FG_K} * MAD, per frame and channel",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    # --- figures
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    for c in fluor:
        n = names[c]
        for ax, metric, title in ((axs[0], "p99_9", "Brightest 0.1% (p99.9)"),
                                   (axs[1], "fg_mean_minus_bg", "Worm signal (fg mean - bg)")):
            v = np.array([r[f"{n}_{metric}"] for r in rows], dtype=float)
            ax.plot(t_min, v / np.mean(v[:5]), label=n, lw=1)
            ax.set_title(title)
    for ax in axs:
        ax.axhline(0.5, color="grey", ls=":", lw=0.8)
        ax.set_xlabel("time (min)")
        ax.set_ylabel("fraction of start")
        ax.set_ylim(bottom=0)
        ax.legend()
    fig.suptitle(path.name, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "signal.png", dpi=110)
    plt.close(fig)

    if trans:
        fig, axs = plt.subplots(1, 2, figsize=(11, 3.5))
        axs[0].plot(t_min[1:], [r["TD_activity"] for r in rows[1:]], lw=0.6)
        axs[0].set_title("Movement between frames (TD)")
        axs[0].set_xlabel("time (min)")
        axs[1].plot(t_min, [r["TD_drift_x_um"] for r in rows], label="x")
        axs[1].plot(t_min, [r["TD_drift_y_um"] for r in rows], label="y")
        axs[1].set_title("Cumulative whole-field shift (µm)")
        axs[1].set_xlabel("time (min)")
        axs[1].legend()
        fig.tight_layout()
        fig.savefig(out / "motion.png", dpi=110)
        plt.close(fig)

    ts = sorted(montage)
    fig, axs = plt.subplots(len(names), len(ts), figsize=(2.6 * len(ts), 2.6 * len(names)), squeeze=False)
    for j, t in enumerate(ts):
        for c in range(len(names)):
            im = montage[t][c].astype(np.float32)
            # fixed display range per channel = first frame's range, so bleaching is visible
            lo, hi = np.percentile(montage[ts[0]][c], [1, 99.8])
            axs[c, j].imshow(np.clip((im - lo) / (hi - lo + 1e-9), 0, 1), cmap="gray")
            axs[c, j].set_xticks([])
            axs[c, j].set_yticks([])
            if c == 0:
                axs[c, j].set_title(f"{(times[t] - times[0]) / 60:.0f} min", fontsize=9)
            if j == 0:
                axs[c, j].set_ylabel(names[c])
    fig.suptitle(f"{path.name} (same contrast as first frame)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "montage.png", dpi=90)
    plt.close(fig)
    print(f"done {path.name}: {n_t} T, analysed {len(idx)} -> {out}", flush=True)
    return summary


def compare_plot(out_root: Path, summaries: list[dict]) -> None:
    """Overlay worm signal (fraction of start) of every fluorescence channel of every file."""
    if not summaries:
        return
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for s in summaries:
        stem = Path(s["file"]).stem
        with open(out_root / stem / "per_frame.csv", newline="") as fh:
            rows = list(csv.DictReader(fh))
        t = np.array([float(r["time_s"]) for r in rows]) / 60
        for ch in s["signal"]:
            v = np.array([float(r[f"{ch}_fg_mean_minus_bg"]) for r in rows])
            if len(v) < 2 or np.mean(v[:5]) <= 0:
                continue
            power = s["settings"].get(ch, {}).get("laser_power_pct") or ["?"]
            ax.plot(t, v / np.mean(v[:5]), lw=1, label=f"{stem} | {ch} {power[0]}%")
    ax.axhline(0.5, color="grey", ls=":", lw=0.8)
    ax.set_xlabel("time (min)")
    ax.set_ylabel("worm signal, fraction of start")
    ax.set_ylim(bottom=0)
    ax.set_title("Signal retention across runs (fg mean - bg)")
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_root / "comparison.png", dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--step", type=int, default=1, help="analyse every Nth time point (default all)")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    allsum = []
    for p in a.files:
        try:
            allsum.append(analyze(p, a.out, a.step))
        except Exception as e:  # keep going on other files
            print(f"FAILED {p.name}: {e}", flush=True)
    (a.out / "all_summaries.json").write_text(json.dumps(allsum, indent=2))
    compare_plot(a.out, allsum)


if __name__ == "__main__":
    main()
