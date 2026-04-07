#!/usr/bin/env python3
"""Convert FOS slim CSV files to Parquet with validation.

Example:
    python3 scripts/csv_to_parquet_fos_slim.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert CSV files in a directory to Parquet files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("Data/processed/FOS_slim"),
        help="Directory containing input CSV files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Data/processed/FOS_slim_parquet"),
        help="Directory where Parquet files will be written.",
    )
    parser.add_argument(
        "--compression",
        choices=["snappy", "gzip", "brotli", "zstd", "none"],
        default="snappy",
        help="Parquet compression codec.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Parquet files if they already exist.",
    )
    parser.add_argument(
        "--glob",
        default="*.csv",
        help="Glob pattern for input files (default: *.csv).",
    )
    return parser.parse_args()


def format_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def iter_csv_files(input_dir: Path, pattern: str) -> Iterable[Path]:
    return sorted(path for path in input_dir.glob(pattern) if path.is_file())


def main() -> int:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    compression = None if args.compression == "none" else args.compression

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    csv_files = list(iter_csv_files(input_dir, args.glob))
    if not csv_files:
        raise FileNotFoundError(
            f"No input files matched '{args.glob}' in {input_dir}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    total_csv_bytes = 0
    total_parquet_bytes = 0

    print(f"Input dir:  {input_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Compression: {args.compression}")
    print(f"Files found: {len(csv_files)}\n")

    for csv_path in csv_files:
        parquet_path = output_dir / f"{csv_path.stem}.parquet"

        if parquet_path.exists() and not args.overwrite:
            print(f"SKIP {csv_path.name} -> {parquet_path.name} (already exists)")
            continue

        df = pd.read_csv(csv_path, low_memory=False)
        csv_rows = len(df)
        csv_bytes = csv_path.stat().st_size

        df.to_parquet(parquet_path, engine="pyarrow", compression=compression, index=False)

        # Validation: make sure row counts match after conversion.
        parquet_rows = len(pd.read_parquet(parquet_path, engine="pyarrow"))
        if parquet_rows != csv_rows:
            raise ValueError(
                "Row count mismatch after conversion for "
                f"{csv_path.name}: csv={csv_rows}, parquet={parquet_rows}"
            )

        parquet_bytes = parquet_path.stat().st_size

        total_csv_bytes += csv_bytes
        total_parquet_bytes += parquet_bytes

        ratio = parquet_bytes / csv_bytes if csv_bytes else 0.0
        print(
            f"OK   {csv_path.name} -> {parquet_path.name} | "
            f"{format_mb(csv_bytes)} -> {format_mb(parquet_bytes)} | "
            f"{ratio:.1%}"
        )

    if total_csv_bytes == 0:
        print("\nNo files converted.")
        return 0

    total_ratio = total_parquet_bytes / total_csv_bytes
    print("\nTotals (converted files only):")
    print(f"- CSV total:     {format_mb(total_csv_bytes)}")
    print(f"- Parquet total: {format_mb(total_parquet_bytes)}")
    print(f"- Size ratio:    {total_ratio:.1%}")
    print(f"- Reduction:     {1 - total_ratio:.1%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
