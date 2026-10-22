"""Regression tests for issues found in the v0.2 code review."""

import shutil
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.metrics import DataError, load_data, summarize

ROOT = Path(__file__).resolve().parents[1]


class IntegerFieldFormsTests(unittest.TestCase):
    """Whole numbers written as '1.0' or '01' must not crash or split one frame in two."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "run"
        shutil.copytree(ROOT / "examples" / "synthetic", self.path)
        self.nuc = self.path / "nuclei_qc.csv"
        self.original = self.nuc.read_text(encoding="utf-8")
        self.first_row = self.original.splitlines()[1]

    def set_first_row(self, row):
        lines = self.original.splitlines()
        lines[1] = row
        self.nuc.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_float_style_integers_are_accepted_and_reported(self):
        eid, vol, t, manual, tp, fp, fn, region = self.first_row.split(",")
        self.set_first_row(",".join([eid, vol + ".0", t, manual + ".0", tp + ".0", fp + ".0",
                                     fn + ".0", region]))
        baseline = summarize(load_data(self.path))
        self.nuc.write_text(self.original, encoding="utf-8")
        self.assertEqual(summarize(load_data(self.path)), baseline)

    def test_leading_zero_is_the_same_frame(self):
        eid, vol, *rest = self.first_row.split(",")
        self.nuc.write_text(self.original + ",".join([eid, "0" + vol, *rest]) + "\n",
                            encoding="utf-8")
        with self.assertRaisesRegex(DataError, "duplicate"):
            load_data(self.path)

    def test_fractions_still_rejected(self):
        eid, vol, *rest = self.first_row.split(",")
        self.set_first_row(",".join([eid, vol + ".5", *rest]))
        with self.assertRaisesRegex(DataError, "integer"):
            load_data(self.path)

    def test_lineage_and_volume_counts_normalized(self):
        lin = self.path / "lineage_qc.csv"
        lines = lin.read_text(encoding="utf-8").splitlines()
        parts = lines[1].split(",")
        parts[3] += ".0"
        lines[1] = ",".join(parts)
        lin.write_text("\n".join(lines) + "\n", encoding="utf-8")
        acq = self.path / "acquisitions.csv"
        acq.write_text(acq.read_text(encoding="utf-8").replace(",3,,", ",3.0,,", 1), encoding="utf-8")
        report = summarize(load_data(self.path))
        self.assertTrue(report["lineage_stage_qc"])


class SpotCountReadingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "counts.txt"

    def test_spaces_around_header_names(self):
        from celegans_benchmark.audit import read_spot_counts
        self.file.write_text(" time_point , spots \n0,4\n1, 6 \n", encoding="utf-8")
        self.assertEqual(read_spot_counts(self.file), ({0: 4, 1: 6}, []))

    def test_error_names_the_real_file_line(self):
        from celegans_benchmark.audit import read_spot_counts
        self.file.write_text("# a\n# b\n\ntime_point,spots\n0,4\n1,x\n", encoding="utf-8")
        with self.assertRaisesRegex(DataError, "line 6"):
            read_spot_counts(self.file)


class FirstTimePointTests(unittest.TestCase):
    """Trackers such as StarryNite/AceTree number time points from 1; volume_index is 0-based."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.counts = self.root / "counts.txt"
        self.counts.write_text("time_point,spots\n1,4\n2,6\n3,20\n", encoding="utf-8")
        (self.root / "acquisitions.csv").write_text(
            "embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
            "e1,NSPARC_60s,BV514,mCherry,20,60,60,10\n")
        (self.root / "embryo_outcomes.csv").write_text(
            "embryo_id,hatched,hatch_t_min,abnormal_development,excluded,exclusion_reason\n")
        (self.root / "nuclei_qc.csv").write_text(
            "embryo_id,volume_index,t_min,manual_cell_count,tp,fp,fn,depth_region\n"
            "e1,0,0,4,4,0,0,all\ne1,1,1,6,6,0,0,all\n")
        (self.root / "lineage_qc.csv").write_text(
            "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n")
        (self.root / "milestones.csv").write_text("embryo_id,milestone,t_min\n")

    def test_check_audit_with_one_based_tracker(self):
        from celegans_benchmark.audit import check_audit
        zero = [r["status"] for r in check_audit(self.root, "e1", self.counts)]
        one = [r["status"] for r in check_audit(self.root, "e1", self.counts, first_time_point=1)]
        self.assertEqual(zero, ["not_checkable", "mismatch"])   # wrong alignment
        self.assertEqual(one, ["ok", "ok"])

    def test_select_frames_reports_both_numbers(self):
        from celegans_benchmark.audit import select_frames
        rows = select_frames({1: 4, 2: 60}, per_stage=1, seed=0, first_time_point=1)
        self.assertEqual([(r["time_point"], r["volume_index"]) for r in rows], [(1, 0), (2, 1)])

    def test_time_point_before_first_is_rejected(self):
        from celegans_benchmark.audit import select_frames
        with self.assertRaisesRegex(DataError, "first_time_point"):
            select_frames({0: 4}, per_stage=1, seed=0, first_time_point=1)

    def test_negative_first_time_point_rejected(self):
        from celegans_benchmark.audit import select_frames
        with self.assertRaises(DataError):
            select_frames({0: 4}, per_stage=1, seed=0, first_time_point=-1)

    def test_cli_option(self):
        import contextlib, io
        from celegans_benchmark.cli import main
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = main(["check-audit", "--data-dir", str(self.root), "--embryo-id", "e1",
                         "--spot-counts", str(self.counts), "--first-time-point", "1"])
            sel = main(["select-frames", "--spot-counts", str(self.counts), "--output",
                        str(self.root / "f.csv"), "--first-time-point", "1"])
        self.assertEqual((code, sel), (0, 0))
        self.assertIn("volume_index", (self.root / "f.csv").read_text(encoding="utf-8"))


