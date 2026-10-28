import builtins
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError
from celegans_benchmark.runcheck import check_run, signal_trend, write_run_check


def run(n=5, interval=60.0, slices=41, slice_s=0.7, jitter=None):
    """Fabricated timestamps: first/last slice time (s) of each time point."""
    starts = [i * interval + (jitter[i] if jitter else 0.0) for i in range(n)]
    ends = [s + (slices - 1) * slice_s for s in starts]
    return starts, ends


class CheckRunTests(unittest.TestCase):
    def test_on_schedule(self):
        s, e = run()
        r = check_run(s, e, n_slices=41, planned_interval_s=60)
        self.assertEqual(r["time_points"], 5)
        self.assertEqual(r["interval_s"], {"mean": 60.0, "min": 60.0, "max": 60.0})
        self.assertEqual((r["late"], r["missing_estimate"]), (0, 0))
        # stack = (41-1)*0.7 + one slice step (0.7) = 28.7 s, measured from the data
        self.assertAlmostEqual(r["stack_duration_s"]["mean"], 28.7, places=6)
        self.assertEqual(r["stack_fits_interval"], True)

    def test_late_and_missing(self):
        s = [0, 60, 125, 185, 305]          # 65 s is late (>5%), 120 s gap means ~1 missing
        e = [x + 28 for x in s]
        r = check_run(s, e, n_slices=41, planned_interval_s=60)
        self.assertEqual(r["late"], 2)       # 65 and 120
        self.assertEqual(r["missing_estimate"], 1)

    def test_tolerance_boundary_inclusive(self):
        s = [0, 63, 126]                     # exactly +5%
        r = check_run(s, [x + 28 for x in s], n_slices=41, planned_interval_s=60)
        self.assertEqual(r["late"], 0)
        r = check_run(s, [x + 28 for x in s], n_slices=41, planned_interval_s=60, tolerance=0.01)
        self.assertEqual(r["late"], 2)

    def test_stack_longer_than_interval(self):
        s = [0, 60, 120]
        r = check_run(s, [x + 70 for x in s], n_slices=41, planned_interval_s=60)
        self.assertFalse(r["stack_fits_interval"])

    def test_single_time_point_has_no_interval(self):
        r = check_run([0.0], [28.0], n_slices=41, planned_interval_s=60)
        self.assertEqual(r["time_points"], 1)
        self.assertIsNone(r["interval_s"])
        self.assertIsNone(r["late"])
        self.assertIsNone(r["missing_estimate"])

    def test_single_slice_stack(self):
        r = check_run([0, 60], [0, 60], n_slices=1, planned_interval_s=60)
        self.assertIsNone(r["stack_duration_s"])   # cannot be measured from one slice

    def test_planned_interval_optional(self):
        s, e = run(n=3)
        r = check_run(s, e, n_slices=41, planned_interval_s=None)
        self.assertIsNone(r["late"])
        self.assertIsNone(r["stack_fits_interval"])
        self.assertEqual(r["interval_s"]["mean"], 60.0)

    def test_invalid_input(self):
        for kwargs in ({"starts": [], "ends": []},
                       {"starts": [0, 60], "ends": [28]},
                       {"starts": [0, 60], "ends": [28, 50]},       # end before start
                       {"starts": [60, 0], "ends": [88, 28]},       # not increasing
                       {"starts": [0], "ends": [1], "planned": 0},
                       {"starts": [0], "ends": [1], "slices": 0}):
            with self.assertRaises(DataError, msg=str(kwargs)):
                check_run(kwargs["starts"], kwargs["ends"], n_slices=kwargs.get("slices", 41),
                          planned_interval_s=kwargs.get("planned", 60))


class SignalTrendTests(unittest.TestCase):
    def test_trend(self):
        self.assertEqual(signal_trend([350, 300, 200]),
                         {"first": 350, "last": 200, "min": 200, "last_pct_of_first": 57.1})

    def test_empty_and_zero_first(self):
        self.assertIsNone(signal_trend([]))
        self.assertIsNone(signal_trend([0, 5])["last_pct_of_first"])   # undefined, not 0


class WriteAndCliTests(unittest.TestCase):
    def test_write_outputs(self):
        s, e = run(n=3)
        r = check_run(s, e, n_slices=41, planned_interval_s=60)
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_run_check(r, s, e, [10.0, 9.0, 8.0], Path(tmp) / "out")
            names = sorted(p.name for p in paths)
            self.assertEqual(names, ["run_check.json", "run_check_per_timepoint.csv"])
            data = json.loads((Path(tmp) / "out" / "run_check.json").read_text())
            self.assertEqual(data["signal_p99_9"]["last_pct_of_first"], 80.0)
            rows = (Path(tmp) / "out" / "run_check_per_timepoint.csv").read_text().splitlines()
            self.assertEqual(rows[0], "time_point,start_s,stack_s,signal_p99_9")
            self.assertEqual(len(rows), 4)

    def test_cli_without_nd2_package_gives_clear_error(self):
        real_import = builtins.__import__

        def fake(name, *args, **kwargs):
            if name == "nd2":
                raise ImportError("no nd2")
            return real_import(name, *args, **kwargs)

        err = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "x.nd2"
            f.write_bytes(b"not really")
            with mock.patch("builtins.__import__", fake), contextlib.redirect_stderr(err), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = main(["run-check", "--nd2", str(f), "--planned-interval", "60"])
        self.assertEqual(code, 2)
        self.assertIn('pip install -e ".[nd2]"', err.getvalue())

    def test_cli_missing_file(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = main(["run-check", "--nd2", "does_not_exist.nd2"])
        self.assertEqual(code, 2)
        self.assertIn("not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
