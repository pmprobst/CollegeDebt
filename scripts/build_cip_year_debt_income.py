#!/usr/bin/env python3
"""Build CIP-year debt/income output from IPEDS, BLS OEWS, and CIP-SOC crosswalk.

The output contains one row per CIP code and year with:
- avg debt from IPEDS DEBT_ALL_STGP_ANY_MEAN
- avg income from BLS A_MEAN across mapped SOC codes (broad + detailed)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


DEBT_FIELD = "DEBT_ALL_STGP_ANY_MEAN"
INCOME_FIELD = "A_MEAN"
VALID_O_GROUPS = {"broad", "detailed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Join and aggregate CIP-year debt and income metrics."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("Data"),
        help="Root data directory (default: Data).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Data/cip_year_debt_income.csv"),
        help="Output CSV path (default: Data/cip_year_debt_income.csv).",
    )
    return parser.parse_args()


def normalize_ipeds_cip(series: pd.Series) -> pd.Series:
    """Normalize IPEDS CIPCODE to 4-digit key used in field-of-study files."""
    as_num = pd.to_numeric(series, errors="coerce")
    as_int = as_num.round().astype("Int64")
    normalized = as_int.map(lambda v: f"{v:04d}" if pd.notna(v) else pd.NA)
    return normalized.astype("string")


def crosswalk_cip_to_ipeds_key(series: pd.Series) -> pd.Series:
    """Map crosswalk 6-digit CIP (e.g., 11.0101) to IPEDS 4-digit CIP key (1101)."""
    compact = series.astype("string").str.replace(".", "", regex=False).str.strip()
    return compact.str.slice(0, 4).astype("string")


def parse_ipeds_year(file_name: str) -> int:
    """Extract end year from filename pattern like FieldOfStudyData1415_1516_PP_slim.csv."""
    match = re.search(r"FieldOfStudyData(\d{2})\d{2}_(\d{2})(\d{2})_PP_slim\.csv$", file_name)
    if not match:
        raise ValueError(f"Unrecognized IPEDS filename: {file_name}")
    century = 2000
    end_year = century + int(match.group(3))
    return end_year


def parse_bls_year(file_name: str) -> int:
    match = re.search(r"national_oews_may(\d{4})\.csv$", file_name)
    if not match:
        raise ValueError(f"Unrecognized BLS filename: {file_name}")
    return int(match.group(1))


def build_ipeds_debt(ipeds_dir: Path) -> pd.DataFrame:
    files = sorted(ipeds_dir.glob("FieldOfStudyData*_PP_slim.csv"))
    if not files:
        raise FileNotFoundError(f"No IPEDS field-of-study files found in {ipeds_dir}")

    yearly_frames: list[pd.DataFrame] = []
    for csv_path in files:
        year = parse_ipeds_year(csv_path.name)
        df = pd.read_csv(
            csv_path,
            usecols=["CIPCODE", DEBT_FIELD],
            low_memory=False,
        )
        df["CIP_Code"] = normalize_ipeds_cip(df["CIPCODE"])
        df["debt_value"] = pd.to_numeric(df[DEBT_FIELD], errors="coerce")
        df = df.dropna(subset=["CIP_Code", "debt_value"])
        if df.empty:
            continue

        agg = (
            df.groupby("CIP_Code", as_index=False)["debt_value"]
            .mean()
            .rename(columns={"debt_value": "avg_debt_debt_all_stgp_any_mean"})
        )
        agg["year"] = year
        yearly_frames.append(agg)

    if not yearly_frames:
        return pd.DataFrame(columns=["CIP_Code", "year", "avg_debt_debt_all_stgp_any_mean"])
    return pd.concat(yearly_frames, ignore_index=True)


def build_bls_income(bls_dir: Path) -> pd.DataFrame:
    files = sorted(bls_dir.glob("national_oews_may*.csv"))
    if not files:
        raise FileNotFoundError(f"No BLS OEWS files found in {bls_dir}")

    yearly_frames: list[pd.DataFrame] = []
    for csv_path in files:
        year = parse_bls_year(csv_path.name)
        raw = pd.read_csv(csv_path, low_memory=False)
        normalized_cols = {col: col.upper() for col in raw.columns}
        df = raw.rename(columns=normalized_cols)

        # Older OEWS vintages use GROUP/occ_code/a_mean with lowercase naming
        # and often encode detailed rows as blank GROUP.
        group_col = None
        for candidate in ("O_GROUP", "OCC_GROUP", "GROUP"):
            if candidate in df.columns:
                group_col = candidate
                break
        occ_col = "OCC_CODE"
        income_col = INCOME_FIELD if INCOME_FIELD in df.columns else INCOME_FIELD.lower().upper()

        if group_col is None or occ_col not in df.columns or income_col not in df.columns:
            raise ValueError(f"Missing expected columns in {csv_path.name}")

        group_norm = (
            df[group_col]
            .astype("string")
            .str.strip()
            .str.lower()
            .fillna("")
            .replace({"": "detailed"})
        )
        df = df[group_norm.isin(VALID_O_GROUPS)].copy()
        df["SOC_Code"] = df[occ_col].astype("string").str.strip()
        df["income_value"] = pd.to_numeric(
            df[income_col].astype("string").str.replace(",", "", regex=False),
            errors="coerce",
        )
        df = df.dropna(subset=["SOC_Code", "income_value"])
        if df.empty:
            continue

        agg = (
            df.groupby("SOC_Code", as_index=False)["income_value"]
            .mean()
            .rename(columns={"income_value": "soc_income_a_mean"})
        )
        agg["year"] = year
        yearly_frames.append(agg)

    if not yearly_frames:
        return pd.DataFrame(columns=["SOC_Code", "year", "soc_income_a_mean"])
    return pd.concat(yearly_frames, ignore_index=True)


def load_crosswalk(crosswalk_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        crosswalk_path,
        usecols=["CIP_Code", "SOC_Code"],
        dtype={"CIP_Code": "string", "SOC_Code": "string"},
        low_memory=False,
    )
    df["CIP_Code"] = crosswalk_cip_to_ipeds_key(df["CIP_Code"])
    df["SOC_Code"] = df["SOC_Code"].astype("string").str.strip()
    df = df.dropna(subset=["CIP_Code", "SOC_Code"]).drop_duplicates()
    return df


def main() -> int:
    args = parse_args()
    data_dir: Path = args.data_dir

    crosswalk_path = data_dir / "CIPSOCcrosswalk.csv"
    bls_dir = data_dir / "BLS_OEWS"
    ipeds_dir = data_dir / "IPEDS_College_Scorecard" / "FieldOfStudy"

    crosswalk = load_crosswalk(crosswalk_path)
    ipeds_debt = build_ipeds_debt(ipeds_dir)
    bls_income = build_bls_income(bls_dir)

    cip_income = (
        crosswalk.merge(bls_income, how="inner", on="SOC_Code")
        .groupby(["CIP_Code", "year"], as_index=False)["soc_income_a_mean"]
        .mean()
        .rename(columns={"soc_income_a_mean": "avg_income_a_mean_broad_detailed"})
    )

    final_df = ipeds_debt.merge(cip_income, how="left", on=["CIP_Code", "year"])
    final_df = final_df.sort_values(["CIP_Code", "year"]).reset_index(drop=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(args.output, index=False)

    mapped_cips = set(crosswalk["CIP_Code"])
    debt_cips = set(ipeds_debt["CIP_Code"])
    cips_without_crosswalk = len(debt_cips - mapped_cips)
    debt_rows = len(final_df)
    debt_without_income = int(final_df["avg_income_a_mean_broad_detailed"].isna().sum())

    print(f"Wrote: {args.output}")
    print(f"Rows: {debt_rows:,}")
    if debt_rows:
        print(f"Debt rows without income: {debt_without_income:,} ({debt_without_income / debt_rows:.2%})")
    print(f"Distinct debt CIPs without crosswalk mapping: {cips_without_crosswalk:,}")
    print(
        f"Year coverage (debt): {int(ipeds_debt['year'].min())}-{int(ipeds_debt['year'].max())}, "
        f"(income): {int(bls_income['year'].min())}-{int(bls_income['year'].max())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
