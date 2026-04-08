# Data directory overview

This folder holds CSV (and one TXT) datasets used for college, labor-market, and household-debt analysis. Below is a concise map of **what** each area contains and **how** the pieces relate.

---

## 1. CIP–SOC crosswalk (`CIPSOCcrosswalk.csv`)

**Purpose:** Link **Classification of Instructional Programs (CIP)** codes (fields of study) to **Standard Occupational Classification (SOC)** codes (occupations).

**Columns:** `CIP_Code`, `CIP2020Title`, `SOC_Code`, `SOC2018Title` — one row per CIP–SOC pair (many-to-many mapping).

**Use:** Join college field-of-study or program data to occupational or wage series that use SOC codes.

---

## 2. IPEDS / College Scorecard (`IPEDS_College_Scorecard/`)

Slimmed extracts from the U.S. Department of Education College Scorecard; filenames include `_slim` where columns were reduced for analysis.

### 2a. Institution-level (`Institution/`)

- **`Most-Recent-Cohorts-Institution_slim.csv`** — One row per institution (IPEDS `UNITID`). Core identifiers include `UNITID`, `OPEID6`, `INSTNM`, `MAIN` (main campus flag), `CONTROL` (public/private control).

### 2b. Field-of-study (`FieldOfStudy/`)

Two related shapes:

| File pattern | Role |
|--------------|------|
| **`Most-Recent-Cohorts-Field-of-Study_slim.csv`** | “Most recent” field-of-study snapshot: institution × CIP × credential level, with debt and earnings-related columns. |
| **`FieldOfStudyData*_PP_slim.csv`** (e.g. `1415_1516` through `2122_2223`) | **Panel slices by award-year range** — same logical schema as other field-of-study slim files (identifiers, `CIPCODE` / `CIPDESC`, `CREDLEV` / `CREDDESC`, completions-style counts, debt metrics such as `DEBT_ALL_*`, earnings metrics such as `EARN_*`). `PS` in cells typically means suppressed or not disclosed in the source. |

Together these support institution-level summaries and program-level debt/earnings views over time.

---

## 3. BLS Occupational Employment and Wage Statistics (`BLS_OEWS/`)

**Purpose:** **National** OEWS extracts by occupation (Bureau of Labor Statistics), for linking SOC-based outcomes to employment and wage levels.

**Data files:** `national_oews_mayYYYY.csv` — one file per May survey year from **2000 through 2024** (annual national cross-industry occupation estimates).

**Typical columns** (see any recent year for the full set): geography (`AREA`, `AREA_TITLE`, …), industry cross-industry summary (`NAICS`, `NAICS_TITLE`), occupation (`OCC_CODE`, `OCC_TITLE`, grouping fields), employment (`TOT_EMP`, …), and wage percentiles/means (`H_MEAN`, `A_MEAN`, `H_MEDIAN`, …, `ANNUAL` / `HOURLY` flags).

**Documentation:** `oes_field_descriptions_consolidated.txt` — consolidated field definitions and year-to-year notes (focused on 2003–2017 in the header; still useful for interpreting codes and columns across releases).

---

## 4. Federal Reserve household credit (`FederalReserve/`)

Quarterly **U.S.** time series (`year`, `quarter`), mostly with columns by **loan or debt category** (mortgage, HELOC/revolving home equity, auto, credit card, student loan, other, and often a total).

| File | Content (theme) |
|------|-------------------|
| `debt_balance.csv` | Outstanding **balances** by category (and total). |
| `percent_90_plus_days_deliquent.csv` | Share **90+ days delinquent** by category (note: filename uses “deliquent”). |
| `new_delinquent_balances.csv` | **New** delinquency flows (by category). |
| `new_seriously_delinquent_balances.csv` | **New serious** delinquency (by category). |
| `transition_into_serious_delinquency_by_age.csv` | Transition into serious delinquency **by age band** (`18-29`, `30-39`, …, `all`). |

These series align with common **Federal Reserve Bank of New York** / Consumer Credit Panel style aggregates for macro and student-loan context.

---

## Quick reference: top-level layout

```
Data/
├── CIPSOCcrosswalk.csv
├── IPEDS_College_Scorecard/
│   ├── Institution/
│   └── FieldOfStudy/
├── BLS_OEWS/
└── FederalReserve/
```

For column-level detail, open the CSV header row or `oes_field_descriptions_consolidated.txt` for OEWS.
