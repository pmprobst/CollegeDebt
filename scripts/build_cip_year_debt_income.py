#!/usr/bin/env python3
"""Build CIP-year debt/income output from IPEDS, BLS OEWS, and CIP-SOC crosswalk."""

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


def parse_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", "", regex=False), errors="coerce")


def build_ipeds_debt(ipeds_dir: Path) -> pd.DataFrame:
    files = sorted(ipeds_dir.glob("FieldOfStudyData*_PP_slim.csv"))
    if not files:
        raise FileNotFoundError(f"No IPEDS field-of-study files found in {ipeds_dir}")

    yearly_frames: list[pd.DataFrame] = []
    for csv_path in files:
        year = parse_ipeds_year(csv_path.name)
        df = pd.read_csv(
            csv_path,
            usecols=["CIPCODE", "CREDDESC", DEBT_FIELD, "EARN_MDN_HI_1YR", "EARN_MDN_HI_2YR"],
            low_memory=False,
        )
        df["CIP_Code"] = normalize_ipeds_cip(df["CIPCODE"])
        df["debt_value"] = parse_numeric(df[DEBT_FIELD])
        df["earn_mdn_hi_1yr"] = parse_numeric(df["EARN_MDN_HI_1YR"])
        df["earn_mdn_hi_2yr"] = parse_numeric(df["EARN_MDN_HI_2YR"])
        df["postgrad_earnings_value"] = df[["earn_mdn_hi_1yr", "earn_mdn_hi_2yr"]].mean(axis=1, skipna=True)
        df["credential_tag"] = df["CREDDESC"].astype("string").str.strip()
        df = df.dropna(subset=["CIP_Code", "debt_value"])
        if df.empty:
            continue

        metric_agg = (
            df.groupby("CIP_Code", as_index=False)["debt_value"]
            .mean()
            .rename(columns={"debt_value": "avg_debt_debt_all_stgp_any_mean"})
        )
        postgrad_agg = (
            df.dropna(subset=["postgrad_earnings_value"])
            .groupby("CIP_Code", as_index=False)["postgrad_earnings_value"]
            .mean()
            .rename(columns={"postgrad_earnings_value": "avg_postgrad_earnings"})
        )
        cred_agg = (
            df.dropna(subset=["credential_tag"])
            .groupby("CIP_Code", as_index=False)["credential_tag"]
            .agg(
                lambda vals: "|".join(
                    sorted({v for v in vals if isinstance(v, str) and v and v != "<NA>"})
                )
            )
            .rename(columns={"credential_tag": "credential_level_tags"})
        )
        agg = metric_agg.merge(postgrad_agg, how="left", on="CIP_Code").merge(
            cred_agg, how="left", on="CIP_Code"
        )
        agg["year"] = year
        yearly_frames.append(agg)

    if not yearly_frames:
        return pd.DataFrame(
            columns=[
                "CIP_Code",
                "year",
                "avg_debt_debt_all_stgp_any_mean",
                "avg_postgrad_earnings",
                "credential_level_tags",
            ]
        )
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
        income_col = INCOME_FIELD
        pct10_col = "A_PCT10" if "A_PCT10" in df.columns else "A_WPCT10"
        pct90_col = "A_PCT90" if "A_PCT90" in df.columns else "A_WPCT90"
        emp_col = "TOT_EMP"

        if (
            group_col is None
            or occ_col not in df.columns
            or income_col not in df.columns
            or pct10_col not in df.columns
            or pct90_col not in df.columns
            or emp_col not in df.columns
        ):
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
        df["income_value"] = parse_numeric(df[income_col])
        df["pct10_value"] = parse_numeric(df[pct10_col])
        df["pct90_value"] = parse_numeric(df[pct90_col])
        df["tot_emp_value"] = parse_numeric(df[emp_col])
        df = df.dropna(subset=["SOC_Code"])
        if df.empty:
            continue

        agg = (
            df.groupby("SOC_Code", as_index=False)
            .agg(
                soc_income_a_mean=("income_value", "mean"),
                soc_income_a_pct10=("pct10_value", "mean"),
                soc_income_a_pct90=("pct90_value", "mean"),
                soc_tot_emp=("tot_emp_value", "mean"),
            )
        )
        agg["year"] = year
        yearly_frames.append(agg)

    if not yearly_frames:
        return pd.DataFrame(
            columns=[
                "SOC_Code",
                "year",
                "soc_income_a_mean",
                "soc_income_a_pct10",
                "soc_income_a_pct90",
                "soc_tot_emp",
            ]
        )
    return pd.concat(yearly_frames, ignore_index=True)


