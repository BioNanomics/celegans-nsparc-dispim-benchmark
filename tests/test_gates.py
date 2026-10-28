import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError, Gates, load_data, summarize

ACQ = ("embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
       "e60,NSPARC_60s,BV514,mCherry,20,60,60,5\n"
       "e180,NSPARC_180s,BV514,mCherry,20,180,180,5\n"
       "ec,CONTROL,BV514,mCherry,20,,,0\n")
OUT = ("embryo_id,hatched,hatch_t_min,abnormal_development,excluded,exclusion_reason\n"
       "e60,1,700,0,0,\ne180,1,700,0,0,\nec,,,0,0,\n")
NUC_H = "embryo_id,volume_index,t_min,manual_cell_count,tp,fp,fn,depth_region\n"
LIN_H = "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n"
MIL_H = "embryo_id,milestone,t_min\n"


def nuc(eid, vol, count, tp, fp=0):
    return f"{eid},{vol},{vol},{count},{tp},{fp},{count - tp},all\n"


class GateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        self.write(nuclei=[], lineage=[])

    def write(self, nuclei, lineage, outcomes=OUT):
        (self.path / "acquisitions.csv").write_text(ACQ)
        (self.path / "embryo_outcomes.csv").write_text(outcomes)
        (self.path / "nuclei_qc.csv").write_text(NUC_H + "".join(nuclei))
        (self.path / "lineage_qc.csv").write_text(LIN_H + "".join(lineage))
        (self.path / "milestones.csv").write_text(MIL_H)

    def gates(self, **kw):
        report = summarize(load_data(self.path), Gates(**kw) if kw else None)
        return {(r["group"], r["gate"]): r for r in report["feasibility_gates"]}

    def test_no_data_is_not_evaluable_never_fail(self):
        g = self.gates()
        self.assertEqual(len(g), 4)  # 2 NSPARC groups x 2 gates, CONTROL excluded
        for row in g.values():
            self.assertEqual(row["status"], "not_evaluable")
            self.assertIsNone(row["value"])

    def test_empty_templates_still_report_not_evaluable(self):
        for name in ("nuclei_qc", "lineage_qc"):
            p = self.path / f"{name}.csv"
            p.write_text(p.read_text().splitlines()[0] + "\n")
        (self.path / "acquisitions.csv").write_text(ACQ.splitlines()[0] + "\n")
        (self.path / "embryo_outcomes.csv").write_text(OUT.splitlines()[0] + "\n")
        report = summarize(load_data(self.path))
        self.assertTrue(all(r["status"] == "not_evaluable" for r in report["feasibility_gates"]))
        self.assertEqual(report["feasibility_gates_by_embryo"], [])

    def test_pass_and_fail(self):
        self.write(nuclei=[nuc("e60", 0, 20, 20), nuc("e180", 0, 20, 10)],
                   lineage=["e60,a,1,8,1,1\n", "e180,a,1,8,1,0\n"])
        g = self.gates()
        self.assertEqual(g[("NSPARC_60s", "detection_recall")]["status"], "pass")
        self.assertEqual(g[("NSPARC_180s", "detection_recall")]["status"], "fail")
        self.assertEqual(g[("NSPARC_60s", "lineage_correct")]["status"], "pass")
        row = g[("NSPARC_180s", "lineage_correct")]
        self.assertEqual((row["status"], row["value"]), ("fail", 0.0))  # zero is a fail, not blank

    def test_exactly_100_cells_counts_but_101_does_not(self):
        self.write(nuclei=[nuc("e60", 0, 100, 100), nuc("e60", 1, 101, 0)], lineage=[])
        row = self.gates()[("NSPARC_60s", "detection_recall")]
        self.assertEqual((row["status"], row["value"], row["denominator"]), ("pass", 1.0, 100))

    def test_only_frames_above_limit_is_not_evaluable(self):
        self.write(nuclei=[nuc("e60", 0, 150, 10)], lineage=[])
        self.assertEqual(self.gates()[("NSPARC_60s", "detection_recall")]["status"],
                         "not_evaluable")

    def test_through_cells_is_configurable(self):
        self.write(nuclei=[nuc("e60", 0, 100, 100)], lineage=[])
        row = self.gates(recall_through_cells=99)[("NSPARC_60s", "detection_recall")]
        self.assertEqual(row["status"], "not_evaluable")

    def test_threshold_boundary_is_inclusive(self):
        self.write(nuclei=[nuc("e60", 0, 20, 19), nuc("e180", 0, 20, 18)],
                   lineage=[f"e60,l{i},1,8,1,{int(i < 9)}\n" for i in range(10)])
        g = self.gates()
        self.assertEqual(g[("NSPARC_60s", "detection_recall")]["status"], "pass")    # 0.95
        self.assertEqual(g[("NSPARC_180s", "detection_recall")]["status"], "fail")   # 0.90
        self.assertEqual(g[("NSPARC_60s", "lineage_correct")]["status"], "pass")     # 0.90

    def test_thresholds_configurable(self):
        self.write(nuclei=[nuc("e180", 0, 20, 10)], lineage=[])
        row = self.gates(recall_min=0.5)[("NSPARC_180s", "detection_recall")]
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["threshold"], 0.5)

    def test_invalid_gate_settings_rejected(self):
        for kw in ({"recall_min": 1.5}, {"lineage_min": -0.1}, {"recall_through_cells": -1},
                   {"recall_min": float("nan")}):
            with self.assertRaises(DataError, msg=str(kw)):
                Gates(**kw)

    def test_unverified_lineage_not_counted(self):
        self.write(nuclei=[], lineage=["e60,a,1,8,0,\n"])
        self.assertEqual(self.gates()[("NSPARC_60s", "lineage_correct")]["status"],
                         "not_evaluable")

    def test_excluded_embryo_ignored(self):
        out = OUT.replace("e180,1,700,0,0,", "e180,1,700,0,1,bad mount")
        self.write(nuclei=[nuc("e180", 0, 20, 20)], lineage=[], outcomes=out)
        self.assertEqual(self.gates()[("NSPARC_180s", "detection_recall")]["status"],
                         "not_evaluable")

    def test_group_pools_embryos_and_counts_contributors(self):
        self.write(nuclei=[nuc("e60", 0, 10, 10), nuc("e60", 1, 10, 9)], lineage=[])
        row = self.gates()[("NSPARC_60s", "detection_recall")]
        self.assertEqual((row["numerator"], row["denominator"], row["n_embryos"]), (19, 20, 1))

    def test_by_embryo_table(self):
        self.write(nuclei=[nuc("e60", 0, 20, 20), nuc("e180", 0, 150, 150)],
                   lineage=["e60,a,1,8,1,1\n"])
        rows = summarize(load_data(self.path))["feasibility_gates_by_embryo"]
        got = {(r["embryo_id"], r["gate"]): r["status"] for r in rows}
        self.assertEqual(got, {("e60", "detection_recall"): "pass",
                               ("e60", "lineage_correct"): "pass",
                               ("e180", "detection_recall"): "not_evaluable",
                               ("e180", "lineage_correct"): "not_evaluable"})

    def test_cli_options_and_output_files(self):
        self.write(nuclei=[nuc("e180", 0, 20, 10)], lineage=[])
        out = self.path / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["report", "--data-dir", str(self.path), "--output-dir", str(out),
                         "--recall-threshold", "0.5"])
        self.assertEqual(code, 0)
        with (out / "feasibility_gates.csv").open() as f:
            rows = {(r["group"], r["gate"]): r for r in csv.DictReader(f)}
        self.assertEqual(rows[("NSPARC_180s", "detection_recall")]["status"], "pass")
        self.assertEqual(rows[("NSPARC_60s", "detection_recall")]["value"], "")  # blank, not 0
        self.assertTrue((out / "feasibility_gates_by_embryo.csv").exists())

    def test_cli_rejects_bad_threshold(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = main(["report", "--data-dir", str(self.path), "--output-dir",
                         str(self.path / "o"), "--recall-threshold", "2"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
