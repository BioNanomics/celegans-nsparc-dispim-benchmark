"""Read-only review regression tests; never connect to NIS or real microscope data."""
import contextlib
import csv
from dataclasses import dataclass
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

try:
    import numpy as np
    import nd2
    import matplotlib
    spec = importlib.util.spec_from_file_location(
        "acquired_review", Path(__file__).resolve().parents[1]/"scripts/review_acquired_data.py")
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False


@dataclass
class Params:
    periodMs: float = 20000


@dataclass
class Loop:
    parameters: Params
    type: str = "TimeLoop"


class FakeND2:
    """A late but regular sequence with static configured Z and varying device Z."""
    sizes = {"T": 3, "Y": 4, "X": 4}
    experiment = [Loop(Params())]
    loop_indices = ({"T": 0}, {"T": 1}, {"T": 2})
    attributes = NS(sequenceCount=3, bitsPerComponentSignificant=12)
    text_info = {"capturing": "Detector mode: NSPARC\nNSPARC Mode: CF\n"}
    metadata = NS(channels=[NS(channel=NS(name="GFP"),
                              microscope=NS(objectiveName="Test 10x", objectiveNumericalAperture=.45))])

    def __init__(self, path):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def voxel_size(self):
        return NS(x=.5, y=.5, z=1)

    def frame_metadata(self, index):
        return NS(channels=[NS(time=NS(relativeTimeMs=index*40000),
                               position=NS(stagePositionUm=NS(z=100)))])

    def events(self):
        return [{"Ti2 ZDrive [\u00b5m]": 100+i, "PFS Status": 3} for i in range(3)]

    def read_frame(self, index):
        return np.arange(16, dtype=np.uint16).reshape(4, 4)+index


class FakeOvernight(FakeND2):
    sizes = {"T": 181, "C": 3, "Y": 8, "X": 8}
    metadata = NS(channels=[NS(channel=NS(name=name)) for name in ("GFP","RFP","TD")])

    def frame_metadata(self, index):
        return NS(channels=[NS(time=NS(relativeTimeMs=index*10000))])

    def read_frame(self, index):
        a = np.zeros((3,8,8), dtype=np.uint16)
        a[0,3,3] = 1000
        a[1,3,3] = 500
        a[2] = 500+50*(np.indices((8,8)).sum(axis=0)%2)
        return a


