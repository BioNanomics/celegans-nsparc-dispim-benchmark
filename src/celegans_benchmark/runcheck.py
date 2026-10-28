"""Check an acquired time-lapse: cadence, dropped/late stacks, stack duration and signal over time.

The calculations are plain Python and work on per-time-point timestamps, so they are testable
without microscope files. Reading Nikon ND2 files needs the optional extra:
    pip install -e ".[nd2]"
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from .metrics import DEFAULT_INTERVAL_TOLERANCE, DataError

_EPS = 1e-6


def check_run(starts: list[float], ends: list[float], n_slices: int,
              planned_interval_s: float | None,
              tolerance: float = DEFAULT_INTERVAL_TOLERANCE) -> dict[str, Any]:
    """Summarise timing from the first/last slice time (s) of every time point.

    A stack's duration is measured from the data: last - first slice plus one slice step.
    Intervals longer than planned by more than `tolerance` are 'late'; gaps of about two or
    more planned intervals are counted as missing stacks. Unknowns are None, never 0.
    """
    if not starts or len(starts) != len(ends):
        raise DataError("need one start and one end time per time point")
    if n_slices < 1:
        raise DataError("n_slices must be at least 1")
    if planned_interval_s is not None and not (math.isfinite(planned_interval_s) and planned_interval_s > 0):
        raise DataError("planned interval must be a positive number of seconds")
    if any(e < s for s, e in zip(starts, ends)):
        raise DataError("a stack ends before it starts")
    if any(b <= a for a, b in zip(starts, starts[1:])):
        raise DataError("time points are not in increasing time order")

    intervals = [b - a for a, b in zip(starts, starts[1:])]
    stacks = None
    if n_slices > 1:
        stacks = [(e - s) * n_slices / (n_slices - 1) for s, e in zip(starts, ends)]

    result: dict[str, Any] = {
        "time_points": len(starts), "slices_per_stack": n_slices,
        "planned_interval_s": planned_interval_s, "tolerance": tolerance,
        "interval_s": ({"mean": round(mean(intervals), 3), "min": round(min(intervals), 3),
                        "max": round(max(intervals), 3)} if intervals else None),
        "late": None, "missing_estimate": None,
        "stack_duration_s": ({"mean": round(mean(stacks), 3), "max": round(max(stacks), 3)}
                             if stacks else None),
        "stack_fits_interval": None,
    }
    if planned_interval_s is not None:
        if intervals:
            limit = planned_interval_s * (1 + tolerance) + _EPS
            result["late"] = sum(1 for iv in intervals if iv > limit)
            result["missing_estimate"] = sum(max(0, round(iv / planned_interval_s) - 1)
                                             for iv in intervals)
        if stacks:
            result["stack_fits_interval"] = max(stacks) <= planned_interval_s
    return result


def signal_trend(values: list[float]) -> dict[str, Any] | None:
    """First, last and minimum signal; last as % of first (None if the first is 0)."""
    if not values:
        return None
    first, last = values[0], values[-1]
    return {"first": first, "last": last, "min": min(values),
            "last_pct_of_first": round(100 * last / first, 1) if first else None}


def read_nd2_run(path: str | Path) -> tuple[list[float], list[float], int, list[float]]:
    """(starts_s, ends_s, n_slices, signal_p99_9 per time point) from a single-channel ND2."""
    p = Path(path)
    if not p.is_file():
        raise DataError(f"ND2 file not found: {p}")
    try:
        import nd2
        import numpy as np
    except ImportError:
        raise DataError('Reading ND2 needs the optional extra: pip install -e ".[nd2]"') from None
    with nd2.ND2File(p) as f:
        sizes = dict(f.sizes)
        if sizes.get("C", 1) != 1 or sizes.get("P", 1) != 1:
            raise DataError("run-check supports one channel and one position per file")
        n_t, n_z = sizes.get("T", 1), sizes.get("Z", 1)
        data = f.to_dask()
        starts, ends, signal = [], [], []
        for t in range(n_t):
            first = f.frame_metadata(t * n_z).channels[0].time.relativeTimeMs / 1000
            last = f.frame_metadata(t * n_z + n_z - 1).channels[0].time.relativeTimeMs / 1000
            starts.append(first)
            ends.append(last)
            stack = np.asarray(data[t] if "T" in sizes else data)
            signal.append(round(float(np.percentile(stack, 99.9)), 1))
    return starts, ends, n_z, signal


def write_run_check(result: dict[str, Any], starts: list[float], ends: list[float],
                    signal: list[float], output_dir: str | Path) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    n = result["slices_per_stack"]
    summary = dict(result, signal_p99_9=signal_trend(signal))
    js = out / "run_check.json"
    js.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    table = out / "run_check_per_timepoint.csv"
    with table.open("w", encoding="utf-8", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["time_point", "start_s", "stack_s", "signal_p99_9"])
        for i, (s, e) in enumerate(zip(starts, ends)):
            stack = round((e - s) * n / (n - 1), 3) if n > 1 else ""
            w.writerow([i, round(s, 3), stack, signal[i] if i < len(signal) else ""])
    return [js, table]
