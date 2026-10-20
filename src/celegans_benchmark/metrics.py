"""Read, validate and summarize manually curated embryo/QC CSVs.

The independent biological unit is the embryo. Frame-level pooled rates here are
technical descriptors, not independent samples for biological hypothesis tests.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Any


TABLES: dict[str, set[str]] = {
    "acquisitions": {"embryo_id", "group", "strain", "reporter", "temperature_c",
                     "planned_interval_s", "measured_interval_s", "recorded_volumes"},
    "embryo_outcomes": {"embryo_id", "hatched", "hatch_t_min", "abnormal_development",
                        "excluded", "exclusion_reason"},
    "nuclei_qc": {"embryo_id", "volume_index", "t_min", "manual_cell_count",
                  "tp", "fp", "fn", "depth_region"},
    "lineage_qc": {"embryo_id", "event_id", "t_min", "stage_cell_count",
                   "verified", "correct"},
    "milestones": {"embryo_id", "milestone", "t_min"},
}
GROUPS = ("NSPARC_60s", "NSPARC_180s", "CONTROL")
STAGES = ("<16", "16-49", "50-99", "100-199", "200+")


class DataError(ValueError):
    """An invalid or internally inconsistent input dataset."""


@dataclass(frozen=True)
class Gates:
    """Provisional internal feasibility targets (see docs/ANALYSIS_PLAN.md); all adjustable."""
    recall_min: float = 0.95
    lineage_min: float = 0.90
    recall_through_cells: int = 100  # audited frames with <= this many cells count

    def __post_init__(self) -> None:
        for name in ("recall_min", "lineage_min"):
            value = getattr(self, name)
            if not (math.isfinite(value) and 0 <= value <= 1):
                raise DataError(f"{name} must be between 0 and 1, got {value!r}")
        if self.recall_through_cells < 0:
            raise DataError("recall_through_cells cannot be negative")


@dataclass
class Dataset:
    acquisitions: list[dict[str, str]]
    outcomes: list[dict[str, str]]
    nuclei: list[dict[str, str]]
    lineage: list[dict[str, str]]
    milestones: list[dict[str, str]]

    @property
    def embryos(self) -> dict[str, dict[str, str]]:
        return {r["embryo_id"]: r for r in self.acquisitions}


def _read(path: Path, required: set[str]) -> list[dict[str, str]]:
    if not path.exists():
        raise DataError(f"Missing required CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DataError(f"No CSV header found: {path}")
        missing = required.difference(reader.fieldnames)
        if missing:
            raise DataError(f"{path.name}: missing required columns: {', '.join(sorted(missing))}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise DataError(f"{path.name}: duplicate column names")
        rows: list[dict[str, str]] = []
        for line, row in enumerate(reader, start=2):
            if None in row:
                raise DataError(f"{path.name} line {line}: too many columns")
            clean = {k: (v or "").strip() for k, v in row.items()}
            if not any(clean.values()):
                continue
            if not clean.get("embryo_id"):
                raise DataError(f"{path.name} line {line}: embryo_id missing")
            rows.append(clean)
    return rows


def _number(value: str, name: str, *, required: bool = True,
            nonnegative: bool = False, integer: bool = False) -> float | int | None:
    if not value:
        if required:
            raise DataError(f"Missing numeric value: {name}")
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise DataError(f"{name}: expected number, got {value!r}") from exc
    if not math.isfinite(parsed):
        raise DataError(f"{name}: expected finite number")
    if integer and not parsed.is_integer():
        raise DataError(f"{name}: expected integer")
    if nonnegative and parsed < 0:
        raise DataError(f"{name}: cannot be negative")
    return int(parsed) if integer else parsed


def _flag(value: str, name: str, *, required: bool = False) -> int | None:
    if value == "" and not required:
        return None
    if value not in ("0", "1"):
        raise DataError(f"{name}: expected 1, 0 or blank, got {value!r}")
    return int(value)


def _unique(rows: list[dict[str, str]], name: str, *fields: str) -> None:
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in seen:
            raise DataError(f"{name}: duplicate {fields}: {key}")
        seen.add(key)


def load_data(data_dir: str | Path) -> Dataset:
    root = Path(data_dir)
    loaded = {stem: _read(root / f"{stem}.csv", required) for stem, required in TABLES.items()}
    ds = Dataset(acquisitions=loaded["acquisitions"], outcomes=loaded["embryo_outcomes"],
                 nuclei=loaded["nuclei_qc"], lineage=loaded["lineage_qc"],
                 milestones=loaded["milestones"])
    _unique(ds.acquisitions, "acquisitions", "embryo_id")
    _unique(ds.outcomes, "embryo_outcomes", "embryo_id")
    _unique(ds.nuclei, "nuclei_qc", "embryo_id", "volume_index")
    _unique(ds.lineage, "lineage_qc", "embryo_id", "event_id")
    _unique(ds.milestones, "milestones", "embryo_id", "milestone")
    known = ds.embryos

    for r in ds.acquisitions:
        eid = r["embryo_id"]
        if r["group"] not in GROUPS:
            raise DataError(f"{eid}: unknown group {r['group']!r}; expected {GROUPS}")
        if not r["strain"] or not r["reporter"]:
            raise DataError(f"{eid}: strain and reporter are required")
        if r["temperature_c"]:
            _number(r["temperature_c"], f"{eid}.temperature_c")
        for field in ("planned_interval_s", "measured_interval_s"):
            if r[field]:
                val = _number(r[field], f"{eid}.{field}", nonnegative=True)
                if val == 0:
                    raise DataError(f"{eid}.{field}: expected positive interval")
        _number(r["recorded_volumes"], f"{eid}.recorded_volumes", required=False,
                nonnegative=True, integer=True)
        if r["group"] == "CONTROL" and r["recorded_volumes"] not in ("", "0"):
            raise DataError(f"{eid}: CONTROL must not have fluorescence volumes")

    for table_name, table in (("embryo_outcomes", ds.outcomes), ("nuclei_qc", ds.nuclei),
                              ("lineage_qc", ds.lineage), ("milestones", ds.milestones)):
        for row in table:
            if row["embryo_id"] not in known:
                raise DataError(f"{table_name}: unknown embryo_id {row['embryo_id']!r}")

    for r in ds.outcomes:
        eid = r["embryo_id"]
        _flag(r["hatched"], f"{eid}.hatched")
        _flag(r["abnormal_development"], f"{eid}.abnormal_development")
        excluded = _flag(r["excluded"], f"{eid}.excluded")
        if excluded == 1 and not r["exclusion_reason"]:
            raise DataError(f"{eid}: excluded outcome needs exclusion_reason")
        _number(r["hatch_t_min"], f"{eid}.hatch_t_min", required=False, nonnegative=True)
        if r["hatched"] == "0" and r["hatch_t_min"]:
            raise DataError(f"{eid}: no hatch time expected when hatched=0")
        if r["hatched"] != "1" and r["hatch_t_min"]:
            raise DataError(f"{eid}: hatch time only allowed when hatched=1")

    for r in ds.nuclei:
        eid = r["embryo_id"]
        if known[eid]["group"] == "CONTROL":
            raise DataError(f"{eid}: non-imaged CONTROL cannot have fluorescence nuclei QC")
        idx = _number(r["volume_index"], f"{eid}.volume_index", integer=True, nonnegative=True)
        _number(r["t_min"], f"{eid}.t_min")
        manual = _number(r["manual_cell_count"], f"{eid}.manual_cell_count",
                         integer=True, nonnegative=True)
        tp, fp, fn = (_number(r[field], f"{eid}.{field}", integer=True, nonnegative=True)
                      for field in ("tp", "fp", "fn"))
        if manual != tp + fn:
            raise DataError(f"{eid} volume {idx}: manual_cell_count must equal tp+fn")
        if r["depth_region"] != "all":
            raise DataError(f"{eid} volume {idx}: this starter tool accepts depth_region='all' only")
        vols = known[eid]["recorded_volumes"]
        if vols and idx >= int(vols):
            raise DataError(f"{eid}: QC volume_index {idx} >= recorded_volumes {vols}")

    for r in ds.lineage:
        eid = r["embryo_id"]
        if known[eid]["group"] == "CONTROL":
            raise DataError(f"{eid}: non-imaged CONTROL cannot have fluorescence lineage QC")
        _number(r["t_min"], f"{eid}.lineage.t_min")
        _number(r["stage_cell_count"], f"{eid}.stage_cell_count", integer=True,
                nonnegative=True)
        verified = _flag(r["verified"], f"{eid}.verified", required=True)
        correct = _flag(r["correct"], f"{eid}.correct")
        if verified == 1 and correct is None:
            raise DataError(f"{eid}: correct is required for a verified lineage event")
        if verified == 0 and correct is not None:
            raise DataError(f"{eid}: correct must be blank for unverified event")

    for r in ds.milestones:
        if not r["milestone"]:
            raise DataError(f"{r['embryo_id']}: milestone name cannot be blank")
        _number(r["t_min"], f"{r['embryo_id']}.milestone.t_min")
    return ds


def stage_of(nuclei: int) -> str:
    for stage, upper in zip(STAGES, (16, 50, 100, 200)):
        if nuclei < upper:
            return stage
    return STAGES[-1]


def _rates(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    def frac(a: int, b: int) -> float | None:
        return a / b if b else None
    return {"precision": frac(tp, tp + fp), "recall": frac(tp, tp + fn),
            "f1": frac(2 * tp, 2 * tp + fp + fn)}


def _gate_counts(qc: list[dict[str, str]], links: list[dict[str, str]],
                 gates: Gates) -> dict[str, tuple[int, int, float]]:
    """(numerator, denominator, threshold) per gate for one set of audited rows."""
    frames = [r for r in qc if int(r["manual_cell_count"]) <= gates.recall_through_cells]
    return {
        "detection_recall": (sum(int(r["tp"]) for r in frames),
                             sum(int(r["tp"]) + int(r["fn"]) for r in frames), gates.recall_min),
        "lineage_correct": (sum(int(r["correct"]) for r in links), len(links), gates.lineage_min),
    }


def _gate_row(num: int, den: int, threshold: float) -> dict[str, Any]:
    """Pass/fail needs a denominator; with none the gate is not evaluable, never a fail."""
    value = num / den if den else None
    status = "not_evaluable" if value is None else ("pass" if value >= threshold else "fail")
    return {"threshold": threshold, "numerator": num, "denominator": den,
            "value": value, "status": status}


def summarize(ds: Dataset, gates: Gates | None = None) -> dict[str, list[dict[str, Any]]]:
    gates = gates or Gates()
    outcomes = {r["embryo_id"]: r for r in ds.outcomes}
    active = {r["embryo_id"]: r for r in ds.acquisitions
              if outcomes.get(r["embryo_id"], {}).get("excluded") != "1"}
    by_emb_nuc: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_emb_lin: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in ds.nuclei:
        if r["embryo_id"] in active:
            by_emb_nuc[r["embryo_id"]].append(r)
    for r in ds.lineage:
        if r["embryo_id"] in active and r["verified"] == "1":
            by_emb_lin[r["embryo_id"]].append(r)

    embryos: list[dict[str, Any]] = []
    for eid, a in sorted(active.items()):
        qc = by_emb_nuc[eid]
        links = by_emb_lin[eid]
        tp = sum(int(r["tp"]) for r in qc)
        fp = sum(int(r["fp"]) for r in qc)
        fn = sum(int(r["fn"]) for r in qc)
        outcome = outcomes.get(eid, {})
        hatching = outcome.get("hatched", "")
        embryos.append({
            "embryo_id": eid, "group": a["group"],
            "n_audited_volumes": len(qc), "tp": tp, "fp": fp, "fn": fn,
            **_rates(tp, fp, fn),
            "max_audited_cell_count": max((int(r["manual_cell_count"]) for r in qc), default=None),
            "verified_lineage_events": len(links),
            "correct_lineage_events": sum(int(r["correct"]) for r in links),
            "lineage_correct_fraction": (
                sum(int(r["correct"]) for r in links) / len(links) if links else None),
            "hatched": int(hatching) if hatching in ("0", "1") else None,
            "hatch_t_min": float(outcome["hatch_t_min"]) if outcome.get("hatch_t_min") else None,
            "abnormal_development": (int(outcome["abnormal_development"])
                                     if outcome.get("abnormal_development") in ("0", "1") else None),
        })

    by_group: list[dict[str, Any]] = []
    for group in GROUPS:
        rows = [r for r in embryos if r["group"] == group]
        excluded = [r for r in ds.acquisitions if r["group"] == group and
                    outcomes.get(r["embryo_id"], {}).get("excluded") == "1"]
        tp, fp, fn = (sum(r[field] for r in rows) for field in ("tp", "fp", "fn"))
        hatch_known = [r for r in rows if r["hatched"] is not None]
        hatch_yes = sum(r["hatched"] for r in hatch_known)
        lineage_n = sum(r["verified_lineage_events"] for r in rows)
        lineage_correct = sum(r["correct_lineage_events"] for r in rows)
        by_group.append({
            "group": group, "n_attempted": len(rows) + len(excluded),
            "n_included": len(rows), "n_excluded": len(excluded),
            "hatching_known_n": len(hatch_known), "hatching_unknown_n": len(rows) - len(hatch_known),
            "hatching_n": hatch_yes,
            "hatching_fraction": hatch_yes / len(hatch_known) if hatch_known else None,
            "audited_volumes": sum(r["n_audited_volumes"] for r in rows),
            "tp": tp, "fp": fp, "fn": fn, **_rates(tp, fp, fn),
            "verified_lineage_events": lineage_n, "correct_lineage_events": lineage_correct,
            "lineage_correct_fraction": (lineage_correct / lineage_n if lineage_n else None),
            "max_audited_cell_count": max((r["max_audited_cell_count"] for r in rows
                                           if r["max_audited_cell_count"] is not None), default=None),
        })

    stage_totals: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"audited_volumes": 0, "tp": 0, "fp": 0, "fn": 0})
    timeline = []
    for r in ds.nuclei:
        eid = r["embryo_id"]
        if eid not in active:
            continue
        group = active[eid]["group"]
        stage = stage_of(int(r["manual_cell_count"]))
        vals = stage_totals[(group, stage)]
        vals["audited_volumes"] += 1
        for field in ("tp", "fp", "fn"):
            vals[field] += int(r[field])
        timeline.append({"embryo_id": eid, "group": group, "volume_index": int(r["volume_index"]),
                         "t_min": float(r["t_min"]), "manual_cell_count": int(r["manual_cell_count"])})
    stage_rows = [{"group": group, "stage": stage, **vals, **_rates(vals["tp"], vals["fp"], vals["fn"])}
                  for (group, stage), vals in sorted(stage_totals.items(),
                      key=lambda x: (GROUPS.index(x[0][0]), STAGES.index(x[0][1])))]

    lineage_totals: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"verified_lineage_events": 0, "correct_lineage_events": 0})
    for eid, links in by_emb_lin.items():
        for r in links:
            vals = lineage_totals[(active[eid]["group"], stage_of(int(r["stage_cell_count"])))]
            vals["verified_lineage_events"] += 1
            vals["correct_lineage_events"] += int(r["correct"])
    lineage_stage_rows = [
        {"group": group, "stage": stage, **vals,
         "lineage_correct_fraction": vals["correct_lineage_events"] / vals["verified_lineage_events"]}
        for (group, stage), vals in sorted(
            lineage_totals.items(), key=lambda x: (GROUPS.index(x[0][0]), STAGES.index(x[0][1])))]

    milestone_groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in ds.milestones:
        if r["embryo_id"] in active:
            milestone_groups[(active[r["embryo_id"]]["group"], r["milestone"])].append(float(r["t_min"]))
    milestones = [{"group": group, "milestone": label, "n": len(times),
                   "mean_t_min": mean(times), "sd_t_min": stdev(times) if len(times) > 1 else None}
                  for (group, label), times in sorted(milestone_groups.items())]

    embryo_gates = {eid: _gate_counts(by_emb_nuc[eid], by_emb_lin[eid], gates)
                    for eid in sorted(active) if active[eid]["group"] != "CONTROL"}
    gate_rows: list[dict[str, Any]] = []
    for group in GROUPS:
        if group == "CONTROL":  # never fluorescence-imaged: gates do not apply
            continue
        members = [counts for eid, counts in embryo_gates.items() if active[eid]["group"] == group]
        for gate in ("detection_recall", "lineage_correct"):
            threshold = gates.recall_min if gate == "detection_recall" else gates.lineage_min
            num = sum(m[gate][0] for m in members)
            den = sum(m[gate][1] for m in members)
            gate_rows.append({"group": group, "gate": gate, **_gate_row(num, den, threshold),
                              "n_embryos": sum(1 for m in members if m[gate][1])})
    gate_embryo_rows = [
        {"embryo_id": eid, "group": active[eid]["group"], "gate": gate, **_gate_row(*counts[gate])}
        for eid, counts in embryo_gates.items() for gate in ("detection_recall", "lineage_correct")]

    return {"groups": by_group, "embryos": embryos, "stage_qc": stage_rows,
            "lineage_stage_qc": lineage_stage_rows,
            "feasibility_gates": gate_rows, "feasibility_gates_by_embryo": gate_embryo_rows,
            "audited_timeline": sorted(timeline, key=lambda r: (r["embryo_id"], r["volume_index"])),
            "milestones": milestones}


def write_reports(report: dict[str, list[dict[str, Any]]], output_dir: str | Path) -> list[Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, rows in report.items():
        if not rows:
            continue
        path = directory / f"{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    path = directory / "report.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    written.append(path)
    note = directory / "IMPORTANT_README.txt"
    note.write_text(
        "Descriptive results only. Samples are embryos (not independent nuclei/frames).\n"
        "If input is examples/synthetic, these numbers are FABRICATED for software testing.\n"
        "Rates pooled across audited volumes are technical descriptors; do not use them\n"
        "as independent biological replicates or interpret them as microscope equivalence.\n"
        "An empty value means not measured or mathematically undefined, not zero.\n"
        "Feasibility gate thresholds are provisional internal targets, not diSPIM standards;\n"
        "'not_evaluable' means no data to judge, never a failure.\n",
        encoding="utf-8",
    )
    written.append(note)
    return written


def plot_audited_timeline(report: dict[str, list[dict[str, Any]]], output_dir: str | Path) -> Path | None:
    points = report["audited_timeline"]
    if not points:
        return None
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise DataError("Plot requested but matplotlib missing. Install: pip install -e '.[plots]'") from exc
    fig, ax = plt.subplots(figsize=(9, 5))
    for eid in sorted(set(row["embryo_id"] for row in points)):
        values = [r for r in points if r["embryo_id"] == eid]
        ax.plot([r["t_min"] for r in values], [r["manual_cell_count"] for r in values],
                marker="o", markersize=4, label=f"{eid} ({values[0]['group']})")
    ax.set(xlabel="Stage-aligned time (minutes; verify common time anchor)",
           ylabel="Manually verified nuclei (audited frames only)",
           title="Audited cell counts (not full trajectory)")
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    destination = Path(output_dir) / "audited_cell_counts.png"
    fig.savefig(destination, dpi=180)
    plt.close(fig)
    return destination
