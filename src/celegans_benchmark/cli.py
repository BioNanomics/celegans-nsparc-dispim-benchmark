"""CLI entrypoint for a transparent CSV-based descriptive analysis."""

from __future__ import annotations

import argparse
import sys
from .metrics import DataError, load_data, plot_audited_timeline, summarize, write_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="celegans-benchmark",
        description="Validate manually curated *C. elegans* pilot tables and generate descriptive QC.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Check CSV schemas, values, and embryo references")
    validate.add_argument("--data-dir", required=True, help="Folder containing five run CSVs")
    report = sub.add_parser("report", help="Create CSV/JSON descriptive tables")
    report.add_argument("--data-dir", required=True)
    report.add_argument("--output-dir", required=True)
    report.add_argument("--plot", action="store_true", help="Plot manually audited cell counts (Matplotlib optional)")
    args = parser.parse_args(argv)
    try:
        data = load_data(args.data_dir)
        print(f"Validated {len(data.acquisitions)} registered embryos, "
              f"{len(data.nuclei)} nuclei-QC rows, {len(data.lineage)} lineage-QC rows.")
        if not data.acquisitions:
            print("No embryo rows found. Empty templates validated; no results to analyze.")
        if args.command == "report":
            result = summarize(data)
            paths = write_reports(result, args.output_dir)
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
