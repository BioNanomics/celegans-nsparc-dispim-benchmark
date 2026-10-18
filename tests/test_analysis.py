import csv
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.metrics import DataError, load_data, stage_of, summarize, write_reports


DATA = {
    "acquisitions": (
        "embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
        "e60,NSPARC_60s,BV514,mCherry,20,60,60,3\n"
        "e180,NSPARC_180s,BV514,mCherry,20,180,180,2\n"
        "ec,CONTROL,BV514,mCherry,20,,,0\n"),
    "embryo_outcomes": (
        "embryo_id,hatched,hatch_t_min,abnormal_development,excluded,exclusion_reason\n"
        "e60,1,700,0,0,\n"
        "e180,0,,1,0,\n"
        "ec,,,0,0,\n"),
    "nuclei_qc": (
        "embryo_id,volume_index,t_min,manual_cell_count,tp,fp,fn,depth_region\n"
        "e60,0,0,4,4,0,0,all\n"
        "e60,1,1,8,7,1,1,all\n"
        "e180,0,0,4,3,2,1,all\n"),
    "lineage_qc": (
        "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n"
        "e60,l1,1,8,1,1\n"
        "e60,l2,1,8,1,0\n"
        "e180,l1,1,8,0,\n"),
    "milestones": (
        "embryo_id,milestone,t_min\n"
        "e60,twofold,400\n"
        "e180,twofold,450\n"),
}


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        for name, value in DATA.items():
            (self.path / f"{name}.csv").write_text(value)

    def test_valid_and_metrics(self):
        ds = load_data(self.path)
        report = summarize(ds)
        sixty = report["groups"][0]
        self.assertEqual(sixty["hatching_fraction"], 1.0)
        self.assertEqual(sixty["hatching_known_n"], 1)
        self.assertEqual(sixty["audited_volumes"], 2)
        self.assertEqual(sixty["verified_lineage_events"], 2)
        self.assertEqual(sixty["lineage_correct_fraction"], 0.5)
        self.assertAlmostEqual(sixty["recall"], 11 / 12)
        self.assertEqual(report["groups"][2]["hatching_unknown_n"], 1)
        self.assertEqual(stage_of(100), "100-199")
        paths = write_reports(report, self.path / "out")
        self.assertTrue(all(p.exists() for p in paths))

    def test_unknown_embryo_rejected(self):
        path = self.path / "nuclei_qc.csv"
        path.write_text(path.read_text() + "nonexistent,0,0,4,4,0,0,all\n")
        with self.assertRaisesRegex(DataError, "unknown embryo_id"):
            load_data(self.path)

    def test_manual_counts_must_reconcile(self):
        path = self.path / "nuclei_qc.csv"
        path.write_text(path.read_text().replace("e60,1,1,8,7,1,1,all", "e60,1,1,8,7,1,0,all"))
        with self.assertRaisesRegex(DataError, "must equal tp\\+fn"):
            load_data(self.path)

    def test_duplicate_qc_rejected(self):
        path = self.path / "nuclei_qc.csv"
        path.write_text(path.read_text() + "e60,1,1,8,7,1,1,all\n")
        with self.assertRaisesRegex(DataError, "duplicate"):
            load_data(self.path)

    def test_control_no_fluorescence(self):
        path = self.path / "acquisitions.csv"
        path.write_text(path.read_text().replace("ec,CONTROL,BV514,mCherry,20,,,0", "ec,CONTROL,BV514,mCherry,20,,,1"))
        with self.assertRaisesRegex(DataError, "CONTROL"):
            load_data(self.path)

    def test_exclusion_explained(self):
        path = self.path / "embryo_outcomes.csv"
        path.write_text(path.read_text().replace("e180,0,,1,0,", "e180,0,,1,1,"))
        with self.assertRaisesRegex(DataError, "exclusion_reason"):
            load_data(self.path)

    def test_empty_template_allowed(self):
        for name, value in DATA.items():
            (self.path / f"{name}.csv").write_text(value.splitlines()[0] + "\n")
        ds = load_data(self.path)
        self.assertEqual(ds.acquisitions, [])
        result = summarize(ds)
        self.assertEqual(result["groups"][0]["n_included"], 0)


if __name__ == "__main__":
    unittest.main()
