# EDA Tables and Report Usage

Deterministic summary artifacts produced by `python -m src.basic_eda`. Each table is report-ready and reproducible from cached snapshots.

- `kaggle_segment_distribution.csv` — Segment size baselines (Type/Status/GenderCode/Living status) with counts and pct for audience description.
- `kaggle_missingness.csv` — Column-level missingness for data quality notes and preprocessing decisions.
- `kaggle_numeric_robust_summary.csv` — Quantiles/IQR for numeric fields; supports describing distributions and flagging outliers.
- `kaggle_gender_by_status.csv` — Cross-tab to show gender mix by status for demographic context.

- `hillstrom_treatment_distribution.csv` — Treatment/control allocation for the email experiment.
- `hillstrom_visit_by_segment.csv` — Visit rates by treatment for headline uplift directionality.
- `hillstrom_missingness.csv` — Missingness diagnostics on the analysis frame.
- `hillstrom_numeric_robust_summary.csv` — Quantiles/IQR for numeric covariates to describe the sample.
- `hillstrom_outcome_summary_with_ci.csv` — Visit rates with 95% CIs and uplift vs control for stability reporting.
- `hillstrom_balance_smd_vs_control.csv` — Covariate balance (SMD) vs control to justify comparability.

- `criteo_treatment_distribution.csv` — Treatment/control allocation for the ads experiment.
- `criteo_conversion_by_treatment.csv` — Conversion rates by treatment for baseline uplift directionality.
- `criteo_missingness.csv` — Missingness diagnostics on the Criteo analysis frame.
- `criteo_numeric_robust_summary.csv` — Quantiles/IQR for numeric covariates to describe the sample.
- `criteo_outcome_summary_with_ci.csv` — Conversion rates with 95% CIs and uplift vs control for stability reporting.
- `criteo_balance_smd.csv` — Covariate balance (SMD) treatment=1 vs control=0 to check comparability.
