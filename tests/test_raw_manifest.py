"""Raw-inventory CLI regressions; all files are isolated temporary fixtures."""

import contextlib
import csv
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from celegans_benchmark import checksum
from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError


ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
FIELDS = ("file_name", "raw_data_uri", "size_bytes", "modified_utc",
          "raw_sha256", "checksummed_utc")


class RawManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.source = self.raw / "worm, one.nd2"
        self.source.write_bytes(b"abc")
        self.out = self.root / "inventory" / "raw.csv"

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main([str(arg) for arg in args])
        return result, stdout.getvalue(), stderr.getvalue()

    def write_manifest(self, *rows, fields=FIELDS):
        self.out.parent.mkdir(exist_ok=True)
        with self.out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return self.out

    def row(self, path=None, **changes):
        value = {"file_name": self.source.name,
                 "raw_data_uri": str(self.source if path is None else path),
                 "size_bytes": "3", "modified_utc": "", "raw_sha256": ABC,
                 "checksummed_utc": ""}
        value.update(changes)
        return value

    def read_manifest(self):
        with self.out.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_directory_cli_known_digest_and_manifest_roundtrip(self):
        before = self.source.read_bytes(), self.source.stat().st_mtime_ns
        code, stdout, _ = self.cli("checksum", "--directory", self.raw,
                                   "--manifest", self.out)
        self.assertEqual(code, 0)
        self.assertIn("1 file(s)", stdout)
        rows = self.read_manifest()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), set(FIELDS))
        self.assertEqual(rows[0]["file_name"], "worm, one.nd2")
        self.assertEqual(rows[0]["raw_data_uri"], str(self.source.resolve()))
        self.assertEqual(rows[0]["raw_sha256"], ABC)
        self.assertEqual(rows[0]["size_bytes"], "3")
        self.assertTrue(rows[0]["modified_utc"])
        self.assertTrue(rows[0]["checksummed_utc"])
        self.assertEqual((self.source.read_bytes(), self.source.stat().st_mtime_ns), before)
        code, stdout, _ = self.cli("verify-raw", "--manifest", self.out)
        self.assertEqual(code, 0)
        self.assertIn("1/1 file(s) verified", stdout)

    def test_repeat_directories_recursive_overlap_deduplicated(self):
        nested = self.raw / "nested"
        nested.mkdir()
        (nested / "second.ND2").write_bytes(b"")
        (nested / "ignored.txt").write_bytes(b"ignored")
        code, _, _ = self.cli("checksum", "--directory", self.raw,
                              "--directory", nested, "--directory", self.raw,
                              "--recursive", "--manifest", self.out)
        self.assertEqual(code, 0)
        rows = self.read_manifest()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["raw_data_uri"] for row in rows}), 2)
        self.assertEqual({row["raw_sha256"] for row in rows}, {ABC, EMPTY})

    def test_nonrecursive_directory_does_not_read_nested_files(self):
        nested = self.raw / "nested"
        nested.mkdir()
        (nested / "other.nd2").write_bytes(b"other")
        code, _, _ = self.cli("checksum", "--directory", self.raw, "--manifest", self.out)
        self.assertEqual(code, 0)
        self.assertEqual([r["file_name"] for r in self.read_manifest()], [self.source.name])

    def test_legacy_file_cli_and_single_file_manifest_remain_available(self):
        code, stdout, _ = self.cli("checksum", "--file", self.source)
        self.assertEqual(code, 0)
        self.assertIn(ABC, stdout)
        code, _, _ = self.cli("checksum", "--file", self.source, "--manifest", self.out)
        self.assertEqual(code, 0)
        self.assertEqual(self.read_manifest()[0]["raw_sha256"], ABC)

    def test_existing_manifest_is_never_replaced(self):
        self.out.parent.mkdir()
        self.out.write_bytes(b"baseline must be kept\n")
        with patch.object(checksum, "sha256_file") as hashing:
            code, _, stderr = self.cli("checksum", "--directory", self.raw,
                                       "--manifest", self.out)
        self.assertEqual(code, 2)
        self.assertIn("already exists", stderr)
        hashing.assert_not_called()
        self.assertEqual(self.out.read_bytes(), b"baseline must be kept\n")

    def test_hash_failure_does_not_publish_partial_manifest_or_retry(self):
        (self.raw / "z.nd2").write_bytes(b"last")
        self.out.parent.mkdir()
        with patch.object(checksum, "sha256_file",
                          side_effect=[ABC, PermissionError("fixture denied")]) as hashing:
            code, _, stderr = self.cli("checksum", "--directory", self.raw,
                                       "--manifest", self.out)
        self.assertEqual(code, 2)
        self.assertIn("fixture denied", stderr)
        self.assertEqual(hashing.call_count, 2)
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.out.parent.iterdir()), [])

    def test_no_overwrite_even_if_output_appears_at_publication(self):
        self.out.parent.mkdir()
        real_link = os.link

        def racing_link(source, destination, *args, **kwargs):
            Path(destination).write_bytes(b"other writer\n")
            return real_link(source, destination, *args, **kwargs)

        with patch.object(checksum.os, "link", side_effect=racing_link):
            code, _, _ = self.cli("checksum", "--file", self.source, "--manifest", self.out)
        self.assertEqual(code, 2)
        self.assertEqual(self.out.read_bytes(), b"other writer\n")
        self.assertEqual(list(self.out.parent.iterdir()), [self.out])

    def test_source_changed_while_csv_is_staged_is_not_published(self):
        self.out.parent.mkdir()
        real_fsync = os.fsync

        def flush_then_change_source(descriptor):
            real_fsync(descriptor)
            self.source.write_bytes(b"changed after hashing, while staging CSV")

        with patch.object(checksum.os, "fsync", side_effect=flush_then_change_source) as flush, \
                patch.object(checksum.os, "link") as publish:
            code, _, stderr = self.cli("checksum", "--directory", self.raw,
                                       "--manifest", self.out)
        self.assertEqual(code, 2)
        self.assertIn("changed before manifest completion", stderr)
        flush.assert_called_once()
        publish.assert_not_called()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.out.parent.iterdir()), [])

    def test_earlier_file_changed_before_inventory_finishes_is_rejected(self):
        later = self.raw / "z.nd2"
        later.write_bytes(b"later")
        self.out.parent.mkdir()
        real_hash = checksum.sha256_file

        def hash_then_mutate_previous(path):
            digest = real_hash(path)
            if Path(path) == later.resolve():
                self.source.write_bytes(b"changed")
            return digest

        with patch.object(checksum, "sha256_file", side_effect=hash_then_mutate_previous):
            code, _, stderr = self.cli("checksum", "--directory", self.raw,
                                       "--manifest", self.out)
        self.assertEqual(code, 2)
        self.assertIn("changed before manifest completion", stderr)
        self.assertFalse(self.out.exists())

    def test_fd_signature_change_rejects_digest_even_for_same_length(self):
        stat = self.source.stat()
        changed = SimpleNamespace(st_dev=stat.st_dev, st_ino=stat.st_ino,
                                  st_size=stat.st_size, st_mtime_ns=stat.st_mtime_ns + 1,
                                  st_ctime_ns=stat.st_ctime_ns)
        with patch.object(checksum.os, "fstat", side_effect=[stat, changed]):
            with self.assertRaisesRegex(DataError, "changed while hashing"):
                checksum.sha256_file(self.source)

    def test_path_identity_change_rejects_digest_with_stable_descriptor(self):
        stat = self.source.stat()
        changed = SimpleNamespace(st_dev=stat.st_dev, st_ino=stat.st_ino + 1,
                                  st_size=stat.st_size, st_mtime_ns=stat.st_mtime_ns,
                                  st_ctime_ns=stat.st_ctime_ns)
        # Path.is_file() performs the first stat; the final path lookup must still
        # refer to the file whose descriptor supplied the bytes.
        with patch.object(checksum.os, "fstat", return_value=stat), \
                patch.object(Path, "stat", side_effect=[stat, changed]):
            with self.assertRaisesRegex(DataError, "changed while hashing"):
                checksum.sha256_file(self.source)

    def test_growth_during_read_is_not_reported_as_a_digest(self):
        real_open = Path.open
        target = self.source

        class GrowingReader:
            def __init__(self, handle):
                self.handle = handle
                self.changed = False

            def __enter__(self):
                self.handle.__enter__()
                return self

            def __exit__(self, *args):
                return self.handle.__exit__(*args)

            def fileno(self):
                return self.handle.fileno()

            def read(self, size):
                value = self.handle.read(size)
                if value and not self.changed:
                    self.changed = True
                    with real_open(target, "ab") as writer:
                        writer.write(b"d")
                return value

        def open_source(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            return GrowingReader(handle) if path == target and args == ("rb",) else handle

        with patch.object(Path, "open", open_source):
            with self.assertRaisesRegex(DataError, "changed while hashing"):
                checksum.sha256_file(target, chunk_size=2)
        self.assertEqual(target.read_bytes(), b"abcd")

    def test_strict_manifest_statuses_are_failures_and_not_skips(self):
        self.write_manifest(
            self.row(self.raw / "missing.nd2"),
            self.row(raw_sha256=EMPTY),
            self.row(size_bytes="4"),
            self.row(raw_sha256="not-sha256"),
            self.row(raw_sha256=""),
            self.row(""),
            self.row("s3://bucket/worm.nd2"),
            self.row(self.source.as_uri()),
            self.row(size_bytes="-1"),
            self.row(size_bytes="３"),
            self.row(raw_sha256=ABC.upper()),
        )
        statuses = [row["status"] for row in checksum.verify_manifest(self.out)]
        self.assertEqual(statuses, ["missing", "mismatch", "mismatch", "invalid_hash",
                                    "invalid_hash", "missing", "unsupported_uri",
                                    "unsupported_uri", "invalid_size", "invalid_size", "ok"])
        code, stdout, _ = self.cli("verify-raw", "--manifest", self.out)
        self.assertEqual(code, 1)
        self.assertIn("1/11 file(s) verified", stdout)

    def test_relative_manifest_paths_use_manifest_folder_or_raw_root(self):
        self.write_manifest(self.row(Path("..") / "raw" / self.source.name))
        self.assertEqual(checksum.verify_manifest(self.out)[0]["status"], "ok")
        self.write_manifest(self.row(self.source.name))
        self.assertEqual(checksum.verify_manifest(self.out)[0]["status"], "missing")
        code, stdout, _ = self.cli("verify-raw", "--manifest", self.out,
                                  "--raw-root", self.raw)
        self.assertEqual(code, 0)
        self.assertIn("1/1 file(s) verified", stdout)

    @unittest.skipUnless(hasattr(sys, "set_int_max_str_digits"),
                         "Python has no integer-string conversion limit")
    def test_oversized_integer_size_is_invalid_and_verification_continues(self):
        previous_limit = sys.get_int_max_str_digits()
        self.addCleanup(sys.set_int_max_str_digits, previous_limit)
        sys.set_int_max_str_digits(640)
        self.write_manifest(self.row(size_bytes="9" * 1000), self.row())
        results = checksum.verify_manifest(self.out)
        self.assertEqual([r["status"] for r in results], ["invalid_size", "ok"])
        self.assertEqual(results[0]["actual_sha256"], "")
        code, stdout, _ = self.cli("verify-raw", "--manifest", self.out)
        self.assertEqual(code, 1)
        self.assertIn("1/2 file(s) verified", stdout)

    def test_file_errors_continue_but_command_is_unsuccessful(self):
        paths = [self.raw / (name + ".nd2") for name in ("denied", "changing", "good")]
        for path in paths:
            path.write_bytes(b"abc")
        self.write_manifest(*(self.row(path) for path in paths))
        called = []

        def failures(path):
            called.append(Path(path).name)
            if Path(path).stem == "denied":
                raise PermissionError("fixture denied")
            if Path(path).stem == "changing":
                raise DataError("fixture file changed")
            return ABC

        with patch.object(checksum, "sha256_file", side_effect=failures):
            rows = checksum.verify_manifest(self.out)
        self.assertEqual([r["status"] for r in rows], ["unreadable", "changed", "ok"])
        self.assertEqual([r["actual_sha256"] for r in rows], ["", "", ABC])
        self.assertEqual(called, [path.name for path in paths])
        with patch.object(checksum, "sha256_file", side_effect=failures):
            code, stdout, stderr = self.cli("verify-raw", "--manifest", self.out)
        self.assertEqual(code, 1)
        self.assertIn("1/3 file(s) verified", stdout)
        self.assertIn("fixture denied", stderr)
        self.assertIn("fixture file changed", stderr)

    def test_invalid_manifest_structure_and_empty_inventory_are_errors(self):
        self.out.parent.mkdir()
        for contents in (
            "raw_data_uri,raw_sha256\n",
            "raw_data_uri,raw_sha256,size_bytes,size_bytes\n",
            "raw_data_uri,raw_sha256,size_bytes\n",
            "raw_data_uri,raw_sha256,size_bytes\n,,\n",
            "raw_data_uri,raw_sha256,size_bytes\na,b\n",
            "raw_data_uri,raw_sha256,size_bytes\na,b,1,extra\n",
        ):
            with self.subTest(contents=contents):
                self.out.write_text(contents, encoding="utf-8")
                code, _, stderr = self.cli("verify-raw", "--manifest", self.out)
                self.assertEqual(code, 2)
                self.assertIn("ERROR:", stderr)

    def test_empty_or_missing_directory_produces_no_manifest(self):
        for path in (self.root / "absent", self.root / "empty"):
            if path.name == "empty":
                path.mkdir()
            with self.subTest(path=path):
                code, _, _ = self.cli("checksum", "--directory", path,
                                      "--manifest", self.out)
                self.assertEqual(code, 2)
                self.assertFalse(self.out.exists())

    def test_required_source_and_manifest_flags_are_enforced(self):
        for args in (
            ("checksum", "--directory", self.raw),
            ("checksum", "--file", self.source, "--recursive"),
            ("checksum", "--file", self.source, "--directory", self.raw),
            ("verify-raw", "--manifest", self.out, "--data-dir", self.raw),
        ):
            with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                self.cli(*args)
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
