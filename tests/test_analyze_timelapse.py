"""Tests for the helper functions of scripts/analyze_timelapse.py (needs .[nd2,plots])."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_timelapse.py"

try:
    import numpy as np
    import nd2  # noqa: F401
    import matplotlib  # noqa: F401

    _spec = importlib.util.spec_from_file_location("analyze_timelapse", SCRIPT)
    at = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(at)
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False


@unittest.skipUnless(HAVE_DEPS, "needs optional extras .[nd2,plots]")
class AnalyzeTimelapseHelpers(unittest.TestCase):
    def test_as_cyx_max_projects_z_and_adds_channel_axis(self):
        a = np.zeros((3, 4, 5), dtype=np.uint16)  # Z, Y, X
        a[1, 2, 3] = 9
        out = at.as_cyx(a, ["Z", "Y", "X"])
        self.assertEqual(out.shape, (1, 4, 5))
        self.assertEqual(out[0, 2, 3], 9)
        b = np.zeros((2, 2, 4, 5), dtype=np.uint16)  # Z, C, Y, X
        b[0, 1, 0, 0] = 7
        out = at.as_cyx(b, ["Z", "C", "Y", "X"])
        self.assertEqual(out.shape, (2, 4, 5))
        self.assertEqual(out[1, 0, 0], 7)

    def test_fg_stats_separates_bright_object_from_background(self):
        rng = np.random.default_rng(0)
        img = rng.normal(100, 2, (100, 100))
        img[40:50, 40:50] = 600  # 1% of pixels
        p999, bg, fg, area, integ = at.fg_stats(img)
        self.assertAlmostEqual(bg, 100, delta=1)
        self.assertAlmostEqual(fg, 500, delta=2)
        self.assertAlmostEqual(area, 0.01, delta=0.001)
        self.assertAlmostEqual(integ, 500 * 100, delta=300)
        self.assertGreater(p999, 590)

    def test_fg_stats_flat_image_has_no_foreground(self):
        _, _, fg, area, integ = at.fg_stats(np.full((20, 20), 50.0))
        self.assertEqual((fg, area, integ), (0.0, 0.0, 0.0))

    def test_retention_half_time_and_tau_on_exponential(self):
        t = np.arange(0, 241, 1.0)  # minutes
        v = 1000 * np.exp(-t / 60)
        self.assertAlmostEqual(at.retention(t, v, 60), np.exp(-1), delta=0.03)
        self.assertIsNone(at.retention(t, v, 300))  # beyond the run
        start = v[:5].mean()  # baseline is the mean of the first 5 frames
        self.assertAlmostEqual(at.half_time(t, v), 60 * np.log(2000 / start), delta=1)
        self.assertAlmostEqual(at.exp_tau(t, v), 60, delta=0.5)

    def test_half_time_none_when_signal_stays_above_half(self):
        t = np.arange(25, dtype=float)
        v = np.linspace(100, 80, 25)  # short run, 80% retained
        self.assertIsNone(at.half_time(t, v))
        self.assertIsNone(at.exp_tau(t, np.ones(25)))  # no decay

    def test_shift_between_recovers_translation(self):
        rng = np.random.default_rng(1)
        a = rng.random((64, 64))
        b = np.roll(np.roll(a, 3, axis=0), -5, axis=1)
        dy, dx = at.shift_between(b, a)
        self.assertEqual((dy, dx), (3.0, -5.0))

    def test_compare_plot_writes_figure(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "run1").mkdir()
            with open(root / "run1" / "per_frame.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["t_index", "time_s", "GFP_fg_mean_minus_bg"])
                for i in range(10):
                    w.writerow([i, i * 60, 100 - i])
            summary = {"file": str(root / "run1.nd2"), "signal": {"GFP": {}},
                       "settings": {"GFP": {"laser_power_pct": [3.0]}}}
            json.dumps(summary)
            at.compare_plot(root, [summary])
            self.assertTrue((root / "comparison.png").stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
