"""CLI entrypoint for a transparent CSV-based descriptive analysis."""

from __future__ import annotations

import argparse
import sys
from .metrics import (DEFAULT_INTERVAL_TOLERANCE, STAGES, DataError, Gates, load_data,
                      plot_audited_timeline, stage_of, summarize, write_reports)
from . import __version__
from .audit import check_audit, read_spot_counts, select_frames, write_selection
from .checksum import sha256_file, verify_raw
from .provenance import build_run_info, write_run_info
from .runfolder import init_run
from .summary import auto_label, render_summary, write_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="celegans-benchmark",
        description="Validate manually curated *C. elegans* pilot tables and generate descriptive QC.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Check CSV schemas, values, and embryo references")
    validate.add_argument("--data-dir", required=True, help="Folder containing five run CSVs")
    validate.add_argument("--interval-tolerance", type=float, default=DEFAULT_INTERVAL_TOLERANCE,
                     help="Warn if measured_interval_s exceeds planned_interval_s by more than this "
                          "fraction (default 0.05 = 5%%)")
    report = sub.add_parser("report", help="Create CSV/JSON descriptive tables")
    report.add_argument("--data-dir", required=True)
    report.add_argument("--output-dir", required=True)
    report.add_argument("--interval-tolerance", type=float, default=DEFAULT_INTERVAL_TOLERANCE,
                     help="Warn if measured_interval_s exceeds planned_interval_s by more than this "
                          "fraction (default 0.05 = 5%%)")
    report.add_argument("--recall-threshold", type=float, default=Gates.recall_min,
                        help="Provisional detection-recall target (default 0.95)")
    report.add_argument("--lineage-threshold", type=float, default=Gates.lineage_min,
                        help="Provisional lineage-correct target (default 0.90)")
    report.add_argument("--recall-through-cells", type=int, default=Gates.recall_through_cells,
                        help="Audited frames with at most this many cells count for recall (default 100)")
    report.add_argument("--label", help="Banner for summary.md, e.g. 'PRACTICE DATA' "
                                        "(example data in a 'synthetic' folder is labeled FABRICATED automatically)")
    report.add_argument("--plot", action="store_true", help="Plot manually audited cell counts (Matplotlib optional)")
    init = sub.add_parser("init-run", help="Create a run folder with empty template CSVs (never overwrites)")
    init.add_argument("--run-dir", required=True, help="Private folder to create/fill (keep outside public Git)")
    init.add_argument("--templates-dir", help="Template CSV folder (default: data/templates in the repo)")
    checksum = sub.add_parser("checksum", help="Print the SHA-256 of a (large) file")
    checksum.add_argument("--file", required=True)
    verify = sub.add_parser("verify-raw", help="Check raw_sha256 in acquisitions.csv against the files")
    verify.add_argument("--data-dir", required=True)
    verify.add_argument("--raw-root", help="Folder for relative raw_data_uri values")
    select = sub.add_parser("select-frames",
                            help="Choose audit frames per stage in advance from tracker spot counts")
    select.add_argument("--spot-counts", required=True, help="CSV with header time_point,spots")
    select.add_argument("--output", required=True, help="Frame list to create (never overwritten)")
    select.add_argument("--per-stage", type=int, default=2, help="Frames per stage (default 2)")
    select.add_argument("--seed", type=int, default=0, help="Random seed; record it (default 0)")
    select.add_argument("--first-time-point", type=int, default=0,
                        help="Number of the tracker's first time point: 0 (e.g. Mastodon) or 1 "
                             "(e.g. StarryNite/AceTree); volume_index = time_point - this (default 0)")
    check = sub.add_parser("check-audit",
                           help="Compare tp+fp of audited frames with the tracker's spot counts")
    check.add_argument("--data-dir", required=True)
    check.add_argument("--embryo-id", required=True, help="Embryo the spot-count file belongs to")
    check.add_argument("--spot-counts", required=True, help="CSV with header time_point,spots")
    check.add_argument("--first-time-point", type=int, default=0,
                        help="Number of the tracker's first time point: 0 (e.g. Mastodon) or 1 "
                             "(e.g. StarryNite/AceTree); volume_index = time_point - this (default 0)")
    args = parser.parse_args(argv)
    try:
        if args.command == "check-audit":
            results = check_audit(args.data_dir, args.embryo_id, args.spot_counts, args.first_time_point)
            if not results:
                print(f"No audited frames for {args.embryo_id}; nothing to check.")
                return 0
            for r in results:
                tracker = "unknown" if r["tracker_spots"] is None else r["tracker_spots"]
                print(f"{r['embryo_id']} volume {r['volume_index']}: {r['status']} "
                      f"(tp+fp={r['tp_plus_fp']}, tracker={tracker})")
            mismatches = sum(1 for r in results if r["status"] == "mismatch")
            print(f"{mismatches} mismatch(es) in {len(results)} audited frame(s). "
                  "A mismatch means a counting slip or the wrong frame; recount, don't adjust.")
            return 1 if mismatches else 0
        if args.command == "select-frames":
            counts, blank = read_spot_counts(args.spot_counts)
            rows = select_frames(counts, args.per_stage, args.seed, args.first_time_point)
            if not rows:
                raise DataError("no frames with a known spot count; nothing to select")
            digest = write_selection(rows, args.output)
            for stage in STAGES:
                picked = sum(1 for r in rows if r["stage"] == stage)
                available = sum(1 for n in counts.values() if stage_of(n) == stage)
                print(f"{stage}: {picked} of {available} frame(s) selected" if available
                      else f"{stage}: not selectable (no frames at this stage)")
            if blank:
                print(f"{len(blank)} time point(s) with blank spot count were not eligible.")
            print(f"Wrote {args.output} (seed {args.seed}, {args.per_stage} per stage)")
            print(f"SHA-256: {digest}")
            print("Record this hash before auditing; it shows the frames were fixed in advance. "
                  "Stages are estimated from tracker spots, not manual counts.")
            return 0
        if args.command == "checksum":
            print(f"{sha256_file(args.file)}  {args.file}")
            return 0
        if args.command == "verify-raw":
            results = verify_raw(args.data_dir, args.raw_root)
            for r in results:
                print(f"{r['embryo_id']}: {r['status']}")
            if not results:
                print("No embryo rows found; nothing to verify.")
            return 1 if any(r["status"] in ("mismatch", "missing", "invalid_hash")
                            for r in results) else 0
        if args.command == "init-run":
            for path in init_run(args.run_dir, args.templates_dir):
                print(f"Wrote {path}")
            print("Created empty protocol CSVs. Keep this folder outside public Git.")
            return 0
        data = load_data(args.data_dir, args.interval_tolerance)
        for warning in data.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        print(f"Validated {len(data.acquisitions)} registered embryos, "
              f"{len(data.nuclei)} nuclei-QC rows, {len(data.lineage)} lineage-QC rows.")
        if not data.acquisitions:
            print("No embryo rows found. Empty templates validated; no results to analyze.")
        if args.command == "report":
            gates = Gates(args.recall_threshold, args.lineage_threshold, args.recall_through_cells)
            result = summarize(data, gates)
            paths = write_reports(result, args.output_dir)
            paths.append(write_run_info(
                build_run_info(args.data_dir, gates, args.interval_tolerance, data.warnings),
                args.output_dir))
            paths.append(write_summary(
                render_summary(result, gates, data.warnings,
                               label=auto_label(args.data_dir, args.label)),
                args.output_dir))
            if args.plot:
                figure = plot_audited_timeline(result, args.output_dir)
                if figure is not None:
                    paths.append(figure)
            for path in paths:
                print(f"Wrote {path}")
            print("IMPORTANT: These are descriptive metrics, not an equivalence or safety test.")
    except (DataError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0
