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


if __name__ == "__main__":
    unittest.main()
