"""Per-frame QC of ND2 time-lapses: timing, per-channel signal/bleaching, movement, montage.

Handles any mix of T, Z, C axes (Z is max-projected). The transmitted-light channel
(name "TD", "DIC", "BF" or "TRANS") is used only for movement. Outputs go to --out/<file stem>/:
per_frame.csv, summary.json, signal.png, movement.png, movement_maps.png, montage.png.

Movement measures (descriptive; compare a run with its own start, not runs with each other):
- TD_motion_frac: fraction of transmitted-light pixels that change between consecutive
  analysed frames by more than 6 robust SDs of the frame difference (needs a TD channel).
- <channel>_turnover_60s: 1 - overlap of the fluorescent worm masks ~60 s apart
  (|A xor B| / |A or B|). Uses masks, not intensities, so bleaching is not counted as movement.

Usage:
    python scripts/analyze_timelapse.py --out results/timelapse_analysis file1.nd2 [file2.nd2 ...]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

import numpy as np
import nd2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TRANS_NAMES = ("TD", "DIC", "BF", "TRANS")
FG_K = 6.0  # foreground = pixels above median + FG_K * MAD (per frame, per channel)
MOTION_K = 6.0  # TD pixel "moved" if |frame difference| > MOTION_K robust SDs
TURNOVER_GAP_S = 60.0
BIN_MIN = 30.0


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


def _bg_mad(x: np.ndarray) -> tuple[float, float]:
    bg = float(np.median(x))
    mad = float(np.median(np.abs(x - bg))) or 1.0
    return bg, mad


def fg_mask(img: np.ndarray) -> np.ndarray:
    """Foreground (worm) pixels: above median + FG_K * MAD."""
    x = img.astype(np.float32)
    bg, mad = _bg_mad(x)
    return x > bg + FG_K * mad


def fg_stats(img: np.ndarray) -> tuple[float, float, float, float, float]:
    """(p99.9, background median, fg mean - bg, fg area fraction, fg integrated - bg)."""
    x = img.astype(np.float32).ravel()
    bg, mad = _bg_mad(x)
    mask = x > bg + FG_K * mad
    p999 = float(np.percentile(x, 99.9))
    if mask.any():
        fg = float(x[mask].mean() - bg)
        integ = float((x[mask] - bg).sum())
    else:
        fg = integ = 0.0
    return p999, bg, fg, float(mask.mean()), integ


def motion_frac(a: np.ndarray, b: np.ndarray) -> float:
    """Fraction of pixels whose change from a to b exceeds MOTION_K robust SDs of the difference."""
    df = b.astype(np.float32) - a.astype(np.float32)
    df -= np.median(df)  # ignore a uniform brightness change
    sd = 1.4826 * float(np.median(np.abs(df))) + 1e-6
    return float((np.abs(df) > MOTION_K * sd).mean())


def mask_turnover(a: np.ndarray, b: np.ndarray) -> float | None:
    """|A xor B| / |A or B|: 0 = same pixels, 1 = no overlap. None if both masks empty."""
    union = int(np.logical_or(a, b).sum())
    if union == 0:
        return None
    return float(np.logical_xor(a, b).sum() / union)


def binned(t_min: np.ndarray, vals: np.ndarray, width: float = BIN_MIN) -> list[tuple[float, float]]:
    """Mean of vals in consecutive time bins [s, s+width) starting at 0; NaNs ignored.

    A trailing bin covering < 25% of `width` (e.g. only the final frame) is dropped."""
    out = []
    end = t_min[-1] if len(t_min) else 0.0
    for s in np.arange(0, max(end, 1e-9), width):
        if s > 0 and min(s + width, end) - s < 0.25 * width:
            continue
        m = (t_min >= s) & (t_min < s + width) & ~np.isnan(vals)
        if m.any():
            out.append((float(s), float(np.mean(vals[m]))))
    return out


def retention(t_min: np.ndarray, v: np.ndarray, at_min: float) -> float | None:
    if t_min[-1] < at_min:
        return None
    start = np.mean(v[:5])
    i = int(np.searchsorted(t_min, at_min))
    win = v[max(0, i - 2): i + 3]
    return float(np.mean(win) / start) if start > 0 else None


def half_time(t_min: np.ndarray, v: np.ndarray) -> float | None:
    start = np.mean(v[:5])
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


def _col(rows: list[dict], key: str) -> np.ndarray:
    return np.array([np.nan if r.get(key, "") in ("", None) else float(r[key]) for r in rows])


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
        dt_med = float(np.median(np.diff(times))) if n_t > 1 else TURNOVER_GAP_S
        dt_an = dt_med * step
        gap = max(1, int(round(TURNOVER_GAP_S / dt_an)))  # analysed frames ~60 s apart
        win = max(5, int(round(60 / dt_an)))  # movement-map window: >= 1 min and >= 5 frames
        map_src = trans[0] if trans else (fluor[0] if fluor else 0)
        win_starts = sorted({0, max(0, len(idx) // 2 - win // 2), max(0, len(idx) - win)})
        win_frames: dict[int, list] = {s: [] for s in win_starts}
        masks = {c: collections.deque(maxlen=gap + 1) for c in fluor}

        rows = []
        prev_td = None
        montage_ts = sorted({idx[int(round(q * (len(idx) - 1)))] for q in (0, 0.25, 0.5, 0.75, 1)})
        montage = {}
        for k, t in enumerate(idx):
            fr = as_cyx(data[t] if data is not None else f.asarray(), axes)
            row = {"t_index": t, "time_s": round(float(times[t] - times[0]), 3)}
            for c in fluor:
                p, bg, fg, area, integ = fg_stats(fr[c])
                n = names[c]
                row.update({f"{n}_p99_9": p, f"{n}_bg_median": bg, f"{n}_fg_mean_minus_bg": fg,
                            f"{n}_fg_area_frac": area, f"{n}_fg_integrated": integ})
                masks[c].append(fg_mask(fr[c]))
                tv = mask_turnover(masks[c][0], masks[c][-1]) if len(masks[c]) == gap + 1 else None
                row[f"{n}_turnover_60s"] = "" if tv is None else tv
            if trans:
                td = fr[trans[0]].astype(np.float32)
                row["TD_motion_frac"] = motion_frac(prev_td, td) if prev_td is not None else ""
                prev_td = td
            for s in win_starts:
                if s <= k < s + win:
                    img = fr[map_src].astype(np.float32)
                    if not trans:  # fluorescence: normalise so bleaching does not look like motion
                        img /= max(float(np.percentile(img, 99.9)), 1.0)
                    win_frames[s].append((t, img))
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
            v = _col(rows, f"{n}_{metric}")
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
        a = _col(rows, f"{n}_fg_area_frac")
        entry["fg_area_frac_start_end"] = [round(float(a[:5].mean()), 4), round(float(a[-5:].mean()), 4)]
        ch_summary[n] = entry

    movement = {"bin_min": BIN_MIN, "turnover_gap_s": round(gap * dt_an, 1), "measures": {}}
    move_keys = (["TD_motion_frac"] if trans else []) + [f"{names[c]}_turnover_60s" for c in fluor]
    for key in move_keys:
        b = binned(t_min, _col(rows, key))
        if not b:
            continue
        first, last = b[0][1], b[-1][1]
        movement["measures"][key] = {
            "bins": [{"start_min": s, "mean": round(m, 5)} for s, m in b],
            "last_over_first": round(last / first, 3) if first > 0 and len(b) > 1 else None,
        }
    summary = {
        "file": str(path), "sizes": sizes, "channels": names, "objective": objective,
        "pixel_um": round(vx.x, 4), "frame_step_analysed": step, "settings": laser,
        "timing": timing, "signal": ch_summary, "movement": movement,
        "foreground_rule": f"pixel > median + {FG_K} * MAD, per frame and channel",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    # --- figures
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    for c in fluor:
        n = names[c]
        for ax, metric, title in ((axs[0], "p99_9", "Brightest 0.1% (p99.9)"),
                                   (axs[1], "fg_mean_minus_bg", "Worm signal (fg mean - bg)")):
            v = _col(rows, f"{n}_{metric}")
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

    if movement["measures"]:
        keys_present = list(movement["measures"])
        fig, axs = plt.subplots(1, len(keys_present), figsize=(5.5 * len(keys_present), 3.6), squeeze=False)
        for ax, key in zip(axs[0], keys_present):
            v = _col(rows, key)
            ok = ~np.isnan(v)
            ax.plot(t_min[ok], v[ok], lw=0.5, alpha=0.5, color="grey", label="per frame")
            b = movement["measures"][key]["bins"]
            ax.step([x["start_min"] for x in b] + [b[-1]["start_min"] + BIN_MIN],
                    [x["mean"] for x in b] + [b[-1]["mean"]], where="post", color="C3", lw=2,
                    label=f"{BIN_MIN:.0f}-min mean")
            ax.set_title(key.replace("_", " "))
            ax.set_xlabel("time (min)")
            ax.set_ylim(bottom=0)
            ax.legend(fontsize=8)
        fig.suptitle(f"{path.name}: movement (higher = more moving)", fontsize=9)
        fig.tight_layout()
        fig.savefig(out / "movement.png", dpi=110)
        plt.close(fig)

    # movement maps: first frame of each window (top) and SD over the window (bottom, bright = moving)
    wins = [s for s in win_starts if len(win_frames[s]) >= 2]
    if wins:
        sds = {s: np.stack([im for _, im in win_frames[s]]).std(0) for s in wins}
        vmax = float(np.percentile(sds[wins[0]], 99.5)) or 1.0
        h, w_ = sds[wins[0]].shape
        fig, axs = plt.subplots(2, len(wins), figsize=(4.2 * len(wins), 2 * 4.2 * h / w_ + 0.8), squeeze=False)
        for j, s in enumerate(wins):
            t0, first = win_frames[s][0]
            t1 = win_frames[s][-1][0]
            lo, hi = np.percentile(first, [1, 99.5])
            axs[0, j].imshow(first, cmap="gray", vmin=lo, vmax=hi)
            axs[0, j].set_title(f"{names[map_src]} at {(times[t0] - times[0]) / 60:.0f} min", fontsize=9)
            axs[1, j].imshow(sds[s], cmap="magma", vmin=0, vmax=vmax)
            axs[1, j].set_title(f"movement {(times[t0] - times[0]) / 60:.0f}-{(times[t1] - times[0]) / 60:.0f} min",
                                fontsize=9)
            for ax in axs[:, j]:
                ax.set_xticks([])
                ax.set_yticks([])
        fig.suptitle(f"{path.name}: bottom = SD over window, same scale (bright = moving)", fontsize=9)
        fig.tight_layout()
        fig.savefig(out / "movement_maps.png", dpi=90)
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


def compare_movement_plot(out_root: Path, summaries: list[dict]) -> None:
    """Overlay 60 s mask turnover (30-min means, fraction of first bin) for every run."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    drawn = False
    for s in summaries:
        stem = Path(s["file"]).stem
        for key, m in s.get("movement", {}).get("measures", {}).items():
            if not key.endswith("_turnover_60s") or len(m["bins"]) < 2 or m["bins"][0]["mean"] <= 0:
                continue
            x = [b["start_min"] + BIN_MIN / 2 for b in m["bins"]]
            y = [b["mean"] / m["bins"][0]["mean"] for b in m["bins"]]
            ax.plot(x, y, marker="o", ms=3, lw=1.2, label=f"{stem} | {key.split('_')[0]}")
            drawn = True
    if not drawn:
        plt.close(fig)
        return
    ax.axhline(1, color="grey", ls=":", lw=0.8)
    ax.set_xlabel("time (min, centre of 30-min bin)")
    ax.set_ylabel("movement, fraction of first 30 min")
    ax.set_ylim(bottom=0)
    ax.set_title("Worm movement across runs (60 s fluorescent-mask turnover)")
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_root / "comparison_movement.png", dpi=110)
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
    compare_movement_plot(a.out, allsum)


if __name__ == "__main__":
    main()
