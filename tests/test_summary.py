import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import celegans_benchmark
from celegans_benchmark.cli import main
from celegans_benchmark.metrics import Gates, load_data, summarize
from celegans_benchmark.summary import auto_label, fmt_rate, render_summary

ROOT = Path(__file__).resolve().parents[1]

SMALL = {
    "acquisitions": (
        "embryo_id,group,strain,reporter,temperature_c,planned_interval_s,measured_interval_s,recorded_volumes\n"
        "e60,NSPARC_60s,BV514,mCherry,20,60,60,3\n"
        "e180,NSPARC_180s,BV514,mCherry,20,180,180,2\n"
        "ec,CONTROL,BV514,mCherry,20,,,0\n"),
    "embryo_outcomes": (
        "embryo_id,hatched,hatch_t_min,abnormal_development,excluded,exclusion_reason\n"
        "e60,1,700,0,0,\ne180,,,,0,\nec,,,0,0,\n"),
    "nuclei_qc": (
        "embryo_id,volume_index,t_min,manual_cell_count,tp,fp,fn,depth_region\n"
        "e60,0,0,4,4,0,0,all\ne60,1,1,100,95,1,5,all\ne180,0,0,4,3,2,1,all\n"),
    "lineage_qc": (
        "embryo_id,event_id,t_min,stage_cell_count,verified,correct\n"
        "e60,l1,1,8,1,1\ne60,l2,1,8,1,0\ne180,l1,1,8,0,\n"),
    "milestones": "embryo_id,milestone,t_min\ne60,twofold,400\n",
}


