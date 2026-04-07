#!/usr/bin/env python3
"""Convert Parquet files in a directory to CSV.

Example:
    python3 scripts/parquet_to_csv.py --input-dir Data/IPEDS_College_Scorecard/FieldOfStudy
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert Parquet files to CSV.")
    p.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing input .parquet files.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same as input).",
    )
    p.add_argument(
        "--glob",
        default="*.parquet",
        help="Glob for input files (default: *.parquet).",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing CSV files.",
    )
    return p.parse_args()


def iter_parquet_files(input_dir: Path, pattern: str) -> Iterable[Path]:
    return sorted(path for path in input_dir.glob(pattern) if path.is_file())


def main() -> int:
    args = parse_args()
    input_dir: Path = args.input_dir
    out_root: Path = args.output_dir if args.output_dir is not None else input_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    files = list(iter_parquet_files(input_dir, args.glob))
    if not files:
        raise FileNotFoundError(
            f"No files matched '{args.glob}' in {input_dir}"
        )

    out_root.mkdir(parents=True, exist_ok=True)

    for pq in files:
        rel = pq.relative_to(input_dir) if pq.is_relative_to(input_dir) else pq.name
        csv_path = (out_root / rel).with_suffix(".csv")
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        if csv_path.exists() and not args.overwrite:
            print(f"SKIP {pq.name} -> {csv_path} (exists)")
            continue

        df = pd.read_parquet(pq, engine="pyarrow")
        df.to_csv(csv_path, index=False)
        print(f"OK   {pq.name} -> {csv_path.name} ({len(df):,} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
