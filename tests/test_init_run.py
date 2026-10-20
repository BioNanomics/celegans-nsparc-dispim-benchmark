import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError, TABLES, load_data
from celegans_benchmark.runfolder import init_run


class InitRunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.templates = self.root / "templates"
        self.templates.mkdir()
        for stem in TABLES:
            (self.templates / f"{stem}.csv").write_text(f"embryo_id,{stem}\n")

    def test_creates_missing_folder_with_all_templates(self):
        target = self.root / "run" / "day1"
        written = init_run(target, self.templates)
        self.assertEqual(sorted(p.name for p in written),
                         sorted(f"{stem}.csv" for stem in TABLES))
        self.assertEqual((target / "milestones.csv").read_text(), "embryo_id,milestones\n")

    def test_existing_empty_folder_ok(self):
        target = self.root / "run"
        target.mkdir()
        self.assertEqual(len(init_run(target, self.templates)), len(TABLES))

    def test_non_csv_files_do_not_block(self):
        target = self.root / "run"
        target.mkdir()
        (target / "notes.txt").write_text("keep")
        init_run(target, self.templates)
        self.assertEqual((target / "notes.txt").read_text(), "keep")

    def test_refuses_existing_csv_and_leaves_folder_untouched(self):
        target = self.root / "run"
        target.mkdir()
        (target / "acquisitions.csv").write_text("real data\n")
        with self.assertRaisesRegex(DataError, "refusing to overwrite"):
            init_run(target, self.templates)
        self.assertEqual((target / "acquisitions.csv").read_text(), "real data\n")
        self.assertEqual([p.name for p in target.iterdir()], ["acquisitions.csv"])

    def test_refuses_any_csv_not_just_template_names(self):
        target = self.root / "run"
        target.mkdir()
        (target / "other.csv").write_text("x\n")
        with self.assertRaisesRegex(DataError, "refusing to overwrite"):
            init_run(target, self.templates)
        self.assertFalse((target / "acquisitions.csv").exists())

    def test_target_is_a_file(self):
        target = self.root / "afile"
        target.write_text("x")
        with self.assertRaisesRegex(DataError, "not a folder"):
            init_run(target, self.templates)

    def test_missing_template_creates_nothing(self):
        (self.templates / "lineage_qc.csv").unlink()
        target = self.root / "run"
        with self.assertRaisesRegex(DataError, "template"):
            init_run(target, self.templates)
        self.assertFalse(target.exists())

    def test_missing_templates_dir(self):
        with self.assertRaisesRegex(DataError, "template"):
            init_run(self.root / "run", self.root / "nope")

    def test_real_templates_produce_valid_empty_run(self):
        target = self.root / "run"
        init_run(target)
        self.assertEqual(load_data(target).acquisitions, [])

    def test_cli_success_and_refusal(self):
        target = self.root / "run"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            first = main(["init-run", "--run-dir", str(target),
                          "--templates-dir", str(self.templates)])
            second = main(["init-run", "--run-dir", str(target),
                           "--templates-dir", str(self.templates)])
        self.assertEqual(first, 0)
        self.assertEqual(second, 2)
        self.assertIn("refusing to overwrite", err.getvalue())


if __name__ == "__main__":
    unittest.main()
