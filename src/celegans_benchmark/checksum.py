"""SHA-256 helper for large raw files, with optional verification against acquisitions.csv."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .metrics import DataError, _read

CHUNK_SIZE = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+://")


def sha256_file(path: str | Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Hex SHA-256 of a file, read in chunks so large files are never held in memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    p = Path(path)
    if not p.is_file():
        raise DataError(f"Not a file: {p}")
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def verify_raw(data_dir: str | Path, raw_root: str | Path | None = None) -> list[dict[str, str]]:
    """Compare each acquisition's raw_sha256 with the file at raw_data_uri.

    Status per embryo: ok, mismatch, missing, invalid_hash, not_recorded
    (blank URI or hash = unknown, not a failure), skipped_control, skipped_remote.
    """
    rows = _read(Path(data_dir) / "acquisitions.csv",
                 {"embryo_id", "group", "raw_data_uri", "raw_sha256"})
    results: list[dict[str, str]] = []
    for r in rows:
        uri, expected = r["raw_data_uri"], r["raw_sha256"]
        if r["group"] == "CONTROL":
            status = "skipped_control"
        elif not uri or not expected:
            status = "not_recorded"
        elif _SCHEME.match(uri):
            status = "skipped_remote"
        elif not _SHA256.fullmatch(expected):
            status = "invalid_hash"
        else:
            path = Path(uri)
            if not path.is_absolute() and raw_root is not None:
                path = Path(raw_root) / path
            if not path.is_file():
                status = "missing"
            else:
                status = "ok" if sha256_file(path) == expected.lower() else "mismatch"
        results.append({"embryo_id": r["embryo_id"], "status": status, "raw_data_uri": uri})
    return results
