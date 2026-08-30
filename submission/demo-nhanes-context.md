# NHANES 2021-2023 health examination demo

The U.S. National Health and Nutrition Examination Survey public release for
August 2021 – August 2023, converted from the official SAS transport files without
recoding, filtering or imputation. 11,933 participants appear in `demographics.csv`;
the other seven tables are subsets of those participants, linked by `SEQN`.

| table | contents | rows | columns |
| --- | --- | --- | --- |
| `demographics.csv` | age, sex, race/ethnicity, income ratio, education, survey design | 11,933 | 27 |
| `body_measures.csv` | weight, height, BMI, waist and arm circumference | 8,860 | 22 |
| `blood_pressure.csv` | oscillometric blood pressure, three readings each | 7,801 | 12 |
| `glycohemoglobin.csv` | HbA1c, laboratory | 7,199 | 3 |
| `hdl_cholesterol.csv` | direct HDL cholesterol, laboratory | 8,068 | 4 |
| `sleep.csv` | usual sleep and wake times, weekday and weekend, trouble sleeping | 8,501 | 7 |
| `physical_activity.csv` | global physical activity items | 8,153 | 8 |
| `depression_phq9.csv` | nine-item depression screener | 6,337 | 11 |
| `data_dictionary.csv` | the official CDC codebooks, one row per documented code | 326 | 7 |

Total prepared size is 3.9 MiB.

## What the agents are told, and what they are not

The run supplies the nine files above and a sixteen-line `metadata.md`. That file carries
only what the data cannot state about itself: where the release came from, its licence,
that `data_dictionary.csv` is the official codebook for the other tables, what was
changed relative to the official release, and the rule that an external check must be
independent of this release.

It deliberately does **not** tell the agents how to analyse the data. NHANES carries
several traps that decide whether a result means anything:

- each table is one row per `SEQN`, but component eligibility and non-response differ,
  so an inner join silently changes the analytic population;
- blank means not applicable or not asked, and questionnaire items code refusal and
  non-response as out-of-range integers — commonly `7`/`77`/`777` and `9`/`99`/`999`;
- it is a stratified, multistage probability sample with oversampling, so unweighted
  estimates do not describe the U.S. population, and `WTINT2YR`, `WTMEC2YR`, `SDMVSTRA`
  and `SDMVPSU` exist to be used;
- it is one cross-sectional cycle, so nothing in it establishes temporal order.

Every one of those is documented per variable in the codebook that ships beside the
data. Writing them into the metadata as well would hand the agent an analysis plan and
then credit it for following one. The agent gets the codebook and has to read it.

The same reasoning governs the external stage. The metadata names no holdout source. It
states only what independence means — not another NHANES cycle, not a mirror or
derivative, not the same collection campaign published elsewhere — and the external
agent searches for its own corpus and defends its choice, or abstains and says exactly
what blocked it.

Source: Centers for Disease Control and Prevention, National Center for Health
Statistics, "National Health and Nutrition Examination Survey,"
https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?Cycle=2021-2023.
Public domain (U.S. Government work, 17 U.S.C. 105).

The bundle is rebuilt from the live CDC release by
[`scripts/prepare_nhanes_demo.py`](../scripts/prepare_nhanes_demo.py), which records raw
and prepared SHA-256 digests for every file in `manifest.json`.
