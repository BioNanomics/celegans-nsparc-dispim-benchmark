"""Contracts for a frozen, image-independent manual spot-review plan."""

import copy
import hashlib
import json
import unittest

from celegans_benchmark.spot_annotation import (
    FRAME_REVIEW_STATES, VISIBILITY_STATES, annotation_fieldnames,
    build_frame_plan, frame_review_fieldnames, plan_digest,
)


class FramePlanTests(unittest.TestCase):
    def setUp(self):
        self.times = [float(i * 4) for i in range(151)]
        self.sha = "a" * 64
        self.pixel = 0.5066912885485768

    def plan(self, **overrides):
        args = {"times_s": self.times, "source_sha256": self.sha, "pixel_um": self.pixel}
        args.update(overrides)
        return build_frame_plan(**args)

    def test_temporal_blocks_cover_each_frame_once(self):
        plan = self.plan()
        frames = plan["frames"]
        self.assertEqual([r["frame_index"] for r in frames], list(range(151)))
        for split, expected in (("development", range(60)), ("buffer", range(60, 75)),
                                ("evaluation", range(75, 151))):
            selected = [r["frame_index"] for r in frames if r["split"] == split]
            self.assertEqual(selected, list(expected))
            self.assertEqual(plan["splits"][split]["frame_count"], len(expected))
        self.assertEqual(len(frames), 151)

    def test_plan_starts_unreviewed_without_fabricated_targets(self):
        plan = self.plan()
        self.assertTrue(all(row["review_status"] == "not_reviewed" for row in plan["frames"]))
        self.assertTrue(all(set(row) == {"frame_index", "time_s", "split", "secondary_review", "review_status"}
                            for row in plan["frames"]))
        self.assertIsNone(plan["matching_tolerance_um"])
        self.assertNotIn("annotations", plan)
        self.assertNotIn("targets", plan)
        self.assertNotIn("plan_sha256", plan)

    def test_secondary_review_is_fixed_and_stratified(self):
        plan = self.plan()
        selected = plan["secondary_review_frames"]
        self.assertEqual(selected, [19, 34, 47, 49, 53, 81, 90, 105, 124, 125])
        self.assertEqual(len(set(selected)), 10)
        self.assertEqual(sum(i < 60 for i in selected), 5)
        self.assertEqual(sum(i >= 75 for i in selected), 5)
        self.assertFalse(any(60 <= i < 75 for i in selected))
        self.assertEqual([r["frame_index"] for r in plan["frames"] if r["secondary_review"]], selected)
        self.assertEqual(plan["seed"], 20261118)

    def test_selection_replays_and_does_not_use_timestamps_or_source_image_content(self):
        first = self.plan()
        self.assertEqual(first, self.plan())
        other = self.plan(times_s=[400 + i * 4.01 for i in range(151)], source_sha256="b" * 64)
        self.assertEqual(first["secondary_review_frames"], other["secondary_review_frames"])
        self.assertNotEqual(first["secondary_review_frames"], self.plan(seed=20261119)["secondary_review_frames"])

    def test_measured_times_are_normalized_without_forcing_nominal_cadence(self):
        measured = [10.0 + i * 4.0 for i in range(151)]
        measured[1] += 0.125
        plan = self.plan(times_s=measured)
        self.assertEqual(plan["frames"][0]["time_s"], 0.0)
        self.assertEqual(plan["frames"][1]["time_s"], 4.125)
        self.assertEqual(plan["frames"][-1]["time_s"], 600.0)
        self.assertIn("Native ND2", plan["timebase"])

    def test_metadata_records_calibration_and_prior_exposure(self):
        plan = self.plan(source_sha256="AB" * 32)
        self.assertEqual(plan["source_name"], "Celegans_01_stack_timing1111.nd2")
        self.assertEqual(plan["source_sha256"], "ab" * 32)
        self.assertEqual((plan["width_px"], plan["height_px"], plan["frame_count"]), (1024, 1024, 151))
        self.assertEqual(plan["pixel_um"], self.pixel)
        self.assertEqual(plan["primary_channel"], "GFP")
        self.assertEqual(plan["context_channels"], ["RFP", "TD"])
        self.assertEqual(plan["prior_preview_frames"], [0, 38, 75, 112, 150])
        self.assertIn("not wholly unseen", plan["held_out_disclosure"])
        self.assertIn("not independent biological replicates", plan["held_out_disclosure"])
        self.assertIn("not stage coordinates", plan["coordinate_convention"])

    def test_inputs_and_independent_plans_are_not_mutated(self):
        before = list(self.times)
        plan = self.plan()
        plan["frames"][0]["review_status"] = "reviewed"
        plan["context_channels"].append("invented")
        self.assertEqual(self.times, before)
        fresh = self.plan()
        self.assertEqual(fresh["frames"][0]["review_status"], "not_reviewed")
        self.assertEqual(fresh["context_channels"], ["RFP", "TD"])

    def test_rejects_wrong_count_or_non_numeric_time_input(self):
        for value in ([], self.times[:-1], self.times + [604], None, "0123"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    self.plan(times_s=value)
        for value in (None, "4", True, float("nan"), float("inf"), -float("inf")):
            times = list(self.times)
            times[1] = value
            with self.subTest(timestamp=value):
                with self.assertRaises(ValueError):
                    self.plan(times_s=times)

    def test_rejects_duplicate_reversed_or_overflowing_elapsed_times(self):
        for times in ([0.0] * 151, list(reversed(self.times)),
                      [-1e308] + [float(i) for i in range(1, 150)] + [1e308]):
            with self.assertRaises(ValueError):
                self.plan(times_s=times)

    def test_rejects_invalid_source_hash_calibration_and_seed(self):
        for sha in (None, "", "a" * 63, "g" * 64, " a" * 32):
            with self.subTest(sha=sha):
                with self.assertRaises(ValueError):
                    self.plan(source_sha256=sha)
        for pixel in (0, -1, True, "0.5", None, float("nan"), float("inf")):
            with self.subTest(pixel=pixel):
                with self.assertRaises(ValueError):
                    self.plan(pixel_um=pixel)
        for seed in (True, -1, 1.5, "20261118", None):
            with self.subTest(seed=seed):
                with self.assertRaises(ValueError):
                    self.plan(seed=seed)


class PlanDigestTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_frame_plan([i * 4.0 for i in range(151)], "a" * 64, 0.5066912885485768)

    def test_digest_is_canonical_and_can_be_embedded(self):
        digest = plan_digest(self.plan)
        reordered = dict(reversed(list(self.plan.items())))
        reordered["frames"] = [dict(reversed(list(row.items()))) for row in self.plan["frames"]]
        self.assertEqual(plan_digest(reordered), digest)
        embedded = {**self.plan, "plan_sha256": digest}
        self.assertEqual(plan_digest(embedded), digest)
        canonical = json.dumps(self.plan, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.assertEqual(digest, hashlib.sha256(canonical).hexdigest())
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, "76d73d03106e955db206cecba1001e0aa4fcc707ce9c4002381afe7ae0fd06ca")

    def test_design_or_source_changes_change_digest(self):
        baseline = plan_digest(self.plan)
        for field, replacement in (("source_sha256", "b" * 64), ("pixel_um", 0.6),
                                   ("matching_tolerance_um", 1.0)):
            changed = copy.deepcopy(self.plan)
            changed[field] = replacement
            self.assertNotEqual(plan_digest(changed), baseline)
        changed = copy.deepcopy(self.plan)
        changed["frames"][1]["time_s"] += 0.001
        self.assertNotEqual(plan_digest(changed), baseline)

    def test_invalid_json_numbers_and_non_mapping_are_rejected(self):
        with self.assertRaises(TypeError):
            plan_digest([])
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                plan_digest({"invalid": value})


class CsvSchemaTests(unittest.TestCase):
    def test_exact_annotation_columns_and_visibility_states(self):
        self.assertEqual(annotation_fieldnames(), [
            "source_sha256", "plan_sha256", "reviewer_id", "target_id", "frame_index",
            "time_s", "split", "channel", "visibility", "x_px", "y_px", "x_um", "y_um",
            "reason", "notes", "reviewed_at",
        ])
        self.assertEqual(VISIBILITY_STATES, ("visible", "uncertain", "not_visible"))

    def test_exact_frame_review_columns_and_statuses(self):
        self.assertEqual(frame_review_fieldnames(), [
            "source_sha256", "plan_sha256", "reviewer_id", "frame_index", "time_s",
            "split", "review_status", "notes", "reviewed_at",
        ])
        self.assertEqual(FRAME_REVIEW_STATES, ("not_reviewed", "reviewed", "needs_review"))
        self.assertNotIn("visible_spot_count", frame_review_fieldnames())

    def test_schema_lists_are_fresh(self):
        original_annotations = annotation_fieldnames()
        altered = annotation_fieldnames()
        altered.append("unexpected")
        self.assertEqual(annotation_fieldnames(), original_annotations)
        original_frames = frame_review_fieldnames()
        altered = frame_review_fieldnames()
        altered.clear()
        self.assertEqual(frame_review_fieldnames(), original_frames)


if __name__ == "__main__":
    unittest.main()
