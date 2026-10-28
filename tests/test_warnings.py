import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.cli import main
from celegans_benchmark.metrics import TABLES, acquisition_warnings, load_data

HEADER = ("embryo_id,group,strain,reporter,temperature_c,power_at_sample_mw,"
          "nsparc_mode,planned_interval_s,measured_interval_s,recorded_volumes,raw_sha256\n")
FULL = "e1,NSPARC_60s,BV514,mCherry,20,1.2,processed,60,60,3,%s\n" % ("a" * 64)


class WarningTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        self.write(FULL)

    def write(self, *rows, header=HEADER):
        (self.path / "acquisitions.csv").write_text(header + "".join(rows))
        for stem, cols in TABLES.items():
            if stem != "acquisitions":
                (self.path / f"{stem}.csv").write_text(",".join(sorted(cols)) + "\n")

    def warnings(self):
        return load_data(self.path).warnings

    def test_complete_row_has_no_warnings(self):
        self.assertEqual(self.warnings(), [])

    def test_each_blank_field_warns(self):
        for blank, text in (("power_at_sample_mw", "e1,NSPARC_60s,BV514,mCherry,20,,processed,60,60,3,%s\n"),
                            ("nsparc_mode", "e1,NSPARC_60s,BV514,mCherry,20,1.2,,60,60,3,%s\n")):
            self.write(text % ("a" * 64))
            got = self.warnings()
            self.assertEqual(len(got), 1, blank)
            self.assertIn(blank, got[0])
            self.assertIn("e1", got[0])
        self.write("e1,NSPARC_60s,BV514,mCherry,20,1.2,processed,60,60,3,\n")
        self.assertIn("raw_sha256", self.warnings()[0])

    def test_several_blank_fields_one_warning_per_embryo(self):
        self.write("e1,NSPARC_60s,BV514,mCherry,20,,,60,60,3,\n")
        got = self.warnings()
        self.assertEqual(len(got), 1)
        for field in ("power_at_sample_mw", "nsparc_mode", "raw_sha256"):
            self.assertIn(field, got[0])

    def test_control_rows_are_skipped(self):
        self.write("c1,CONTROL,BV514,mCherry,20,,,,,0,\n")
        self.assertEqual(self.warnings(), [])

    def test_whitespace_only_counts_as_blank(self):
        self.write("e1,NSPARC_60s,BV514,mCherry,20,   ,processed,60,60,3,%s\n" % ("a" * 64))
        self.assertIn("power_at_sample_mw", self.warnings()[0])

    def test_zero_power_is_a_value_not_blank(self):
        self.write("e1,NSPARC_60s,BV514,mCherry,20,0,processed,60,60,3,%s\n" % ("a" * 64))
        self.assertEqual(self.warnings(), [])

    def test_absent_column_warns_instead_of_crashing(self):
        header = "embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
        self.write("e1,NSPARC_60s,BV514,mCherry,20,60,60,3\n", header=header)
        self.assertIn("raw_sha256", self.warnings()[0])

    def test_no_embryos_no_warnings(self):
        self.write()
        self.assertEqual(self.warnings(), [])
        self.assertEqual(acquisition_warnings([]), [])

    def test_warnings_keep_order_of_rows(self):
        self.write("e2,NSPARC_60s,BV514,mCherry,20,,processed,60,60,3,%s\n" % ("a" * 64),
                   "e1,NSPARC_180s,BV514,mCherry,20,,processed,180,180,3,%s\n" % ("a" * 64))
        got = self.warnings()
        self.assertTrue(got[0].startswith("e2:"))
        self.assertTrue(got[1].startswith("e1:"))

    def test_cli_prints_warnings_to_stderr_and_still_succeeds(self):
        self.write("e1,NSPARC_60s,BV514,mCherry,20,,processed,60,60,3,\n")
        for command in (["validate"], ["report", "--output-dir", str(self.path / "out")]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(command + ["--data-dir", str(self.path)])
            self.assertEqual(code, 0)
            self.assertIn("WARNING", err.getvalue())
            self.assertIn("power_at_sample_mw", err.getvalue())
            self.assertNotIn("WARNING", out.getvalue())

    def test_cli_silent_when_complete(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            main(["validate", "--data-dir", str(self.path)])
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
