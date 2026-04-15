"""Load field-of-study panel CSVs and compute cohort-level aggregates for Tab 2."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from major_explorer import CREDENTIAL_FILTER_LEVELS, prepare_fos_dataframe

REPO_ROOT = Path(__file__).resolve().parents[1]
FIELD_OF_STUDY_DIR = (
    REPO_ROOT / "Data" / "IPEDS_College_Scorecard" / "FieldOfStudy"
)

# Fixed order: award-year pooled cohorts (College Scorecard panel releases)
PANEL_SPECS: list[tuple[str, int, str]] = [
    ("FieldOfStudyData1415_1516_PP_slim.csv", 0, "2014–16"),
    ("FieldOfStudyData1516_1617_PP_slim.csv", 1, "2015–17"),
    ("FieldOfStudyData1617_1718_PP_slim.csv", 2, "2016–18"),
    ("FieldOfStudyData1718_1819_PP_slim.csv", 3, "2017–19"),
    ("FieldOfStudyData1819_1920_PP_slim.csv", 4, "2018–20"),
    ("FieldOfStudyData1920_2021_PP_slim.csv", 5, "2019–21"),
    ("FieldOfStudyData2021_2122_PP_slim.csv", 6, "2020–22"),
    ("FieldOfStudyData2122_2223_PP_slim.csv", 7, "2021–23"),
]


def load_panels_long() -> pd.DataFrame:
    """Concatenate all panel slim CSVs with cohort_sort and cohort_label."""
    frames: list[pd.DataFrame] = []
    for fname, sort_key, label in PANEL_SPECS:
        path = FIELD_OF_STUDY_DIR / fname
        if not path.is_file():
            continue
        raw = pd.read_csv(path, low_memory=False)
        df = prepare_fos_dataframe(raw)
        df["cohort_sort"] = sort_key
        df["cohort_label"] = label
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def aggregate_by_program_cohort(
    df: pd.DataFrame,
    cipcodes: list[float | int],
    cred_levels: list[int],
) -> pd.DataFrame:
    """Median debt and earnings per cohort × program (across institutions)."""
    if df.empty or not cipcodes or not cred_levels:
        return pd.DataFrame(
            columns=[
                "cohort_sort",
                "cohort_label",
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
    codes = [float(c) for c in cipcodes]
    d = df[
        (df["CIPCODE"].isin(codes)) & (df["CREDLEV"].isin(cred_levels))
    ].copy()
    if d.empty:
        return pd.DataFrame(
            columns=[
                "cohort_sort",
                "cohort_label",
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

    grp = d.groupby(
        ["cohort_sort", "cohort_label", "CIPCODE", "CREDLEV"],
        as_index=False,
    )
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
    return agg.sort_values(["CIPCODE", "cohort_sort"])


def family_median_ratio_by_cohort(
    df: pd.DataFrame,
    cred_level: int,
) -> pd.DataFrame:
    """
    For each cohort and 2-digit CIP family: median of program-level
    (median debt / median 2yr earnings) among programs with valid ratio.
    """
    if df.empty or cred_level not in CREDENTIAL_FILTER_LEVELS:
        return pd.DataFrame(columns=["cohort_sort", "cohort_label", "cip_family", "ratio_median"])

    d = df[df["CREDLEV"] == cred_level].copy()
    grp = d.groupby(
        ["cohort_sort", "cohort_label", "CIPCODE", "CREDLEV", "cip_family"],
        as_index=False,
    ).agg(
        debt_mdn=("DEBT_ALL_STGP_ANY_MDN", "median"),
        earn_2yr=("EARN_MDN_HI_2YR", "median"),
    )
    grp = grp.dropna(subset=["debt_mdn", "earn_2yr"])
    grp = grp[grp["earn_2yr"] > 0]
    grp["ratio"] = grp["debt_mdn"] / grp["earn_2yr"]

    fam = (
        grp.groupby(["cohort_sort", "cohort_label", "cip_family"], as_index=False)[
            "ratio"
        ]
        .median()
        .rename(columns={"ratio": "ratio_median"})
    )
    return fam.sort_values(["cip_family", "cohort_sort"])


def family_ratio_delta(
    df: pd.DataFrame,
    cred_level: int,
) -> pd.DataFrame:
    """
    Change in family median debt-to-earnings ratio from earliest to latest cohort.
    Positive delta = higher ratio in latest cohort (worse ROI). Requires both endpoints.
    """
    fam = family_median_ratio_by_cohort(df, cred_level)
    if fam.empty:
        return pd.DataFrame(
            columns=["cip_family", "family_title", "ratio_first", "ratio_last", "delta_ratio"]
        )

    sort_min = fam["cohort_sort"].min()
    sort_max = fam["cohort_sort"].max()
    first = fam[fam["cohort_sort"] == sort_min][["cip_family", "ratio_median"]].rename(
        columns={"ratio_median": "ratio_first"}
    )
    last = fam[fam["cohort_sort"] == sort_max][["cip_family", "ratio_median"]].rename(
        columns={"ratio_median": "ratio_last"}
    )
    merged = first.merge(last, on="cip_family", how="inner")
    merged = merged.dropna(subset=["ratio_first", "ratio_last"])
    merged["delta_ratio"] = merged["ratio_last"] - merged["ratio_first"]

    # Title: first CIPDESC seen for this family in the long df (latest cohort)
    latest = df[df["cohort_sort"] == sort_max].sort_values("CIPDESC")
    titles = (
        latest.groupby("cip_family", as_index=False)["CIPDESC"]
        .first()
        .rename(columns={"CIPDESC": "family_title"})
    )
    out = merged.merge(titles, on="cip_family", how="left")
    out["family_title"] = out["cip_family"] + " — " + out["family_title"].fillna("").str.slice(0, 50)
    return out.sort_values("delta_ratio", ascending=False)
