"""Deterministic review plan and CSV schemas for the AML18 10-minute movie.

This module reads no images and creates no annotations or files. A frame plan is
an evaluation-design record, not manual ground truth or a tracking result.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

SOURCE_NAME = "Celegans_01_stack_timing1111.nd2"
FRAME_COUNT = 151
WIDTH_PX = HEIGHT_PX = 1024
DEFAULT_SEED = 20261118
PRIOR_PREVIEW_FRAMES = (0, 38, 75, 112, 150)
VISIBILITY_STATES = ("visible", "uncertain", "not_visible")
FRAME_REVIEW_STATES = ("not_reviewed", "reviewed", "needs_review")

ANNOTATION_FIELDNAMES = (
    "source_sha256", "plan_sha256", "reviewer_id", "target_id", "frame_index",
    "time_s", "split", "channel", "visibility", "x_px", "y_px", "x_um", "y_um",
    "reason", "notes", "reviewed_at",
)
FRAME_REVIEW_FIELDNAMES = (
    "source_sha256", "plan_sha256", "reviewer_id", "frame_index", "time_s",
    "split", "review_status", "notes", "reviewed_at",
)


def annotation_fieldnames() -> list[str]:
    """Return a fresh ordered list of per-target annotation CSV columns."""
    return list(ANNOTATION_FIELDNAMES)


def frame_review_fieldnames() -> list[str]:
    """Return a fresh ordered list of whole-frame review CSV columns."""
    return list(FRAME_REVIEW_FIELDNAMES)


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, (bool, str, bytes)):
        raise ValueError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _secondary_frames(start: int, end: int, split: str, seed: int) -> list[int]:
    """Select five frames by hash ranking, independent of pixels and RNG version."""
    def rank(frame: int) -> tuple[bytes, int]:
        key = f"celegans-spot-secondary-v1|{seed}|{split}|{frame}"
        return hashlib.sha256(key.encode("ascii")).digest(), frame

    return sorted(sorted(range(start, end + 1), key=rank)[:5])


def build_frame_plan(times_s: Iterable[float], source_sha256: str, pixel_um: float,
                     seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Build a fixed 151-frame, temporally blocked manual-review plan.

    ``times_s`` contains the native frame-start timestamps in seconds, in frame
    order. The plan stores elapsed seconds relative to the first frame. Values
    must be finite and strictly increasing; no idealized four-second clock is
    substituted for measured timestamps. ``source_sha256`` identifies the raw
    ND2 bytes, not an exported image. The caller verifies that the source name,
    image shape, channel order and calibration match this specific movie.

    No image-quality score enters secondary-frame selection. Five frames from
    development and five from evaluation are selected using SHA-256 ranking of
    the seed, split and frame index. All review states start unreviewed, and no
    algorithmic matching tolerance is selected here.
    """
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
        raise ValueError("source_sha256 must contain exactly 64 hexadecimal characters")
    calibration = _finite_number(pixel_um, "pixel_um")
    if calibration <= 0:
        raise ValueError("pixel_um must be positive")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if isinstance(times_s, (str, bytes)):
        raise ValueError("times_s must contain 151 numeric timestamps")
    try:
        raw_times = list(times_s)
    except TypeError as exc:
        raise ValueError("times_s must contain 151 numeric timestamps") from exc
    if len(raw_times) != FRAME_COUNT:
        raise ValueError(f"expected {FRAME_COUNT} timestamps, got {len(raw_times)}")
    times = [_finite_number(value, f"times_s[{i}]") for i, value in enumerate(raw_times)]
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise ValueError("times_s must be strictly increasing in frame order")
    elapsed = [value - times[0] for value in times]
    if not all(math.isfinite(value) for value in elapsed):
        raise ValueError("elapsed frame times must remain finite")

    bounds = (("development", 0, 59), ("buffer", 60, 74), ("evaluation", 75, 150))
    secondary = (_secondary_frames(0, 59, "development", seed)
                 + _secondary_frames(75, 150, "evaluation", seed))
    secondary_set = set(secondary)
    splits = {
        name: {"start_frame": start, "end_frame": end, "frame_count": end - start + 1}
        for name, start, end in bounds
    }
    frames = [
        {"frame_index": i, "time_s": elapsed[i], "split": name,
         "secondary_review": i in secondary_set, "review_status": "not_reviewed"}
        for name, start, end in bounds for i in range(start, end + 1)
    ]
    return {
        "schema": "celegans_benchmark.spot_annotation.frame_plan",
        "schema_version": 1,
        "source_name": SOURCE_NAME,
        "source_sha256": source_sha256.lower(),
        "frame_count": FRAME_COUNT,
        "width_px": WIDTH_PX,
        "height_px": HEIGHT_PX,
        "pixel_um": calibration,
        "coordinate_convention": (
            "Zero-based full-image pixel centres; origin is upper-left, x is column and y is row. "
            "Image-space x_um=x_px*pixel_um and y_um=y_px*pixel_um; these are not stage coordinates."
        ),
        "timebase": "Native ND2 frame-start timestamps, elapsed seconds since the first frame",
        "primary_channel": "GFP",
        "context_channels": ["RFP", "TD"],
        "seed": seed,
        "secondary_review_method": "sha256-ranking-v1: five development and five evaluation frames; no buffer frames",
        "secondary_review_frames": secondary,
        "prior_preview_frames": list(PRIOR_PREVIEW_FRAMES),
        "held_out_disclosure": (
            "Frames 0, 38, 75, 112 and 150 were qualitatively previewed before this plan. "
            "Evaluation means withheld from tracker fitting and threshold selection, not wholly unseen images. "
            "The temporal blocks come from one movie and are not independent biological replicates."
        ),
        "matching_tolerance_um": None,
        "visibility_states": list(VISIBILITY_STATES),
        "frame_review_states": list(FRAME_REVIEW_STATES),
        "splits": splits,
        "frames": frames,
    }


def plan_digest(plan: Mapping[str, Any]) -> str:
    """SHA-256 of canonical UTF-8 JSON, excluding an optional top-level digest.

    Keys are sorted, separators have no extra spaces, Unicode is retained, and
    NaN/infinity are rejected. An optional ``plan_sha256`` field is excluded so
    callers can embed this derived value without a recursive checksum. Verify
    an embedded value by comparing it with this function's recomputed result.
    """
    if not isinstance(plan, Mapping):
        raise TypeError("plan must be a mapping")
    payload = {key: value for key, value in plan.items() if key != "plan_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
