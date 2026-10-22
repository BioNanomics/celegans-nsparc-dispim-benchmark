import contextlib
import csv
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from celegans_benchmark.audit import read_spot_counts, select_frames, write_selection
from celegans_benchmark.cli import main
from celegans_benchmark.metrics import DataError, STAGES


def counts_file(path, rows, header="time_point,spots", comments=()):
    text = "".join(f"# {c}\n" for c in comments) + header + "\n" + "".join(f"{r}\n" for r in rows)
    path.write_text(text, encoding="utf-8")
    return path


class ReadSpotCountsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_reads_rows_and_skips_comments(self):
        p = counts_file(self.root / "c.txt", ["0,4", "1,4", "2,6"], comments=["practice data"])
        counts, blank = read_spot_counts(p)
        self.assertEqual(counts, {0: 4, 1: 4, 2: 6})
        self.assertEqual(blank, [])

    def test_blank_spot_count_is_unknown_not_zero(self):
        p = counts_file(self.root / "c.txt", ["0,4", "1,", "2,6"])
        counts, blank = read_spot_counts(p)
        self.assertEqual(counts, {0: 4, 2: 6})
        self.assertEqual(blank, [1])

    def test_rejects_bad_input(self):
        cases = {
            "header": (["0,4"], "frame,n"),
            "duplicate": (["0,4", "0,5"], "time_point,spots"),
            "negative": (["0,-1"], "time_point,spots"),
            "not integer": (["0,4.5"], "time_point,spots"),
            "text": (["zero,4"], "time_point,spots"),
            "empty": ([], "time_point,spots"),
        }
        for name, (rows, header) in cases.items():
            p = counts_file(self.root / f"{name}.txt", rows, header=header)
            with self.assertRaises(DataError, msg=name):
                read_spot_counts(p)

    def test_missing_file(self):
        with self.assertRaises(DataError):
            read_spot_counts(self.root / "nope.txt")


class SelectFramesTests(unittest.TestCase):
    COUNTS = {t: n for t, n in enumerate([4, 4, 6, 7, 8, 14, 15, 16, 20, 30, 49, 50, 60,
                                           99, 100, 120, 150, 199, 200, 250, 363])}

    def test_picks_per_stage_sorted_by_time(self):
        rows = select_frames(self.COUNTS, per_stage=2, seed=1)
        by_stage = {}
        for r in rows:
            by_stage.setdefault(r["stage"], []).append(r["time_point"])
        self.assertEqual(set(by_stage), set(STAGES))
        self.assertTrue(all(len(v) == 2 for v in by_stage.values()))
        self.assertEqual([r["time_point"] for r in rows], sorted(r["time_point"] for r in rows))

    def test_exactly_100_is_100_199(self):
        rows = select_frames({0: 100}, per_stage=1, seed=0)
        self.assertEqual(rows, [{"time_point": 0, "volume_index": 0, "estimated_spots": 100, "stage": "100-199"}])

    def test_single_frame(self):
        self.assertEqual(len(select_frames({7: 3}, per_stage=5, seed=0)), 1)

    def test_small_stage_takes_all_and_missing_stage_is_absent(self):
        rows = select_frames({0: 4, 1: 5, 2: 60}, per_stage=3, seed=0)
        self.assertEqual({r["stage"] for r in rows}, {"<16", "50-99"})
        self.assertEqual(len(rows), 3)

    def test_same_seed_same_frames_different_seed_differs(self):
        counts = {t: 10 for t in range(200)}
        a = select_frames(counts, per_stage=5, seed=42)
        self.assertEqual(a, select_frames(counts, per_stage=5, seed=42))
        self.assertNotEqual(a, select_frames(counts, per_stage=5, seed=43))

    def test_no_frames(self):
        self.assertEqual(select_frames({}, per_stage=3, seed=0), [])

    def test_per_stage_must_be_positive(self):
        with self.assertRaises(DataError):
            select_frames(self.COUNTS, per_stage=0, seed=0)


class WriteSelectionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_writes_csv_and_returns_its_sha256(self):
        out = self.root / "frames.csv"
        digest = write_selection([{"time_point": 3, "volume_index": 3, "estimated_spots": 8, "stage": "<16"}], out)
        self.assertEqual(digest, hashlib.sha256(out.read_bytes()).hexdigest())
        with out.open(encoding="utf-8", newline="") as f:
            self.assertEqual(list(csv.DictReader(f)),
                             [{"time_point": "3", "volume_index": "3", "estimated_spots": "8", "stage": "<16"}])

    def test_refuses_to_overwrite_a_frozen_list(self):
        out = self.root / "frames.csv"
        out.write_text("already chosen\n")
        with self.assertRaisesRegex(DataError, "refusing to overwrite"):
            write_selection([{"time_point": 3, "estimated_spots": 8, "stage": "<16"}], out)
        self.assertEqual(out.read_text(), "already chosen\n")


class SelectFramesCliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_cli_writes_list_and_reports_hash_and_gaps(self):
        src = counts_file(self.root / "c.txt", ["0,4", "1,", "2,30", "3,60"])
        out = self.root / "frames.csv"
        code, stdout, _ = self.run_cli("select-frames", "--spot-counts", str(src), "--output",
                                       str(out), "--per-stage", "2", "--seed", "7")
        self.assertEqual(code, 0)
        self.assertTrue(out.exists())
        self.assertIn(hashlib.sha256(out.read_bytes()).hexdigest(), stdout)
        self.assertIn("100-199: not selectable", stdout)
        self.assertIn("200+: not selectable", stdout)
        self.assertIn("1 time point(s) with blank spot count", stdout)

    def test_cli_refusal_exit_code(self):
        src = counts_file(self.root / "c.txt", ["0,4"])
        out = self.root / "frames.csv"
        args = ("select-frames", "--spot-counts", str(src), "--output", str(out))
        self.assertEqual(self.run_cli(*args)[0], 0)
        code, _, err = self.run_cli(*args)
        self.assertEqual(code, 2)
        self.assertIn("refusing to overwrite", err)

    def test_cli_no_eligible_frames_writes_nothing(self):
        src = counts_file(self.root / "c.txt", ["0,"])
        out = self.root / "frames.csv"
        code, _, err = self.run_cli("select-frames", "--spot-counts", str(src), "--output", str(out))
        self.assertEqual(code, 2)
        self.assertFalse(out.exists())
        self.assertIn("no frames", err)


if __name__ == "__main__":
    unittest.main()
