# Research log — STAT 281 (College Dept Data Vis)

Brief notes on data work, decisions, and next steps. Add a new dated section each day you work on the project.

---

## 2026-04-01 (Wednesday)

- Downloaded, parsed, and clean edFederal Reserve data from the New York Fed [Household Debt and Credit Report](https://www.newyorkfed.org/microeconomics/hhdc) (Center for Microeconomic Data).
- Downloaded Occupational Employment and Wage Statistics (OEWS) Tables from the US Bureau of Labor Statistics
- Consolidated field descriptions from OEWS tables into one txt document

## 2026-04-02

- converted 24 years of OEWS files from .xls/.xlsx to csv and standerdized naming.
- downloaded CIP/SOC crosswalk to join education and industry data

## 2026-04-06 (Monday)

- Produced reduced-column College Scorecard MERGED extracts (`MERGED*_PP_slim.csv`, 213 columns each) under `Data/processed/MERGED_slim/` for all release years in `College_Scorecard_Raw_Data_03232026`. (Automation scripts and config used for that step were removed afterward.)

## 2026-04-07 (Tuesday)

- Slimmed **most recent** College Scorecard extracts to match the same column set as the FoS slim files: `Most-Recent-Cohorts-Field-of-Study.csv` → `Data/processed/FOS_slim/Most-Recent-Cohorts-Field-of-Study_slim.csv` (32 columns, aligned with `FieldOfStudyData*_PP_slim.csv` headers).
- Slimmed `Most-Recent-Cohorts-Institution.csv` using a separate markdown drop list → `Data/processed/Institution_slim/Most-Recent-Cohorts-Institution_slim.csv` (institution columns overlapping the FoS keep set).
- Added helper markdown specs under `Data/College_Scorecard_Raw_Data_03232026/` (`MostRecentInstitution_columns.md`, `MostRecentInstitution_drop.md`) and extended `scripts/slim_fos_from_md.py` (drop-spec and keep-header modes). **Removed those scripts and spec files after** so only the processed slim CSVs remain in `Data/processed/`.

---

## Template (copy below the line)

```markdown
## YYYY-MM-DD (Weekday)

- Bullet what you did.

**Notes / next time**

-
```

