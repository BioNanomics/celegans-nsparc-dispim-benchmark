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

    def _set_lineage(self, rows):
        header = "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n"
        (self.path / "lineage_qc.csv").write_text(header + "".join(rows))

    def _lineage_stage(self):
        return summarize(load_data(self.path))["lineage_stage_qc"]

    def test_lineage_stage_basic(self):
        rows = self._lineage_stage()
        # default data: both verified events (stage_cell_count=8) are in e60
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["group"], row["stage"]), ("NSPARC_60s", "<16"))
        self.assertEqual(row["verified_lineage_events"], 2)
        self.assertEqual(row["correct_lineage_events"], 1)
        self.assertEqual(row["lineage_correct_fraction"], 0.5)

    def test_lineage_stage_bin_edges(self):
        edges = [(15, "<16"), (16, "16-49"), (49, "16-49"), (50, "50-99"),
                 (99, "50-99"), (100, "100-199"), (199, "100-199"), (200, "200+")]
        self._set_lineage([f"e60,l{i},1,{n},1,1\n" for i, (n, _) in enumerate(edges)])
        got = {r["stage"]: r["verified_lineage_events"] for r in self._lineage_stage()}
        self.assertEqual(got, {"<16": 1, "16-49": 2, "50-99": 2, "100-199": 2, "200+": 1})

    def test_lineage_stage_exactly_100_is_100_199(self):
        self._set_lineage(["e60,l1,1,100,1,1\n"])
        rows = self._lineage_stage()
        self.assertEqual([r["stage"] for r in rows], ["100-199"])

    def test_lineage_stage_no_data(self):
        self._set_lineage([])
        self.assertEqual(self._lineage_stage(), [])

    def test_lineage_stage_unverified_only_is_absent(self):
        self._set_lineage(["e60,l1,1,8,0,\n", "e180,l1,1,60,0,\n"])
        self.assertEqual(self._lineage_stage(), [])

    def test_lineage_stage_single_event(self):
        self._set_lineage(["e180,l1,1,60,1,1\n"])
        rows = self._lineage_stage()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["group"], rows[0]["stage"]), ("NSPARC_180s", "50-99"))
        self.assertEqual(rows[0]["lineage_correct_fraction"], 1.0)

    def test_lineage_stage_all_incorrect_is_zero_not_blank(self):
        self._set_lineage(["e60,l1,1,8,1,0\n", "e60,l2,1,8,1,0\n"])
        self.assertEqual(self._lineage_stage()[0]["lineage_correct_fraction"], 0.0)

    def test_lineage_stage_excludes_excluded_embryos(self):
        self._set_lineage(["e60,l1,1,8,1,1\n", "e180,l1,1,8,1,1\n"])
        path = self.path / "embryo_outcomes.csv"
        path.write_text(path.read_text().replace("e180,0,,1,0,", "e180,0,,1,1,bad mount"))
        self.assertEqual([r["group"] for r in self._lineage_stage()], ["NSPARC_60s"])

    def test_lineage_stage_sorted_by_group_then_stage(self):
        self._set_lineage(["e180,a,1,120,1,1\n", "e180,b,1,8,1,1\n",
                           "e60,c,1,60,1,1\n", "e60,d,1,8,1,1\n"])
        got = [(r["group"], r["stage"]) for r in self._lineage_stage()]
        self.assertEqual(got, [("NSPARC_60s", "<16"), ("NSPARC_60s", "50-99"),
                               ("NSPARC_180s", "<16"), ("NSPARC_180s", "100-199")])

    def test_lineage_stage_written_to_reports(self):
        paths = write_reports(summarize(load_data(self.path)), self.path / "out")
        self.assertIn("lineage_stage_qc.csv", [p.name for p in paths])

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