def render(path, gates=None, warnings=(), label=None):
    gates = gates or Gates()
    return render_summary(summarize(load_data(path), gates), gates, list(warnings), label=label)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.small = self.root / "small"
        self.small.mkdir()
        for name, text in SMALL.items():
            (self.small / f"{name}.csv").write_text(text)

    # ---- formatting helpers ------------------------------------------
    def test_fmt_rate(self):
        self.assertEqual(fmt_rate(0, 4), "0.0% (0/4)")       # a real zero stays zero
        self.assertEqual(fmt_rate(4, 4), "100.0% (4/4)")
        self.assertEqual(fmt_rate(11, 12), "91.7% (11/12)")
        self.assertEqual(fmt_rate(0, 0), "n/a")              # no denominator is unknown, not 0

    # ---- content ------------------------------------------------------
    def test_core_sections_and_values(self):
        text = render(self.small)
        for heading in ("## Groups", "## Feasibility gates", "## Detection by stage",
                        "## Lineage links by stage", "## Embryos", "## Warnings"):
            self.assertIn(heading, text)
        self.assertIn(f"v{celegans_benchmark.__version__}", text)
        self.assertIn("NSPARC_60s", text)
        self.assertIn("e60", text)

    def test_hatching_unknown_is_separate_never_zero(self):
        text = render(self.small)
        self.assertIn("1/1 known, 0 unknown", text)        # NSPARC_60s
        self.assertIn("n/a (0 known, 1 unknown)", text)    # NSPARC_180s: only unknown outcomes

    def test_exactly_100_cell_frame_counts_in_gate(self):
        text = render(self.small)
        # frames <= 100 cells: 4+100 cells -> tp 99, tp+fn 104 for the 60 s group
        self.assertIn("95.2% (99/104)", text)

    def test_gate_statuses_and_no_data_is_not_a_failure(self):
        text = render(self.small)
        self.assertIn("PASS", text)  # e60 recall 99/104 = 95.2% >= 95%
        self.assertIn("NOT EVALUABLE", text)
        # 180 s lineage has only unverified events -> not evaluable, shown as such
        empty = self.root / "empty"
        empty.mkdir()
        for name, text_ in SMALL.items():
            (empty / f"{name}.csv").write_text(text_.splitlines()[0] + "\n")
        none = render(empty)
        self.assertIn("NOT EVALUABLE", none)
        self.assertNotIn("FAIL", none)
        self.assertNotIn("PASS", none)
        self.assertIn("No embryos", none)

    def test_gate_targets_follow_settings(self):
        text = render(self.small, gates=Gates(recall_min=0.99))
        self.assertIn("≥ 99%", text)
        self.assertIn("FAIL", text)

    def test_stage_tables(self):
        text = render(self.small)
        self.assertIn("100-199", text)     # the 100-cell frame is binned by its own count
        self.assertIn("<16", text)
        self.assertIn("50.0% (1/2)", text) # lineage: 1 of 2 verified links correct

    def test_depth_section_only_when_near_far_present(self):
        self.assertNotIn("## Depth", render(self.small))
        nuc = self.small / "nuclei_qc.csv"
        nuc.write_text(SMALL["nuclei_qc"] +
                       "e60,2,2,6,6,0,0,near\ne60,2,2,6,5,0,1,far\n")
        text = render(self.small)
        self.assertIn("## Depth", text)
        self.assertIn("near", text)

    def test_embryos_listed_with_hatching_words(self):
        text = render(self.small)
        self.assertIn("| e60 | NSPARC_60s | yes |", text)
        self.assertIn("| e180 | NSPARC_180s | unknown |", text)

    def test_excluded_embryos_counted(self):
        out = self.small / "embryo_outcomes.csv"
        out.write_text(SMALL["embryo_outcomes"].replace("e180,,,,0,", "e180,,,,1,bad mount"))
        text = render(self.small)
        self.assertRegex(text, r"\| NSPARC_180s \| 1 \| 0 \| 1 \|")

    def test_warnings_listed_or_none(self):
        self.assertIn("No warnings", render(self.small))
        text = render(self.small, warnings=["e60: blank raw_sha256"])
        self.assertIn("- e60: blank raw_sha256", text)
        self.assertNotIn("No warnings", text)

    def test_pipes_in_ids_are_escaped(self):
        report = summarize(load_data(self.small))
        report["embryos"][0]["embryo_id"] = "a|b"
        text = render_summary(report, Gates(), [])
        self.assertIn("a\\|b", text)

    def test_descriptive_only_notice_present(self):
        text = render(self.small)
        self.assertIn("descriptive", text)
        self.assertIn("embryo", text.lower())

    def test_deterministic_and_no_timestamp_or_paths(self):
        a, b = render(self.small), render(self.small)
        self.assertEqual(a, b)
        self.assertNotIn(str(self.root), a)

    # ---- banner -------------------------------------------------------
    def test_auto_label(self):
        self.assertIn("FABRICATED", auto_label(Path("examples/synthetic"), None))
        self.assertIsNone(auto_label(Path("D:/private/run1"), None))
        self.assertEqual(auto_label(Path("D:/private/run1"), "PRACTICE DATA"), "PRACTICE DATA")
        self.assertIsNone(auto_label(Path("D:/private/run1"), "   "))

    def test_banner_rendered(self):
        text = render(self.small, label="FABRICATED example data")
        self.assertTrue(text.splitlines()[2].startswith("> **DATA LABEL: FABRICATED"))
        self.assertNotIn("DATA LABEL", render(self.small))

    # ---- CLI ------------------------------------------------------------
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue()

    def test_report_writes_summary_md(self):
        outdir = self.root / "out"
        code, out = self.run_cli("report", "--data-dir", str(self.small), "--output-dir", str(outdir))
        self.assertEqual(code, 0)
        self.assertIn("summary.md", out)
        text = (outdir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("## Groups", text)
        self.assertNotIn("DATA LABEL", text)

    def test_cli_label_and_synthetic_autodetect(self):
        outdir = self.root / "out2"
        self.run_cli("report", "--data-dir", str(self.small), "--output-dir", str(outdir),
                     "--label", "PRACTICE DATA")
        self.assertIn("DATA LABEL: PRACTICE DATA", (outdir / "summary.md").read_text(encoding="utf-8"))
        synthetic = self.root / "synthetic_copy"
        shutil.copytree(ROOT / "examples" / "synthetic", synthetic)
        outdir = self.root / "out3"
        self.run_cli("report", "--data-dir", str(synthetic), "--output-dir", str(outdir))
        self.assertIn("FABRICATED", (outdir / "summary.md").read_text(encoding="utf-8"))

    def test_validate_does_not_write_summary(self):
        self.run_cli("validate", "--data-dir", str(self.small))
        self.assertFalse(list(self.small.rglob("summary.md")))


if __name__ == "__main__":
    unittest.main()
