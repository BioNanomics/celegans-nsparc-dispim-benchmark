"""Scale test: the full pipeline on a study-sized, FABRICATED dataset.

Every number here is random and has no biological meaning. The generated files are
labeled FABRICATED and are written to a temporary folder, never into the repository.
"""

import contextlib
import csv
import hashlib
import io
import json
import math
import random
import tempfile
import time
import unittest
from collections import defaultdict
from pathlib import Path

from celegans_benchmark.cli import main
from celegans_benchmark.metrics import GROUPS, load_data

ROOT = Path(__file__).resolve().parents[1]
ARMS = [("NSPARC_60s", "E60", 60, 451), ("NSPARC_180s", "E180", 180, 150), ("CONTROL", "CTL", None, 0)]
PER_ARM = 10
EXCLUDED = {"E60_03", "E180_07"}
SLOW = {"E60_04", "E180_04"}          # measured interval 20% over plan
NO_POWER, NO_SHA, NO_MODE = "E60_06", "E60_08", "E180_10"


def _write(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def generate(out: Path, seed: int = 20260421, audit_every: int = 3) -> Path:
    """Write five FABRICATED CSVs: 10 embryos per arm, up to 451 volumes, mixed all/near+far frames."""
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    acq_cols = (ROOT / "data" / "templates" / "acquisitions.csv").read_text().splitlines()[0].split(",")
    acq, outcomes, nuclei, lineage, milestones = [], [], [], [], []
    for group, prefix, interval, nvol in ARMS:
        for i in range(1, PER_ARM + 1):
            eid = f"{prefix}_{i:02d}"
            row = {c: "" for c in acq_cols}
            row.update(embryo_id=eid, group=group, strain="BV514", reporter="mCherry",
                       temperature_c="20", notes="FABRICATED")
            if interval:
                measured = interval * 1.2 if eid in SLOW else interval + rng.choice([0, 1])
                row.update(planned_interval_s=interval, measured_interval_s=f"{measured:g}",
                           recorded_volumes=nvol, power_at_sample_mw="" if eid == NO_POWER else "1.2",
                           nsparc_mode="" if eid == NO_MODE else "processed",
                           raw_sha256="" if eid == NO_SHA else hashlib.sha256(eid.encode()).hexdigest())
            else:
                row.update(recorded_volumes=0)
            acq.append(row)

            u = rng.random()
            hatched = "1" if u < 0.8 else ("0" if u < 0.9 else "")
            outcomes.append({
                "embryo_id": eid, "hatched": hatched,
                "hatch_t_min": 690 + rng.randint(-15, 15) if hatched == "1" else "",
                "abnormal_development": rng.choice(["0", "0", "0", "1"]),
                "excluded": "1" if eid in EXCLUDED else "0",
                "exclusion_reason": "FABRICATED mounting failure" if eid in EXCLUDED else "",
                "notes": "FABRICATED"})
            milestones.append({"embryo_id": eid, "milestone": "twofold",
                               "t_min": 400 + rng.randint(-20, 20), "notes": "FABRICATED"})
            if not interval:
                continue

            for n, v in enumerate(range(0, nvol, audit_every)):
                count = max(1, 4 + int(380 * (v / (nvol - 1)) ** 1.6) + rng.randint(-2, 2))
                fn = max(0, min(count, round(rng.gauss(count * (0.01 + 0.0004 * count), 1.0))))
                fp = max(0, round(rng.gauss(count * 0.01, 0.8)))
                t = round(v * interval / 60, 4)
                if (i + n) % 5 == 0:   # near/far partition, split without losing any nucleus
                    near = count // 2
                    parts = [("near", near, fn // 2, fp // 2),
                             ("far", count - near, fn - fn // 2, fp - fp // 2)]
                else:
                    parts = [("all", count, fn, fp)]
                for region, manual, f_n, f_p in parts:
                    nuclei.append({"embryo_id": eid, "volume_index": v, "t_min": t,
                                   "manual_cell_count": manual, "tp": manual - f_n,
                                   "fp": f_p, "fn": f_n, "depth_region": region})
            for k in range(40):
                stage = rng.randint(2, 250)
                verified = rng.random() < 0.9
                lineage.append({"embryo_id": eid, "event_id": f"ev{k:03d}",
                                "t_min": round(rng.uniform(0, 450), 1), "stage_cell_count": stage,
                                "verified": int(verified),
                                "correct": int(rng.random() < max(0.5, 0.97 - 0.001 * stage)) if verified else ""})

    _write(out / "acquisitions.csv", acq_cols, acq)
    _write(out / "embryo_outcomes.csv", list(outcomes[0]), outcomes)
    _write(out / "nuclei_qc.csv", ["embryo_id", "volume_index", "t_min", "manual_cell_count",
                                   "tp", "fp", "fn", "depth_region"], nuclei)
    _write(out / "lineage_qc.csv", ["embryo_id", "event_id", "t_min", "stage_cell_count",
                                    "verified", "correct"], lineage)
    _write(out / "milestones.csv", ["embryo_id", "milestone", "t_min", "notes"], milestones)
    (out / "README_FABRICATED.txt").write_text(
        "FABRICATED data generated for software scale testing. Random numbers; no biological meaning.\n")
    return out


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class ScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.data = generate(base / "synthetic_large")        # 'synthetic' in the name -> auto banner
        cls.out = base / "report"
        cls.stdout, cls.stderr = io.StringIO(), io.StringIO()
        start = time.perf_counter()
        with contextlib.redirect_stdout(cls.stdout), contextlib.redirect_stderr(cls.stderr):
            cls.code = main(["report", "--data-dir", str(cls.data), "--output-dir", str(cls.out)])
        cls.elapsed = time.perf_counter() - start

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_pipeline_succeeds_quickly(self):
        self.assertEqual(self.code, 0, self.stderr.getvalue())
        self.assertLess(self.elapsed, 30)

    def test_all_outputs_written(self):
        for name in ("groups", "embryos", "stage_qc", "lineage_stage_qc", "depth_qc",
                     "feasibility_gates", "feasibility_gates_by_embryo", "audited_timeline",
                     "milestones"):
            self.assertTrue((self.out / f"{name}.csv").exists(), name)
        for name in ("report.json", "run_info.json", "summary.md", "IMPORTANT_README.txt"):
            self.assertTrue((self.out / name).exists(), name)

    def test_dataset_has_study_size(self):
        ds = load_data(self.data)
        self.assertEqual(len(ds.acquisitions), 30)
        self.assertEqual(max(int(r["recorded_volumes"]) for r in ds.acquisitions), 451)
        regions = {r["depth_region"] for r in ds.nuclei}
        self.assertEqual(regions, {"all", "near", "far"})
        self.assertGreater(len(ds.nuclei), 2000)  # ~2000 frames: 10 x 151 + 10 x 50, plus near/far pairs

    def test_group_counts_add_up(self):
        groups = {g["group"]: g for g in read(self.out / "groups.csv")}
        self.assertEqual({g: int(groups[g]["n_attempted"]) for g in GROUPS}, {g: 10 for g in GROUPS})
        self.assertEqual(int(groups["NSPARC_60s"]["n_excluded"]), 1)
        self.assertEqual(int(groups["NSPARC_180s"]["n_excluded"]), 1)
        self.assertEqual(int(groups["CONTROL"]["n_excluded"]), 0)
        hatched = {r["embryo_id"]: r["hatched"] for r in read(self.data / "embryo_outcomes.csv")}
        for group, prefix, *_ in ARMS:
            ids = [e for e in hatched if e.startswith(prefix) and e not in EXCLUDED]
            unknown = sum(1 for e in ids if hatched[e] == "")
            self.assertEqual(int(groups[group]["hatching_unknown_n"]), unknown, group)
            self.assertEqual(int(groups[group]["hatching_known_n"]), len(ids) - unknown, group)

    def test_counts_match_independent_recomputation(self):
        """tp/fp/fn and frames recomputed straight from the CSV rows; no double counting."""
        nuc = [r for r in read(self.data / "nuclei_qc.csv") if r["embryo_id"] not in EXCLUDED]
        groups = {g["group"]: g for g in read(self.out / "groups.csv")}
        for group, prefix, *_ in ARMS[:2]:
            rows = [r for r in nuc if r["embryo_id"].startswith(prefix)]
            for field in ("tp", "fp", "fn"):
                self.assertEqual(int(groups[group][field]), sum(int(r[field]) for r in rows), field)
            frames = {(r["embryo_id"], r["volume_index"]) for r in rows}
            self.assertEqual(int(groups[group]["audited_volumes"]), len(frames), group)
        all_frames = {(r["embryo_id"], r["volume_index"]) for r in nuc}
        self.assertEqual(sum(int(r["audited_volumes"]) for r in read(self.out / "stage_qc.csv")),
                         len(all_frames))

    def test_stage_uses_frame_total_for_near_far(self):
        nuc = [r for r in read(self.data / "nuclei_qc.csv") if r["embryo_id"] not in EXCLUDED]
        totals = defaultdict(int)
        for r in nuc:
            totals[(r["embryo_id"], r["volume_index"])] += int(r["manual_cell_count"])
        def stage(n):
            return "<16" if n < 16 else "16-49" if n < 50 else "50-99" if n < 100 else "100-199" if n < 200 else "200+"
        expected = defaultdict(int)
        for (eid, _), total in totals.items():
            expected[(next(g for g, p, *_ in ARMS if eid.startswith(p)), stage(total))] += 1
        got = {(r["group"], r["stage"]): int(r["audited_volumes"]) for r in read(self.out / "stage_qc.csv")}
        self.assertEqual(got, dict(expected))

    def test_depth_rows_match_csv(self):
        nuc = [r for r in read(self.data / "nuclei_qc.csv") if r["embryo_id"] not in EXCLUDED]
        depth = defaultdict(int)
        for r in read(self.out / "depth_qc.csv"):
            depth[r["depth_region"]] += int(r["audited_volumes"])
        for region in ("all", "near", "far"):
            self.assertEqual(depth[region], sum(1 for r in nuc if r["depth_region"] == region), region)
        self.assertEqual(depth["near"], depth["far"])   # always given as a pair

    def test_lineage_counts_match(self):
        links = [r for r in read(self.data / "lineage_qc.csv")
                 if r["embryo_id"] not in EXCLUDED and r["verified"] == "1"]
        total = sum(int(r["verified_lineage_events"]) for r in read(self.out / "lineage_stage_qc.csv"))
        correct = sum(int(r["correct_lineage_events"]) for r in read(self.out / "lineage_stage_qc.csv"))
        self.assertEqual(total, len(links))
        self.assertEqual(correct, sum(int(r["correct"]) for r in links))

    def test_gates_cover_both_nsparc_groups(self):
        rows = read(self.out / "feasibility_gates.csv")
        self.assertEqual({(r["group"], r["gate"]) for r in rows},
                         {(g, gate) for g in ("NSPARC_60s", "NSPARC_180s")
                          for gate in ("detection_recall", "lineage_correct")})
        self.assertTrue(all(r["status"] in ("pass", "fail") for r in rows))  # data exists: evaluable
        embryo_rows = read(self.out / "feasibility_gates_by_embryo.csv")
        self.assertEqual(len(embryo_rows), 2 * 18)    # 18 included NSPARC embryos x 2 gates

    def test_expected_warnings_recorded(self):
        warnings = json.loads((self.out / "run_info.json").read_text())["warnings"]
        text = "\n".join(warnings)
        for eid in SLOW:
            self.assertRegex(text, rf"{eid}: measured interval")
        self.assertIn(f"{NO_POWER}: blank power_at_sample_mw", text)
        self.assertIn(f"{NO_SHA}: blank raw_sha256", text)
        self.assertIn(f"{NO_MODE}: blank nsparc_mode", text)
        self.assertNotIn("CTL_", text)       # CONTROL rows are never warned about
        self.assertIn("WARNING", self.stderr.getvalue())

    def test_summary_is_labeled_fabricated(self):
        summary = (self.out / "summary.md").read_text(encoding="utf-8")
        self.assertIn("FABRICATED", summary)
        self.assertIn("## Feasibility gates", summary)

    def test_json_is_strict(self):
        text = (self.out / "report.json").read_text()
        json.loads(text, parse_constant=lambda c: self.fail(f"non-finite {c}"))
        self.assertFalse(any(isinstance(v, float) and not math.isfinite(v)
                             for v in json.loads(text)["groups"][0].values()))

    # ---- generator and stress -------------------------------------------
    def test_generator_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, c = (generate(Path(tmp) / n, seed=s) for n, s in (("a", 1), ("b", 1), ("c", 2)))
            same = lambda p, q: all((p / f).read_bytes() == (q / f).read_bytes()
                                    for f in ("nuclei_qc.csv", "lineage_qc.csv"))
            self.assertTrue(same(a, b))
            self.assertFalse(same(a, c))

    def test_every_volume_audited_still_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = generate(Path(tmp) / "synthetic_dense", audit_every=1)
            out = Path(tmp) / "out"
            start = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = main(["report", "--data-dir", str(data), "--output-dir", str(out)])
            self.assertEqual(code, 0)
            self.assertLess(time.perf_counter() - start, 60)
            self.assertGreater(len(read(data / "nuclei_qc.csv")), 7000)  # 10 x 451 + 10 x 150 frames


if __name__ == "__main__":
    unittest.main()
