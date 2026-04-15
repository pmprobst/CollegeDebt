"""Data preparation and aggregation for the Major Explorer view."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOS_PATH = (
    REPO_ROOT
    / "Data"
    / "IPEDS_College_Scorecard"
    / "FieldOfStudy"
    / "Most-Recent-Cohorts-Field-of-Study_slim.csv"
)

NUMERIC_COLS = [
    "DEBT_ALL_STGP_ANY_MDN",
    "EARN_MDN_HI_1YR",
    "EARN_MDN_HI_2YR",
]

# IPEDS credential levels for Bachelor's, Master's, Doctoral
CREDENTIAL_FILTER_LEVELS = {3, 5, 6}
CREDENTIAL_LABELS = {
    3: "Bachelor's",
    5: "Master's",
    6: "Doctoral",
}


def _cipcode_to_str(code: float | int | str) -> str:
    if pd.isna(code):
        return ""
    try:
        x = float(code)
        if pd.isna(x):
            return ""
        if x == int(x):
            return str(int(x))
        return str(code).strip()
    except (TypeError, ValueError):
        s = str(code).strip()
        return s


def cip_family(code: float | int | str | None) -> str | None:
    """Two-digit CIP family (string, zero-padded) for broad category filter."""
    s = _cipcode_to_str(code)
    if not s:
        return None
    if len(s) <= 4:
        s = s.zfill(4)
    else:
        s = s.zfill(6)
    return s[:2]


def short_credential(creddesc: str) -> str:
    if pd.isna(creddesc) or not str(creddesc).strip():
        return ""
    t = str(creddesc).strip()
    for suffix in (" Degree", " degree"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
    return t


def coerce_numeric(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    s = s.replace(
        {
            "PS": pd.NA,
            "PrivacySuppressed": pd.NA,
            "": pd.NA,
            "nan": pd.NA,
        }
    )
    return pd.to_numeric(s, errors="coerce")


def prepare_fos_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw field-of-study CSV data (shared by most-recent and panel loads)."""
    df = df.copy()
    df["CIPCODE"] = pd.to_numeric(df["CIPCODE"], errors="coerce")
    df = df.dropna(subset=["CIPCODE"])
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = coerce_numeric(df[col])
    df["cip_family"] = df["CIPCODE"].map(cip_family)
    df = df[df["cip_family"].notna()].copy()
    df["cred_short"] = df["CREDDESC"].map(short_credential)
    df = df[df["CREDLEV"].isin(CREDENTIAL_FILTER_LEVELS)].copy()
    return df


def load_and_prepare(csv_path: Path | None = None) -> pd.DataFrame:
    path = csv_path or DEFAULT_FOS_PATH
    df = pd.read_csv(path, low_memory=False)
    return prepare_fos_dataframe(df)


def family_labels(df: pd.DataFrame) -> pd.DataFrame:
    """One row per cip_family with a display label (first seen CIPDESC)."""
    g = (
        df.sort_values(["cip_family", "CIPDESC"])
        .groupby("cip_family", as_index=False)
        .first()
    )
    g["family_label"] = g["cip_family"] + " — " + g["CIPDESC"].fillna("").str.slice(0, 60)
    return g[["cip_family", "family_label"]]


def aggregate_by_program(
    df: pd.DataFrame,
    cip_families: list[str] | None = None,
    cred_levels: list[int] | None = None,
) -> pd.DataFrame:
    """Median debt and earnings per (CIPCODE, credential) across institutions."""
    d = df.copy()
    if cip_families is not None:
        d = d[d["cip_family"].isin(cip_families)]
    if cred_levels is not None:
        d = d[d["CREDLEV"].isin(cred_levels)]
    if d.empty:
        return pd.DataFrame(
            columns=[
                "CIPCODE",
                "CIPDESC",
                "CREDLEV",
                "CREDDESC",
                "cred_short",
                "cip_family",
                "debt_mdn",
                "earn_1yr",
                "earn_2yr",
                "n_inst",
            ]
        )

    grp = d.groupby(["CIPCODE", "CREDLEV"], as_index=False)
    agg = grp.agg(
        CIPDESC=("CIPDESC", "first"),
        CREDDESC=("CREDDESC", "first"),
        cred_short=("cred_short", "first"),
        cip_family=("cip_family", "first"),
        debt_mdn=("DEBT_ALL_STGP_ANY_MDN", "median"),
        earn_1yr=("EARN_MDN_HI_1YR", "median"),
        earn_2yr=("EARN_MDN_HI_2YR", "median"),
        n_inst=("UNITID", "nunique"),
    )
    return agg
