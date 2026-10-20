import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.checksum import sha256_file, verify_raw
from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError

ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
HEADER = "embryo_id,group,raw_data_uri,raw_sha256\n"


class Sha256FileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_known_value(self):
        f = self.root / "a.bin"
        f.write_bytes(b"abc")
        self.assertEqual(sha256_file(f), ABC)

    def test_empty_file(self):
        f = self.root / "empty.bin"
        f.write_bytes(b"")
        self.assertEqual(sha256_file(f), EMPTY)

    def test_chunk_boundaries_give_same_hash(self):
        for size in (0, 1, 7, 8, 9, 16, 1000):
            data = bytes(range(256)) * 4
            data = data[:size]
            f = self.root / f"f{size}.bin"
            f.write_bytes(data)
            self.assertEqual(sha256_file(f, chunk_size=8),
                             hashlib.sha256(data).hexdigest(), size)

    def test_missing_file_and_folder_rejected(self):
        with self.assertRaisesRegex(DataError, "Not a file"):
            sha256_file(self.root / "nope.bin")
        with self.assertRaisesRegex(DataError, "Not a file"):
            sha256_file(self.root)

    def test_bad_chunk_size(self):
        f = self.root / "a.bin"
        f.write_bytes(b"abc")
        with self.assertRaises(ValueError):
            sha256_file(f, chunk_size=0)


class VerifyRawTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "raw").mkdir()
        self.raw = self.root / "raw" / "e1.nd2"
        self.raw.write_bytes(b"abc")

    def _acq(self, *rows):
        (self.root / "acquisitions.csv").write_text(HEADER + "".join(r + "\n" for r in rows))

    def _status(self, **kw):
        return {r["embryo_id"]: r["status"] for r in verify_raw(self.root, **kw)}

    def test_ok(self):
        self._acq(f"e1,NSPARC_60s,{self.raw},{ABC}")
        self.assertEqual(self._status(), {"e1": "ok"})

    def test_uppercase_hash_accepted(self):
        self._acq(f"e1,NSPARC_60s,{self.raw},{ABC.upper()}")
        self.assertEqual(self._status(), {"e1": "ok"})

    def test_mismatch(self):
        self._acq(f"e1,NSPARC_60s,{self.raw},{EMPTY}")
        self.assertEqual(self._status(), {"e1": "mismatch"})

    def test_missing_file(self):
        self._acq(f"e1,NSPARC_60s,{self.root / 'gone.nd2'},{ABC}")
        self.assertEqual(self._status(), {"e1": "missing"})

    def test_blank_fields_are_not_recorded_not_failure(self):
        self._acq(f"e1,NSPARC_60s,{self.raw},", "e2,NSPARC_60s,,", f"e3,NSPARC_60s,,{ABC}")
        self.assertEqual(self._status(),
                         {"e1": "not_recorded", "e2": "not_recorded", "e3": "not_recorded"})

    def test_invalid_hash_format(self):
        self._acq(f"e1,NSPARC_60s,{self.raw},notahash")
        self.assertEqual(self._status(), {"e1": "invalid_hash"})

    def test_control_rows_skipped(self):
        self._acq(f"c1,CONTROL,{self.raw},{EMPTY}")
        self.assertEqual(self._status(), {"c1": "skipped_control"})

    def test_remote_uri_skipped(self):
        self._acq(f"e1,NSPARC_60s,s3://bucket/e1.nd2,{ABC}")
        self.assertEqual(self._status(), {"e1": "skipped_remote"})

    def test_relative_uri_uses_raw_root(self):
        self._acq(f"e1,NSPARC_60s,e1.nd2,{ABC}")
        self.assertEqual(self._status(raw_root=self.root / "raw"), {"e1": "ok"})
        self.assertEqual(self._status(raw_root=self.root), {"e1": "missing"})

    def test_no_embryos(self):
        self._acq()
        self.assertEqual(verify_raw(self.root), [])

    def test_missing_columns_or_file(self):
        (self.root / "acquisitions.csv").write_text("embryo_id,group\ne1,NSPARC_60s\n")
        with self.assertRaisesRegex(DataError, "raw_sha256"):
            verify_raw(self.root)
        (self.root / "acquisitions.csv").unlink()
        with self.assertRaisesRegex(DataError, "Missing required CSV"):
            verify_raw(self.root)

    def test_cli(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code_hash = main(["checksum", "--file", str(self.raw)])
            self._acq(f"e1,NSPARC_60s,{self.raw},{ABC}")
            code_ok = main(["verify-raw", "--data-dir", str(self.root)])
            self._acq(f"e1,NSPARC_60s,{self.raw},{EMPTY}")
            code_bad = main(["verify-raw", "--data-dir", str(self.root)])
            self._acq(f"e1,NSPARC_60s,{self.raw},")
            code_unknown = main(["verify-raw", "--data-dir", str(self.root)])
        self.assertIn(ABC, out.getvalue())
        self.assertEqual((code_hash, code_ok, code_bad, code_unknown), (0, 0, 1, 0))


if __name__ == "__main__":
    unittest.main()
