# Digital Marketing Data Loaders

Centralised dataset access for the Digital Marketing project. Provides reusable helpers to load:
- Kaggle customer profile Excel (features only, descriptive profiling).
- Hillstrom (MineThatData) email uplift experiment.
- Criteo uplift prediction dataset.


## Current Progress (Phase 1)

Implemented and reproducible:

- **Step 1 - Data loading + standardization**
  - All datasets are loaded through `src.data_loading` and standardized into `(X, y, t)` for uplift work (where applicable).
  - A cached snapshot is saved to `Data/Processed/` for fast iteration and reporting.

- **Step 2 - Deterministic uplift-oriented EDA (no plots, no models)**
  - Implemented in `src/basic_eda.py`
  - Produces clean console summaries + small report-ready CSV tables in `Data/Processed/`
  - Includes robustness checks: missingness tables, robust numeric summaries (quantiles/IQR), outcome rate CIs, and covariate balance via SMD.


## Repository Structure (key parts)

- `src/data_loading.py`  
  Dataset loaders and standardization helpers.

- `src/basic_eda.py`  
  Deterministic, reusable EDA module for Kaggle (customer base), Hillstrom (email experiment), and Criteo (ads experiment).

- `Data/Processed/`  
  Auto-generated outputs (snapshots + summary tables). Safe to regenerate.


## Quickstart

### 1) Install deps (Python 3.10+)
```bash
pip install -r requirements.txt
```

### 2) Load datasets and write processed snapshots
```bash
python -m src.data_loading
```
Writes:
- `Data/Processed/kaggle_customer_profile.csv`
- `Data/Processed/hillstrom_visit.csv`
- `Data/Processed/criteo_conversion_10pct.csv`

### 3) Run deterministic EDA and generate report tables
```bash
python -m src.basic_eda
```
Writes the following (all into `Data/Processed/`):

**Kaggle (customer base description)**
- `kaggle_segment_distribution.csv` (Type/Status/GenderCode/Living status counts + pct)
- `kaggle_missingness.csv`
- `kaggle_numeric_robust_summary.csv`
- `kaggle_gender_by_status.csv`

**Hillstrom (email experiment; visit outcome)**
- `hillstrom_treatment_distribution.csv`
- `hillstrom_visit_by_segment.csv`
- `hillstrom_missingness.csv`
- `hillstrom_numeric_robust_summary.csv`
- `hillstrom_outcome_summary_with_ci.csv` (rates + 95% CI + uplift vs control)
- `hillstrom_balance_smd_vs_control.csv` (covariate balance vs "No E-Mail")

**Criteo (ads experiment; conversion outcome, 10% sample)**
- `criteo_treatment_distribution.csv`
- `criteo_conversion_by_treatment.csv`
- `criteo_missingness.csv`
- `criteo_numeric_robust_summary.csv`
- `criteo_outcome_summary_with_ci.csv` (rates + 95% CI + uplift vs control)
- `criteo_balance_smd.csv` (covariate balance: treatment=1 vs control=0)


## What the EDA is proving (and why it matters)

This project is about incrementality, not response prediction.

- Hillstrom and Criteo provide treatment/control structure needed for uplift.
- The EDA tables are built to drop directly into the thesis/report:
  - Treatment distributions
  - Baseline outcome rates
  - Raw uplift vs control
  - Confidence intervals (stability)
  - Balance checks (comparability)


## Known Data Quality Issues (Kaggle)

- Kaggle is used for customer base description, not uplift estimation.
- Status label inconsistency (e.g., "InActive" vs "Inactive"), resolved for reporting via normalization.
- Implausible age outliers (e.g., ages < 18 and > 100 exist). Age is treated as noisy/descriptive only unless cleaned later.


## Experimental Sanity Checks (Hillstrom + Criteo)

To avoid telling causal stories from messy data, EDA includes:
- Outcome rate + 95% CI per treatment (`*_outcome_summary_with_ci.csv`)
- Covariate balance via SMD (`*_balance_smd*.csv`)
- Rule of thumb: max |SMD| < 0.10 indicates good balance.
- Latest run shows strong balance:
  - Hillstrom: max |SMD| ~ 0.009
  - Criteo: max |SMD| ~ 0.047


## Next steps

- Uplift modeling (two-model, meta-learners, or tree-based uplift).
- Evaluation with Qini/uplift curves and policy value estimates.