class FrozenListWriteTests(unittest.TestCase):
    def test_write_uses_exclusive_create(self):
        from unittest import mock
        from celegans_benchmark.audit import write_selection
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f.csv"
            real_open = Path.open
            modes = []

            def spy(self, mode="r", *args, **kwargs):
                modes.append(mode)
                return real_open(self, mode, *args, **kwargs)

            with mock.patch.object(Path, "open", spy):
                write_selection([{"time_point": 0, "volume_index": 0, "estimated_spots": 4,
                                  "stage": "<16"}], out)
            self.assertIn("x", modes)


class VerifyRawInvalidHashTests(unittest.TestCase):
    def test_invalid_hash_exits_nonzero(self):
        import contextlib, io
        from celegans_benchmark.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "e1.nd2"
            raw.write_bytes(b"abc")
            (root / "acquisitions.csv").write_text(
                f"embryo_id,group,raw_data_uri,raw_sha256\ne1,NSPARC_60s,{raw},{'a' * 63}\n")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = main(["verify-raw", "--data-dir", str(root)])
            self.assertIn("invalid_hash", out.getvalue())
            self.assertEqual(code, 1)


class AutoLabelTests(unittest.TestCase):
    """The FABRICATED banner follows the data (acquisitions notes), not words in the path."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def make(self, folder, notes):
        d = self.root / folder
        d.mkdir(parents=True)
        (d / "acquisitions.csv").write_text(f"embryo_id,group,notes\ne1,NSPARC_60s,{notes}\n")
        return d

    def test_real_data_in_a_folder_named_synthetic_is_not_labeled(self):
        from celegans_benchmark.summary import auto_label
        self.assertIsNone(auto_label(self.make("synthetic_lethality/run3", "pilot day 1"), None))

    def test_fabricated_data_is_labeled_wherever_it_lives(self):
        from celegans_benchmark.summary import auto_label
        self.assertIn("FABRICATED", auto_label(self.make("anything", "FABRICATED DEMO ONLY"), None))
        self.assertIn("FABRICATED", auto_label(ROOT / "examples" / "synthetic", None))

    def test_relative_dot_inside_example_folder(self):
        import os
        from celegans_benchmark.summary import auto_label
        here = os.getcwd()
        try:
            os.chdir(ROOT / "examples" / "synthetic")
            self.assertIn("FABRICATED", auto_label(".", None))
        finally:
            os.chdir(here)

    def test_explicit_label_wins_and_missing_files_are_no_label(self):
        from celegans_benchmark.summary import auto_label
        self.assertEqual(auto_label(self.make("x", "FABRICATED"), "PRACTICE DATA"), "PRACTICE DATA")
        self.assertIsNone(auto_label(self.root / "does_not_exist", None))
        d = self.root / "nonotes"
        d.mkdir()
        (d / "acquisitions.csv").write_text("embryo_id,group\ne1,NSPARC_60s\n")
        self.assertIsNone(auto_label(d, None))


class StaleReportFilesTests(unittest.TestCase):
    def test_rerun_removes_tables_that_are_now_empty(self):
        import contextlib, io
        from celegans_benchmark.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "run"
            shutil.copytree(ROOT / "examples" / "synthetic", data)
            out = Path(tmp) / "out"
            nuc = data / "nuclei_qc.csv"
            original = nuc.read_text(encoding="utf-8")
            row = original.splitlines()[1].split(",")
            near = ",".join(row[:3] + [str(int(row[3])), row[4], row[5], row[6], "near"])
            far = ",".join(row[:3] + ["0", "0", "0", "0", "far"])
            lines = original.splitlines()
            lines[1:2] = [near, far]
            nuc.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["report", "--data-dir", str(data), "--output-dir", str(out)]), 0)
                self.assertTrue((out / "depth_qc.csv").exists())
                (data / "lineage_qc.csv").write_text(
                    "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n")
                self.assertEqual(main(["report", "--data-dir", str(data), "--output-dir", str(out)]), 0)
            self.assertFalse((out / "lineage_stage_qc.csv").exists())
            (out / "notes_by_me.csv").write_text("keep\n")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                main(["report", "--data-dir", str(data), "--output-dir", str(out)])
            self.assertTrue((out / "notes_by_me.csv").exists())   # never delete files we did not write


if __name__ == "__main__":
    unittest.main()
