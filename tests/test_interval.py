import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError, TABLES, load_data

HEADER = ("embryo_id,group,strain,reporter,temperature_c,power_at_sample_mw,"
          "nsparc_mode,planned_interval_s,measured_interval_s,recorded_volumes,raw_sha256\n")
SHA = "a" * 64


def acq(eid="e1", group="NSPARC_60s", planned="60", measured="60"):
    return f"{eid},{group},BV514,mCherry,20,1.2,processed,{planned},{measured},3,{SHA}\n"


class IntervalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)

    def write(self, *rows):
        (self.path / "acquisitions.csv").write_text(HEADER + "".join(rows))
        for stem, cols in TABLES.items():
            if stem != "acquisitions":
                (self.path / f"{stem}.csv").write_text(",".join(sorted(cols)) + "\n")

    def warnings(self, *rows, **kw):
        self.write(*rows)
        return load_data(self.path, **kw).warnings

    def test_on_schedule_and_within_tolerance_silent(self):
        self.assertEqual(self.warnings(acq(measured="60"), acq("e2", measured="62.9")), [])

    def test_exactly_at_tolerance_is_not_flagged(self):
        self.assertEqual(self.warnings(acq(measured="63")), [])  # 60 s + 5%
        self.assertEqual(self.warnings(acq("e2", "NSPARC_180s", "180", "189")), [])

    def test_just_over_tolerance_is_flagged(self):
        got = self.warnings(acq(measured="63.1"))
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("e1:"))
        for text in ("63.1", "60", "5%"):
            self.assertIn(text, got[0])

    def test_much_slower_flagged(self):
        got = self.warnings(acq(measured="95"))
        self.assertIn("interval", got[0])

    def test_faster_than_planned_not_flagged(self):
        self.assertEqual(self.warnings(acq(measured="40")), [])

    def test_blank_intervals_are_unknown_not_flagged(self):
        self.assertEqual(self.warnings(acq(planned="", measured="500"),
                                       acq("e2", planned="60", measured="")), [])

    def test_control_rows_skipped(self):
        self.assertEqual(self.warnings("c1,CONTROL,BV514,mCherry,20,,,60,500,0,\n"), [])

    def test_tolerance_is_configurable(self):
        rows = (acq(measured="66"),)  # 10% over
        self.assertEqual(len(self.warnings(*rows)), 1)
        self.assertEqual(self.warnings(*rows, interval_tolerance=0.10), [])
        self.assertEqual(len(self.warnings(acq(measured="60.5"), interval_tolerance=0)), 1)
        self.assertEqual(self.warnings(acq(measured="60"), interval_tolerance=0), [])

    def test_invalid_tolerance_rejected(self):
        self.write(acq())
        for bad in (-0.1, float("nan"), float("inf")):
            with self.assertRaises(DataError, msg=str(bad)):
                load_data(self.path, interval_tolerance=bad)

    def test_one_warning_per_embryo_and_independent_of_blank_field_warning(self):
        self.write("e1,NSPARC_60s,BV514,mCherry,20,,processed,60,90,3,%s\n" % SHA)
        got = load_data(self.path).warnings
        self.assertEqual(len(got), 2)
        self.assertTrue(any("power_at_sample_mw" in w for w in got))
        self.assertTrue(any("interval" in w for w in got))

    def test_cli_option_and_exit_code(self):
        self.write(acq(measured="66"))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            default = main(["validate", "--data-dir", str(self.path)])
        self.assertEqual(default, 0)
        self.assertIn("WARNING: e1:", err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            relaxed = main(["report", "--data-dir", str(self.path), "--output-dir",
                            str(self.path / "out"), "--interval-tolerance", "0.2"])
        self.assertEqual(relaxed, 0)
        self.assertEqual(err.getvalue(), "")

    def test_cli_rejects_bad_tolerance(self):
        self.write(acq())
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = main(["validate", "--data-dir", str(self.path), "--interval-tolerance", "-1"])
        self.assertEqual(code, 2)
        self.assertIn("interval_tolerance", err.getvalue())


if __name__ == "__main__":
    unittest.main()
