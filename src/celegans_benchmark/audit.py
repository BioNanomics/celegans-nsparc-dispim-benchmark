"""Helpers for the manual audit: choose frames in advance from tracker spot counts.

Input is a plain `time_point,spots` table (lines starting with '#' are comments), so any
tracker's output (StarryNite, AceTree, Mastodon, ...) can be used after a simple export.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any

from .checksum import sha256_file
from .metrics import STAGES, DataError, load_data, stage_of

SELECTION_FIELDS = ("time_point", "estimated_spots", "stage")


def read_spot_counts(path: str | Path) -> tuple[dict[int, int], list[int]]:
    """Return ({time_point: spots}, [time points with a blank spot count]).

    A blank spot count is unknown, never zero, so that time point is not eligible.
    """
    p = Path(path)
    if not p.is_file():
        raise DataError(f"Spot-count file not found: {p}")
    with p.open(encoding="utf-8-sig", newline="") as handle:
        lines = [line for line in handle if line.strip() and not line.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    if reader.fieldnames is None or [f.strip() for f in reader.fieldnames] != ["time_point", "spots"]:
        raise DataError(f"{p.name}: header must be exactly 'time_point,spots'")
    counts: dict[int, int] = {}
    blank: list[int] = []
    seen: set[int] = set()
    for line, row in enumerate(reader, start=2):
        t_raw, n_raw = (row.get("time_point") or "").strip(), (row.get("spots") or "").strip()
        if not t_raw.isdigit():
            raise DataError(f"{p.name} row {line}: time_point must be a non-negative integer, got {t_raw!r}")
        t = int(t_raw)
        if t in seen:
            raise DataError(f"{p.name}: duplicate time_point {t}")
        seen.add(t)
        if not n_raw:
            blank.append(t)
        elif n_raw.isdigit():
            counts[t] = int(n_raw)
        else:
            raise DataError(f"{p.name} row {line}: spots must be a non-negative integer or blank, got {n_raw!r}")
    if not seen:
        raise DataError(f"{p.name}: no rows")
    return counts, blank


def select_frames(counts: dict[int, int], per_stage: int, seed: int) -> list[dict[str, Any]]:
    """Pick up to `per_stage` time points from each nuclei-count stage, reproducibly.

    The stage is estimated from the tracker's spot count, because the manual count is not
    known yet when frames are chosen. A stage with fewer frames contributes all of them;
    a stage with none contributes nothing.
    """
    if per_stage < 1:
        raise DataError("per_stage must be at least 1")
    rng = random.Random(seed)
    chosen: list[int] = []
    for stage in STAGES:
        pool = sorted(t for t, n in counts.items() if stage_of(n) == stage)
        chosen += pool if len(pool) <= per_stage else rng.sample(pool, per_stage)
    return [{"time_point": t, "estimated_spots": counts[t], "stage": stage_of(counts[t])}
            for t in sorted(chosen)]


def write_selection(rows: list[dict[str, Any]], path: str | Path) -> str:
    """Write the frame list and return its SHA-256. Never overwrites: a chosen list is frozen."""
    p = Path(path)
    if p.exists():
        raise DataError(f"{p} already exists; refusing to overwrite a frozen frame list")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SELECTION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return sha256_file(p)


def check_audit(data_dir: str | Path, embryo_id: str,
                spot_counts: str | Path) -> list[dict[str, Any]]:
    """Compare tp+fp of each audited frame of one embryo with the tracker's spot count.

    Every tracker spot is either a true or a false detection, so tp+fp should equal the
    tracker's count for that frame. Near/far rows are summed per frame. A frame absent from
    the counts file, or with a blank count, is 'not_checkable' (unknown), never a mismatch.
    """
    ds = load_data(data_dir)
    if embryo_id not in ds.embryos:
        raise DataError(f"Unknown embryo_id {embryo_id!r} in {Path(data_dir) / 'acquisitions.csv'}")
    counts, _ = read_spot_counts(spot_counts)
    totals: dict[int, int] = {}
    for r in ds.nuclei:
        if r["embryo_id"] == embryo_id:
            vol = int(r["volume_index"])
            totals[vol] = totals.get(vol, 0) + int(r["tp"]) + int(r["fp"])
    results = []
    for vol in sorted(totals):
        tracker = counts.get(vol)
        status = ("not_checkable" if tracker is None
                  else "ok" if tracker == totals[vol] else "mismatch")
        results.append({"embryo_id": embryo_id, "volume_index": vol, "tp_plus_fp": totals[vol],
                        "tracker_spots": tracker, "status": status})
    return results
