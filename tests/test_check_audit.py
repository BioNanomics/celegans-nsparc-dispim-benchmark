import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.audit import check_audit
from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError

ACQ = ("embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
       "e1,NSPARC_60s,BV514,mCherry,20,60,60,10\n"
       "e2,NSPARC_60s,BV514,mCherry,20,60,60,10\n")
NUC_H = "embryo_id,volume_index,t_min,manual_cell_count,tp,fp,fn,depth_region\n"


class CheckAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.counts = self.root / "counts.txt"
        self.write_counts(["0,4", "1,6", "2,", "3,20"])

    def write(self, *nuclei):
        (self.root / "acquisitions.csv").write_text(ACQ)
        (self.root / "embryo_outcomes.csv").write_text(
            "embryo_id,hatched,hatch_t_min,abnormal_development,excluded,exclusion_reason\n")
        (self.root / "nuclei_qc.csv").write_text(NUC_H + "".join(nuclei))
        (self.root / "lineage_qc.csv").write_text(
            "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n")
        (self.root / "milestones.csv").write_text("embryo_id,milestone,t_min\n")

    def write_counts(self, rows):
        self.counts.write_text("# practice\ntime_point,spots\n" + "".join(r + "\n" for r in rows))

    def status(self, embryo="e1"):
        return {r["volume_index"]: r["status"] for r in check_audit(self.root, embryo, self.counts)}

    def test_match_and_mismatch(self):
        # frame 0: tp+fp = 4 matches 4 spots; frame 1: tp+fp = 5 but tracker has 6
        self.write("e1,0,0,4,4,0,0,all\n", "e1,1,1,6,4,1,2,all\n")
        rows = {r["volume_index"]: r for r in check_audit(self.root, "e1", self.counts)}
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual((rows[1]["status"], rows[1]["tp_plus_fp"], rows[1]["tracker_spots"]),
                         ("mismatch", 5, 6))

    def test_frame_missing_or_blank_in_counts_is_not_checkable(self):
        self.write("e1,2,2,5,5,0,0,all\n", "e1,7,7,5,5,0,0,all\n")
        self.assertEqual(self.status(), {2: "not_checkable", 7: "not_checkable"})

    def test_near_far_checked_against_frame_total(self):
        # near tp+fp = 9, far tp+fp = 11 -> frame total 20 = tracker 20
        self.write("e1,3,3,10,9,0,1,near\n", "e1,3,3,10,9,2,1,far\n")
        rows = check_audit(self.root, "e1", self.counts)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["tp_plus_fp"], rows[0]["status"]), (20, "ok"))

    def test_only_the_named_embryo_is_checked(self):
        self.write("e1,0,0,4,4,0,0,all\n", "e2,0,0,4,1,0,3,all\n")
        rows = check_audit(self.root, "e1", self.counts)
        self.assertEqual([(r["embryo_id"], r["status"]) for r in rows], [("e1", "ok")])

    def test_no_audited_rows(self):
        self.write()
        self.assertEqual(check_audit(self.root, "e1", self.counts), [])

    def test_unknown_embryo_rejected(self):
        self.write("e1,0,0,4,4,0,0,all\n")
        with self.assertRaisesRegex(DataError, "e9"):
            check_audit(self.root, "e9", self.counts)

    def test_invalid_run_data_still_rejected(self):
        self.write("e1,0,0,4,4,0,1,all\n")  # manual != tp + fn
        with self.assertRaises(DataError):
            check_audit(self.root, "e1", self.counts)

    def test_sorted_by_frame(self):
        self.write("e1,3,3,20,20,0,0,all\n", "e1,0,0,4,4,0,0,all\n")
        self.assertEqual([r["volume_index"] for r in check_audit(self.root, "e1", self.counts)], [0, 3])

    # ---- CLI ---------------------------------------------------------------
    def run_cli(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["check-audit", "--data-dir", str(self.root), "--embryo-id", "e1",
                         "--spot-counts", str(self.counts)])
        return code, out.getvalue(), err.getvalue()

    def test_cli_exit_codes(self):
        self.write("e1,0,0,4,4,0,0,all\n", "e1,2,2,5,5,0,0,all\n")
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)              # not_checkable is unknown, not a failure
        self.assertIn("not_checkable", out)
        self.write("e1,1,1,6,4,1,2,all\n")
        code, out, _ = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("mismatch", out)
        self.assertIn("tp+fp=5", out)
        self.assertIn("tracker=6", out)

    def test_cli_no_rows_and_errors(self):
        self.write()
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("No audited frames", out)
        self.counts.unlink()
        self.assertEqual(self.run_cli()[0], 2)


if __name__ == "__main__":
    unittest.main()
