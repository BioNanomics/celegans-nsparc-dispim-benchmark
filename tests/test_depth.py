import csv
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.metrics import DataError, load_data, summarize, write_reports

ACQ = ("embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
       "e60,NSPARC_60s,BV514,mCherry,20,60,60,5\n"
       "e180,NSPARC_180s,BV514,mCherry,20,180,180,5\n"
       "ec,CONTROL,BV514,mCherry,20,,,0\n")
OUT = ("embryo_id,hatched,hatch_t_min,abnormal_development,excluded,exclusion_reason\n"
       "e60,1,700,0,0,\ne180,1,700,0,0,\nec,,,0,0,\n")
NUC_H = "embryo_id,volume_index,t_min,manual_cell_count,tp,fp,fn,depth_region\n"


def row(eid, vol, region, count, tp, fp=0, t=None):
    return f"{eid},{vol},{vol if t is None else t},{count},{tp},{fp},{count - tp},{region}\n"


class DepthTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)

    def write(self, *nuclei):
        (self.path / "acquisitions.csv").write_text(ACQ)
        (self.path / "embryo_outcomes.csv").write_text(OUT)
        (self.path / "nuclei_qc.csv").write_text(NUC_H + "".join(nuclei))
        (self.path / "lineage_qc.csv").write_text(
            "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n")
        (self.path / "milestones.csv").write_text("embryo_id,milestone,t_min\n")

    def report(self, *nuclei):
        self.write(*nuclei)
        return summarize(load_data(self.path))

    def assertRejected(self, pattern, *nuclei):
        self.write(*nuclei)
        with self.assertRaisesRegex(DataError, pattern):
            load_data(self.path)

    @staticmethod
    def emb(r, eid):
        return next(e for e in r["embryos"] if e["embryo_id"] == eid)

    # ---- validation -------------------------------------------------
    def test_near_plus_far_accepted(self):
        self.write(row("e60", 0, "near", 10, 10), row("e60", 0, "far", 10, 9))
        self.assertEqual(len(load_data(self.path).nuclei), 2)

    def test_all_plus_near_or_far_rejected(self):
        self.assertRejected("both", row("e60", 0, "all", 20, 20), row("e60", 0, "near", 10, 10),
                            row("e60", 0, "far", 10, 10))
        self.assertRejected("both", row("e60", 0, "all", 20, 20), row("e60", 0, "near", 10, 10))
        self.assertRejected("both", row("e60", 0, "far", 10, 10), row("e60", 0, "all", 20, 20))

    def test_near_without_far_rejected(self):
        self.assertRejected("near and far", row("e60", 0, "near", 10, 10))
        self.assertRejected("near and far", row("e60", 0, "far", 10, 10))

    def test_unknown_or_miscased_region_rejected(self):
        self.assertRejected("depth_region", row("e60", 0, "mid", 10, 10))
        self.assertRejected("depth_region", row("e60", 0, "Near", 10, 10))
        self.assertRejected("depth_region", row("e60", 0, "", 10, 10))

    def test_duplicate_region_for_same_frame_rejected(self):
        self.assertRejected("duplicate", row("e60", 0, "near", 10, 10), row("e60", 0, "near", 10, 10),
                            row("e60", 0, "far", 10, 10))
        self.assertRejected("duplicate", row("e60", 0, "all", 10, 10), row("e60", 0, "all", 10, 10))

    def test_near_far_time_must_agree(self):
        self.assertRejected("t_min", row("e60", 0, "near", 10, 10, t=0), row("e60", 0, "far", 10, 10, t=1))

    def test_per_row_counts_must_reconcile(self):
        self.write("e60,0,0,10,8,0,1,near\n", row("e60", 0, "far", 10, 10))
        with self.assertRaisesRegex(DataError, "tp\\+fn"):
            load_data(self.path)

    def test_frames_may_mix_styles_across_volumes_and_embryos(self):
        self.write(row("e60", 0, "all", 20, 20), row("e60", 1, "near", 12, 12),
                   row("e60", 1, "far", 12, 12), row("e180", 0, "near", 5, 5), row("e180", 0, "far", 5, 5))
        self.assertEqual(len(load_data(self.path).nuclei), 5)

    # ---- frames are counted once, binned by total ---------------------
    def test_stage_uses_frame_total_not_region_count(self):
        r = self.report(row("e60", 0, "near", 10, 10), row("e60", 0, "far", 10, 9))
        self.assertEqual([(s["stage"], s["audited_volumes"]) for s in r["stage_qc"]],
                         [("16-49", 1)])  # 10 + 10 = 20 cells, one frame
        self.assertEqual((r["stage_qc"][0]["tp"], r["stage_qc"][0]["fn"]), (19, 1))

    def test_embryo_and_group_counts_frames_not_rows(self):
        r = self.report(row("e60", 0, "near", 10, 10), row("e60", 0, "far", 10, 9, fp=2),
                        row("e60", 1, "all", 30, 30))
        emb = self.emb(r, "e60")
        self.assertEqual(emb["n_audited_volumes"], 2)
        self.assertEqual((emb["tp"], emb["fp"], emb["fn"]), (49, 2, 1))  # plain sum of rows
        self.assertEqual(emb["max_audited_cell_count"], 30)
        self.assertEqual(r["groups"][0]["audited_volumes"], 2)

    def test_max_count_is_frame_total(self):
        r = self.report(row("e60", 0, "near", 30, 30), row("e60", 0, "far", 25, 25))
        self.assertEqual(self.emb(r, "e60")["max_audited_cell_count"], 55)
        self.assertEqual(r["groups"][0]["max_audited_cell_count"], 55)

    def test_timeline_one_point_per_frame(self):
        r = self.report(row("e60", 0, "near", 10, 10), row("e60", 0, "far", 7, 7))
        self.assertEqual([(p["volume_index"], p["manual_cell_count"]) for p in r["audited_timeline"]],
                         [(0, 17)])

    def test_single_frame_embryo(self):
        r = self.report(row("e180", 0, "near", 3, 3), row("e180", 0, "far", 2, 2))
        self.assertEqual(self.emb(r, "e180")["n_audited_volumes"], 1)
        self.assertEqual(r["stage_qc"][0]["stage"], "<16")

    # ---- gates use the frame total ------------------------------------
    def gate(self, r):
        return next(g for g in r["feasibility_gates"]
                    if g["group"] == "NSPARC_60s" and g["gate"] == "detection_recall")

    def test_gate_exactly_100_total_counts(self):
        r = self.report(row("e60", 0, "near", 60, 60), row("e60", 0, "far", 40, 38))
        g = self.gate(r)
        self.assertEqual((g["numerator"], g["denominator"]), (98, 100))
        self.assertEqual(g["status"], "pass")  # 98/100 = 0.98 >= 0.95

    def test_gate_101_total_excluded(self):
        r = self.report(row("e60", 0, "near", 61, 61), row("e60", 0, "far", 40, 40))
        self.assertEqual(self.gate(r)["status"], "not_evaluable")

    def test_gate_halves_below_limit_but_total_above_is_excluded(self):
        # each half alone is <= 100, the frame total (140) is not
        r = self.report(row("e60", 0, "near", 70, 70), row("e60", 0, "far", 70, 70))
        self.assertEqual(self.gate(r)["denominator"], 0)

    # ---- depth_qc table -------------------------------------------------
    def test_depth_qc_by_region_and_frame_stage(self):
        r = self.report(row("e60", 0, "near", 10, 10), row("e60", 0, "far", 10, 8),
                        row("e60", 1, "all", 30, 30))
        got = {(d["depth_region"], d["stage"]): d for d in r["depth_qc"]}
        self.assertEqual(set(got), {("all", "16-49"), ("near", "16-49"), ("far", "16-49")})
        self.assertEqual(got[("near", "16-49")]["recall"], 1.0)
        self.assertEqual(got[("far", "16-49")]["recall"], 0.8)
        self.assertEqual(got[("far", "16-49")]["audited_volumes"], 1)

    def test_depth_qc_sorted_and_empty_when_no_data(self):
        self.assertEqual(self.report()["depth_qc"], [])
        r = self.report(row("e180", 0, "far", 5, 5), row("e180", 0, "near", 5, 5), row("e60", 0, "all", 5, 5))
        self.assertEqual([(d["group"], d["depth_region"]) for d in r["depth_qc"]],
                         [("NSPARC_60s", "all"), ("NSPARC_180s", "near"), ("NSPARC_180s", "far")])

    def test_depth_qc_written_to_reports(self):
        r = self.report(row("e60", 0, "near", 10, 10), row("e60", 0, "far", 10, 10))
        paths = write_reports(r, self.path / "out")
        self.assertIn("depth_qc.csv", [p.name for p in paths])
        with (self.path / "out" / "depth_qc.csv").open() as f:
            self.assertEqual(len(list(csv.DictReader(f))), 2)

    def test_all_only_data_unchanged(self):
        r = self.report(row("e60", 0, "all", 20, 18, fp=1), row("e60", 1, "all", 60, 60))
        self.assertEqual(self.emb(r, "e60")["n_audited_volumes"], 2)
        self.assertEqual([(s["stage"], s["audited_volumes"]) for s in r["stage_qc"]],
                         [("16-49", 1), ("50-99", 1)])


if __name__ == "__main__":
    unittest.main()
