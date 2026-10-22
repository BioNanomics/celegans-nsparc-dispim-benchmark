"""Create a private run folder from the empty CSV templates (replaces scripts/init_run.sh)."""

from __future__ import annotations

import shutil
from pathlib import Path

from .metrics import TABLES, DataError

DEFAULT_TEMPLATES = Path(__file__).resolve().parents[2] / "data" / "templates"


def init_run(run_dir: str | Path, templates_dir: str | Path | None = None) -> list[Path]:
    """Copy the template CSVs into run_dir; never overwrite existing CSVs.

    All checks run before the first file is written, so a refusal leaves
    the target untouched.
    """
    target = Path(run_dir)
    source = Path(templates_dir) if templates_dir is not None else DEFAULT_TEMPLATES
    templates = [source / f"{stem}.csv" for stem in TABLES]
    missing = [p.name for p in templates if not p.is_file()]
    if missing:
        raise DataError(f"Missing template CSVs in {source}: {', '.join(missing)}. "
                        "Pass --templates-dir if running from an installed package.")
    if target.exists() and not target.is_dir():
        raise DataError(f"{target} exists and is not a folder")
    if target.is_dir() and any(target.glob("*.csv")):
        raise DataError(f"Existing CSVs found; refusing to overwrite {target}")
    target.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(p, target / p.name)) for p in templates]