def load_crosswalk(crosswalk_path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        crosswalk_path,
        usecols=["CIP_Code", "CIP2020Title", "SOC_Code"],
        dtype={"CIP_Code": "string", "CIP2020Title": "string", "SOC_Code": "string"},
        low_memory=False,
    )
    df["CIP_Code"] = crosswalk_cip_to_ipeds_key(df["CIP_Code"])
    df["CIP_Desc"] = df["CIP2020Title"].astype("string").str.strip()
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

    crosswalk_base = crosswalk[["CIP_Code", "SOC_Code"]].drop_duplicates()
    cip_desc = (
        crosswalk[["CIP_Code", "CIP_Desc"]]
        .dropna(subset=["CIP_Desc"])
        .drop_duplicates()
        .sort_values(["CIP_Code", "CIP_Desc"])
        .drop_duplicates(subset=["CIP_Code"], keep="first")
    )

    crosswalk_income = crosswalk_base.merge(bls_income, how="inner", on="SOC_Code")
    weighted_bits = crosswalk_income.assign(
        weighted_income_numerator=crosswalk_income["soc_income_a_mean"] * crosswalk_income["soc_tot_emp"]
    )
    cip_income = (
        weighted_bits.groupby(["CIP_Code", "year"], as_index=False).agg(
            avg_income_a_mean_broad_detailed=("soc_income_a_mean", "mean"),
            avg_income_a_pct10_broad_detailed=("soc_income_a_pct10", "mean"),
            avg_income_a_pct90_broad_detailed=("soc_income_a_pct90", "mean"),
            sum_employment_tot_emp=("soc_tot_emp", "sum"),
            weighted_income_a_mean_by_tot_emp=("weighted_income_numerator", "sum"),
        )
    )
    cip_income["weighted_income_a_mean_by_tot_emp"] = cip_income["weighted_income_a_mean_by_tot_emp"] / cip_income[
        "sum_employment_tot_emp"
    ]

    final_df = ipeds_debt.merge(cip_income, how="left", on=["CIP_Code", "year"]).merge(
        cip_desc, how="left", on="CIP_Code"
    )
    final_df = final_df[
        [
            "CIP_Code",
            "CIP_Desc",
            "credential_level_tags",
            "year",
            "avg_debt_debt_all_stgp_any_mean",
            "avg_postgrad_earnings",
            "avg_income_a_mean_broad_detailed",
            "weighted_income_a_mean_by_tot_emp",
            "avg_income_a_pct10_broad_detailed",
            "avg_income_a_pct90_broad_detailed",
            "sum_employment_tot_emp",
        ]
    ]
    final_df = final_df.sort_values(["CIP_Code", "year"]).reset_index(drop=True)

    for col in (
        "avg_debt_debt_all_stgp_any_mean",
        "avg_postgrad_earnings",
        "avg_income_a_mean_broad_detailed",
        "weighted_income_a_mean_by_tot_emp",
        "avg_income_a_pct10_broad_detailed",
        "avg_income_a_pct90_broad_detailed",
    ):
        final_df[col] = parse_numeric(final_df[col]).round(0).astype("Int64")
    final_df["sum_employment_tot_emp"] = parse_numeric(final_df["sum_employment_tot_emp"]).round(0).astype("Int64")

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