@unittest.skipUnless(HAVE_DEPS, "needs optional extras .[nd2,plots]")
class AcquiredDataReviewTests(unittest.TestCase):
    def inspect_fake(self, root, reader=FakeND2, manifest=None):
        raw, out = root/"raw", root/"out"
        raw.mkdir(); out.mkdir()
        (raw/"sample.nd2").write_bytes(b"raw")
        with patch.object(review.nd2, "ND2File", reader), contextlib.redirect_stdout(io.StringIO()):
            records = review.review_inventory(raw, manifest, out)
        return records[0], raw, out

    def test_regular_but_slow_intervals_are_compared_with_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            item, _, _ = self.inspect_fake(Path(folder))
            self.assertEqual(item["interval_median_s"], 40)
            self.assertEqual(item["planned_interval_s_from_metadata"], 20)
            self.assertEqual(item["intervals_over_plan_5pct"], 2)

    def test_device_events_are_kept_separate_from_static_position(self):
        with tempfile.TemporaryDirectory() as folder:
            item, _, _ = self.inspect_fake(Path(folder))
            self.assertEqual(item["first_plane_z_range_um"], 0)
            self.assertEqual(item["device_event_ranges"]["Ti2 ZDrive [\u00b5m]"]["max"], 102)
            self.assertEqual(item["nsparc_mode"], "CF")
            self.assertTrue(item["size_and_mtime_unchanged_since_inspection"])
            self.assertIsNone(item["sampled_pixel_statistics"][0]["normalized_laplacian_variance"])

    def test_prior_hash_is_not_presented_as_new_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root/"manifest.csv"
            manifest.write_text("file_name,size_bytes,raw_sha256\nsample.nd2,3,"+"a"*64+"\n")
            item, raw, _ = self.inspect_fake(root, manifest=manifest)
            self.assertTrue(item["bytes_match_manifest"])
            self.assertEqual(item["baseline_sha256"], "a"*64)
            self.assertFalse(item["full_hash_verified_today"])
            self.assertEqual((raw/"sample.nd2").read_bytes(), b"raw")

    def test_missing_baseline_is_unknown_and_not_a_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            item, _, _ = self.inspect_fake(Path(folder))
            self.assertIsNone(item["bytes_match_manifest"])

    def test_multi_position_file_is_reported_unsupported(self):
        class Positions(FakeND2):
            sizes = {"T": 3, "V": 2, "Y": 4, "X": 4}
        with tempfile.TemporaryDirectory() as folder:
            item, _, out = self.inspect_fake(Path(folder), Positions)
            self.assertIn("one-position", item["error"])
            self.assertFalse(item.get("sampled_pixels_readable", False))
            self.assertTrue((out/"time_points.csv").exists())

    def test_incomplete_z_grid_is_not_marked_readable(self):
        class Incomplete(FakeND2):
            sizes = {"T": 3, "Z": 2, "Y": 4, "X": 4}
        with tempfile.TemporaryDirectory() as folder:
            item, _, _ = self.inspect_fake(Path(folder), Incomplete)
            self.assertIn("declared number of Z planes", item["error"])

    def test_existing_output_directory_is_refused_before_reading_raw(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw, out = root/"raw", root/"out"
            raw.mkdir(); out.mkdir()
            (raw/"sample.nd2").write_bytes(b"raw")
            marker = out/"keep.txt"
            marker.write_text("preserve")
            with patch.object(review.nd2, "ND2File") as reader, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    review.main(["--raw-root",str(raw),"--out",str(out)])
            self.assertEqual(error.exception.code, 2)
            reader.assert_not_called()
            self.assertEqual(marker.read_text(), "preserve")

    def test_nondefault_sampling_includes_required_preview_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(review.nd2,"ND2File",FakeOvernight), contextlib.redirect_stdout(io.StringIO()):
                result=review.review_overnight("dummy.nd2",Path(folder),sample_minutes=7)
            self.assertTrue((Path(folder)/"overnight_early_samples.png").exists())
            with (Path(folder)/"overnight_samples.csv").open() as stream:
                rows=list(csv.DictReader(stream))
            self.assertTrue({90,180}.issubset({int(row["t_index"])for row in rows}))
            self.assertIn("7 minutes",result["sampling"])

    def test_initially_blank_td_is_not_a_successful_normalized_result(self):
        class Blank(FakeOvernight):
            def read_frame(self,index):
                a=super().read_frame(index)
                a[2]=0
                return a
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(review.nd2,"ND2File",Blank), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,"unevaluable initial"):
                    review.review_overnight("dummy.nd2",Path(folder))
            self.assertFalse((Path(folder)/"overnight_sampled_qc.json").exists())

    def test_later_blank_td_is_an_unknown_metric_not_nan(self):
        class LaterBlank(FakeOvernight):
            def read_frame(self,index):
                a=super().read_frame(index)
                if index>=30:
                    a[2]=0
                return a
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(review.nd2,"ND2File",LaterBlank), contextlib.redirect_stdout(io.StringIO()):
                review.review_overnight("dummy.nd2",Path(folder))
            saved=json.loads((Path(folder)/"overnight_sampled_qc.json").read_text(),
                             parse_constant=lambda value: self.fail("Nonstandard JSON: "+value))
            self.assertIsNone(saved["checkpoints"][-1]["TD_normalized_laplacian_variance_relative_first5"])


if __name__ == "__main__":
    unittest.main()
