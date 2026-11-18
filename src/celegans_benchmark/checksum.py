"""Streaming SHA-256 and verification of acquisition tables or raw-file manifests."""

from __future__ import annotations

import csv
import hashlib
import os
import re
import tempfile
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

from .metrics import DataError, _read

CHUNK_SIZE = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+://")
MANIFEST_FIELDS = ("file_name", "raw_data_uri", "size_bytes", "modified_utc",
                   "raw_sha256", "checksummed_utc")


def _signature(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def sha256_file(path: str | Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Hex SHA-256 of a file, read in chunks so large files are never held in memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    p = Path(path)
    if not p.is_file():
        raise DataError(f"Not a file: {p}")
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        before = os.fstat(handle.fileno())
        length = 0
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
            length += len(chunk)
        after = os.fstat(handle.fileno())
        if (length != before.st_size or _signature(before) != _signature(after)
                or _signature(after) != _signature(p.stat())):
            raise DataError(f"File changed while hashing: {p}")
    return digest.hexdigest()


def write_raw_manifest(paths: Iterable[str | Path], manifest: str | Path,
                       progress: Callable[[str], None] | None = None) -> list[dict[str, str]]:
    """Hash paths in place and publish a complete, new CSV without replacing a baseline."""
    output = Path(manifest)
    if output.exists():
        raise DataError(f"Manifest already exists: {output}; choose a new filename")
    files = sorted({Path(p).resolve(strict=True) for p in paths}, key=str)
    if not files:
        raise DataError("No files found to checksum")
    rows = []
    snapshots = []
    for index, path in enumerate(files, start=1):
        before = path.stat()
        if progress:
            progress(f"Hashing {index}/{len(files)}: {path} ({before.st_size:,} bytes)")
        digest = sha256_file(path)
        if _signature(before) != _signature(path.stat()):
            raise DataError(f"File changed while hashing: {path}")
        rows.append({
            "file_name": path.name,
            "raw_data_uri": str(path),
            "size_bytes": str(before.st_size),
            "modified_utc": datetime.fromtimestamp(before.st_mtime, timezone.utc).isoformat(),
            "raw_sha256": digest,
            "checksummed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        snapshots.append((path, _signature(before)))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        for path, signature in snapshots:
            if signature != _signature(path.stat()):
                raise DataError(f"File changed before manifest completion: {path}")
        # Publish the complete file in one step, failing if another writer created the baseline.
        os.link(temporary, output)
    except FileExistsError:
        raise DataError(f"Manifest already exists: {output}; choose a new filename") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return rows


def verify_manifest(manifest: str | Path,
                    raw_root: str | Path | None = None) -> list[dict[str, str]]:
    """Verify every local file in an inventory. Relative paths use its folder or raw_root."""
    source = Path(manifest)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise DataError(f"{source}: duplicate column names")
        required = {"raw_data_uri", "raw_sha256", "size_bytes"}
        missing = required.difference(fields)
        if missing:
            raise DataError(f"{source}: missing required columns: {', '.join(sorted(missing))}")
        rows = []
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise DataError(f"{source} line {line}: inconsistent column count")
            clean = {key: value.strip() for key, value in row.items()}
            if any(clean.values()):
                rows.append(clean)
    if not rows:
        raise DataError(f"{source}: no files to verify")
    root = Path(raw_root) if raw_root is not None else source.resolve().parent
    results = []
    for row in rows:
        uri, expected = row["raw_data_uri"], row["raw_sha256"]
        actual = ""
        error = ""
        expected_size = None
        size_text = row["size_bytes"]
        if size_text.isascii() and size_text.isdigit():
            try:
                expected_size = int(size_text)
            except ValueError:
                pass
        if not _SHA256.fullmatch(expected):
            status = "invalid_hash"
        elif expected_size is None:
            status = "invalid_size"
        elif _SCHEME.match(uri):
            status = "unsupported_uri"
        else:
            path = Path(uri)
            if not path.is_absolute():
                path = root / path
            try:
                if not uri or not path.is_file():
                    status = "missing"
                elif path.stat().st_size != expected_size:
                    status = "mismatch"
                else:
                    actual = sha256_file(path)
                    status = "ok" if actual == expected.lower() else "mismatch"
            except DataError as exc:
                status, error = "changed", str(exc)
            except OSError as exc:
                status, error = "unreadable", str(exc)
        results.append({"raw_data_uri": uri, "status": status,
                        "actual_sha256": actual, "error": error})
    return results


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
