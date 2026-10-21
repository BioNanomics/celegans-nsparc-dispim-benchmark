"""Record which code, settings and input files produced a report (run_info.json)."""

from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .checksum import sha256_file
from .metrics import TABLES, Gates


def git_info(cwd: str | Path) -> tuple[str | None, bool | None]:
    """(commit, has_uncommitted_changes) of the repo containing cwd; (None, None) if unknown."""
    try:
        def run(*args: str) -> str:
            result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                                    timeout=10, check=True)
            return result.stdout.strip()
        return run("rev-parse", "HEAD"), bool(run("status", "--porcelain"))
    except (OSError, subprocess.SubprocessError):
        return None, None


def build_run_info(data_dir: str | Path, gates: Gates, interval_tolerance: float,
                   warnings: list[str], now: str | None = None,
                   git: tuple[str | None, bool | None] | None = None) -> dict[str, Any]:
    """Provenance for one report run.

    Input files are recorded by file name and SHA-256 only, so private folder paths
    are never written into the output.
    """
    commit, dirty = git if git is not None else git_info(Path(__file__).resolve().parent)
    root = Path(data_dir)
    return {
        "tool": "celegans-benchmark",
        "version": __version__,
        "git_commit": commit,
        "git_dirty": dirty,
        "python": platform.python_version(),
        "created_utc": now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {**asdict(gates), "interval_tolerance": interval_tolerance},
        "inputs": {f"{stem}.csv": sha256_file(root / f"{stem}.csv") for stem in TABLES},
        "warnings": list(warnings),
    }


def write_run_info(info: dict[str, Any], output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "run_info.json"
    path.write_text(json.dumps(info, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path
