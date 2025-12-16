# Digital Marketing Data Loaders

Centralised dataset access for the Digital Marketing project. Provides reusable helpers to load:
- Kaggle customer profile Excel (features only, descriptive profiling).
- Hillstrom (MineThatData) email uplift experiment.
- Criteo uplift prediction dataset.

## Structure
- `src/data_loading.py` — load helpers and CLI entrypoint.
- `Data/` — place raw files here (e.g., `Email Marketing Analysis.xlsx`). Processed exports are written to `Data/Processed/`.

## Quickstart
1) Install deps (Python 3.10+):
```bash
pip install -r requirements.txt
```
2) Run loaders and write processed CSVs:
```bash
python -m src.data_loading
```
This will:
- Read `Data/Email Marketing Analysis.xlsx` sheet `TBL_CustomerProfileData`.
- Download Hillstrom and Criteo datasets via `scikit-uplift`.
- Save CSVs under `Data/Processed/` and print shapes/basic stats.

## Using in code
```python
from src.data_loading import load_kaggle_customer_profile, load_hillstrom, load_criteo

kaggle_df = load_kaggle_customer_profile()
X_hill, y_hill, t_hill = load_hillstrom(target_col="visit")
X_cri, y_cri, t_cri = load_criteo(target_col="conversion", percent10=True)
```

## Notes
- Kaggle sheet contains features only (no treatment/outcome) for profiling.
- Hillstrom targets: `visit`, `conversion`, or `spend`; treatment_raw keeps original email segments.
- Criteo is large; `percent10=True` keeps a 10% sample for speed.
