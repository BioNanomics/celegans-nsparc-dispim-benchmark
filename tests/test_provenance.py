import contextlib
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import celegans_benchmark
from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError, Gates, TABLES
from celegans_benchmark.provenance import build_run_info, git_info

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-10-21T10:00:00+00:00"


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "private_run"
        shutil.copytree(ROOT / "examples" / "synthetic", self.path)

    def info(self, **kw):
        args = dict(gates=Gates(), interval_tolerance=0.05, warnings=[], now=STAMP,
                    git=(None, None))
        args.update(kw)
        return build_run_info(self.path, **args)

    def test_core_fields(self):
        info = self.info()
        self.assertEqual(info["version"], celegans_benchmark.__version__)
        self.assertEqual(info["created_utc"], STAMP)
        self.assertEqual(info["tool"], "celegans-benchmark")
        self.assertRegex(info["python"], r"^\d+\.\d+\.\d+")

    def test_settings_reflect_what_was_used(self):
        info = self.info(gates=Gates(recall_min=0.9, lineage_min=0.8, recall_through_cells=60),
                         interval_tolerance=0.2)
        self.assertEqual(info["settings"], {"recall_min": 0.9, "lineage_min": 0.8,
                                            "recall_through_cells": 60, "interval_tolerance": 0.2})

    def test_input_hashes_are_sha256_of_each_csv(self):
        inputs = self.info()["inputs"]
        self.assertEqual(set(inputs), {f"{stem}.csv" for stem in TABLES})
        for name, digest in inputs.items():
            self.assertEqual(digest, hashlib.sha256((self.path / name).read_bytes()).hexdigest())

    def test_changing_one_input_changes_only_its_hash(self):
        before = self.info()["inputs"]
        target = self.path / "milestones.csv"
        target.write_bytes(target.read_bytes() + b"\n# touched\n")
        after = self.info()["inputs"]
        changed = {k for k in before if before[k] != after[k]}
        self.assertEqual(changed, {"milestones.csv"})

    def test_same_inputs_same_output(self):
        self.assertEqual(self.info(), self.info())

    def test_missing_input_raises(self):
        (self.path / "lineage_qc.csv").unlink()
        with self.assertRaises(DataError):
            self.info()

    def test_empty_tables_are_hashed(self):
        for stem in TABLES:
            p = self.path / f"{stem}.csv"
            p.write_text(p.read_text().splitlines()[0] + "\n")
        self.assertEqual(len(self.info()["inputs"]), len(TABLES))

    def test_warnings_are_recorded(self):
        self.assertEqual(self.info(warnings=["SYN01: blank raw_sha256"])["warnings"],
                         ["SYN01: blank raw_sha256"])

    def test_no_private_paths_leak(self):
        text = json.dumps(self.info(), allow_nan=False)
        self.assertNotIn(str(self.path), text)
        self.assertNotIn("private_run", text)

    def test_git_fields_recorded_as_given(self):
        info = self.info(git=("a" * 40, True))
        self.assertEqual((info["git_commit"], info["git_dirty"]), ("a" * 40, True))
        info = self.info(git=(None, None))
        self.assertEqual((info["git_commit"], info["git_dirty"]), (None, None))

    # ---- git_info -------------------------------------------------------
    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_git_info_in_repo(self):
        commit, dirty = git_info(ROOT)
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertIsInstance(dirty, bool)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_git_info_outside_repo_is_unknown_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(git_info(Path(tmp)), (None, None))

    def test_git_missing_is_unknown_not_error(self):
        with mock.patch("celegans_benchmark.provenance.subprocess.run",
                        side_effect=FileNotFoundError):
            self.assertEqual(git_info(ROOT), (None, None))

    # ---- CLI -----------------------------------------------------------
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_report_writes_run_info_json(self):
        outdir = self.path / "out"
        code, out, _ = self.run_cli("report", "--data-dir", str(self.path), "--output-dir",
                                    str(outdir), "--recall-threshold", "0.9",
                                    "--interval-tolerance", "0.1")
        self.assertEqual(code, 0)
        info = json.loads((outdir / "run_info.json").read_text(encoding="utf-8"))
        self.assertEqual(info["settings"]["recall_min"], 0.9)
        self.assertEqual(info["settings"]["interval_tolerance"], 0.1)
        self.assertTrue(any(w.startswith("SYN01") for w in info["warnings"]))
        self.assertRegex(info["created_utc"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertIn("run_info.json", out)

    def test_validate_does_not_write_run_info(self):
        code, _, _ = self.run_cli("validate", "--data-dir", str(self.path))
        self.assertEqual(code, 0)
        self.assertFalse(list(self.path.rglob("run_info.json")))

    def test_failed_validation_writes_nothing(self):
        (self.path / "lineage_qc.csv").unlink()
        outdir = self.path / "out"
        code, _, _ = self.run_cli("report", "--data-dir", str(self.path), "--output-dir", str(outdir))
        self.assertEqual(code, 2)
        self.assertFalse(outdir.exists())


if __name__ == "__main__":
    unittest.main()
