from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union, cast

import pandas as pd
from pandas import DataFrame, Series

from sklift.datasets import fetch_hillstrom, fetch_criteo


XType = DataFrame
YType = Series
TType = Series

# Default data directory (adjust if your layout is different)
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "Data"


def load_kaggle_customer_profile(
    data_dir: Union[Path, str] = DEFAULT_DATA_DIR,
    filename: str = "Email Marketing Analysis.xlsx",
    sheet_name: str = "TBL_CustomerProfileData",
) -> DataFrame:
    """
    Load the local Kaggle-style customer profile data.

    This table contains ONLY customer features (X):
        - customer_id
        - demographics (gender, marital status, living status)
        - geography (city, state, postal code)
        - lifecycle (birth date, enrolment date)

    There is NO treatment flag and NO outcome column here, so
    it is used for descriptive profiling, not uplift modelling.

    Returns
    -------
    DataFrame
        Customer-level feature table with a few engineered columns.
    """
    root = Path(__file__).resolve().parents[1]
    processed = root / "Data" / "Processed" / "kaggle_customer_profile.csv"
    processed.parent.mkdir(parents=True, exist_ok=True)

    if processed.exists():
        parse_cols = [c for c in ["BirthDate", "Enrolled on", "Enrolled on "] if c in pd.read_csv(processed, nrows=0).columns]
        df = pd.read_csv(
            processed,
            parse_dates=parse_cols,
            keep_default_na=True,
        )
        for c in ["age_years", "enrol_year"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
        return df

    data_dir = Path(data_dir)
    path = data_dir / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find Kaggle Excel at: {path}. "
            "If this is your first run, execute `python -m src.data_loading` once to build the snapshot."
        )

    df = pd.read_excel(path, sheet_name=sheet_name)

    # Tidy column names
    if "Column1" in df.columns:
        df = df.rename(columns={"Column1": "customer_id"})

    # Parse dates if present
    if "BirthDate" in df.columns:
        df["BirthDate"] = pd.to_datetime(df["BirthDate"], errors="coerce")

    enrol_col = "Enrolled on "
    if enrol_col in df.columns:
        df[enrol_col] = pd.to_datetime(df[enrol_col], errors="coerce")

    today = pd.Timestamp("today").normalize()

    # Vectorised engineered features: age_years and enrol_year
    if "BirthDate" in df.columns:
        # Ensure BirthDate is datetime
        birth = pd.to_datetime(df["BirthDate"], errors="coerce")
        # today - birth -> TimedeltaIndex; cast to days explicitly
        age_days_float = (today - birth) / pd.Timedelta(days=1)
        age_days = pd.to_numeric(age_days_float, errors="coerce").floordiv(1).astype("Int64")
        df["age_years"] = age_days // 365

    if enrol_col in df.columns:
        enrol = pd.to_datetime(df[enrol_col], errors="coerce")
        # Use strftime instead of .dt.year so Pylance doesn't complain
        df["enrol_year"] = enrol.dt.strftime("%Y").astype("Int64")

    # Save snapshot for deterministic reuse
    try:
        df.to_csv(processed, index=False)
    except Exception:
        # Silent fallback; downstream will still return df
        pass

    return df


def load_hillstrom(target_col: str = "visit") -> Tuple[XType, YType, TType]:
    """
    Load the Hillstrom email marketing uplift dataset.

    Parameters
    ----------
    target_col : {'visit', 'conversion', 'spend'}
        Outcome to model.

    Returns
    -------
    X : DataFrame
        Customer features (RFM, channel, demographics, etc.).
    y : Series
        Outcome Series (chosen target_col).
    t : Series
        Treatment assignment (email segment / control).
    """
    X, y_raw, t_raw = fetch_hillstrom(
        target_col=target_col,
        return_X_y_t=True,
    )

    # Force types for the type checker; at runtime these are already Series.
    y = cast(Series, y_raw)
    y.name = target_col

    t = cast(Series, t_raw)
    if t.name is None:
        t.name = "segment"

    return X, y, t


def load_criteo(
    target_col: str = "conversion",
    treatment_col: str = "treatment",
    percent10: bool = True,
) -> Tuple[XType, YType, TType]:
    """
    Load the Criteo uplift prediction dataset.

    Parameters
    ----------
    target_col : {'conversion', 'visit'}
        Outcome to model.
    treatment_col : str
        Name of the treatment column in the returned Series.
    percent10 : bool, default True
        If True, load the 10% sample to keep experiments lightweight.

    Returns
    -------
    X : DataFrame
        Feature matrix (anonymised user/context features).
    y : Series
        Outcome (chosen target_col).
    t : Series
        Binary treatment indicator.
    """
    processed_dir = _ensure_processed_dir()
    cache_path = processed_dir / "criteo_conversion_10pct.csv"

    cache_ok = False
    if percent10 and cache_path.exists():
        cached = pd.read_csv(cache_path)
        legacy_target = f"y_{target_col}"
        if target_col not in cached.columns and legacy_target in cached.columns:
            cached = cached.rename(columns={legacy_target: target_col})
            cached.to_csv(cache_path, index=False)
        if target_col in cached.columns and treatment_col in cached.columns:
            cache_ok = True
            X_cached = cached.drop(columns=[target_col, treatment_col])
            y_cached = cast(Series, cached[target_col])
            y_cached.name = target_col
            t_cached = cast(Series, cached[treatment_col])
            if t_cached.name is None:
                t_cached.name = treatment_col
            print(f"Using cached Criteo 10% sample at {cache_path}")
            return X_cached, y_cached, t_cached
        else:
            print(
                f"Cached file {cache_path} missing required columns; regenerating deterministic 10% sample."
            )

    data_home = DEFAULT_DATA_DIR / "External"
    data_home.mkdir(parents=True, exist_ok=True)

    # Fetch full dataset, then create a deterministic 10% slice by sorted index
    X_full, y_raw, t_raw = fetch_criteo(
        target_col=target_col,
        treatment_col=treatment_col,
        return_X_y_t=True,
        percent10=False,
        data_home=data_home.as_posix(),
    )

    y_full = cast(Series, y_raw)
    y_full.name = target_col

    t_full = cast(Series, t_raw)
    if t_full.name is None:
        t_full.name = treatment_col

    if percent10:
        combined = X_full.copy()
        combined[target_col] = y_full
        combined[treatment_col] = t_full
        n_rows = len(combined)
        n_take = int(n_rows * 0.10)
        n_take = max(1, n_take)
        deterministic_slice = combined.sort_index().iloc[:n_take]
        deterministic_slice.to_csv(cache_path, index=False)
        print(f"Created deterministic Criteo 10% sample at {cache_path}")
        X_out = deterministic_slice.drop(columns=[target_col, treatment_col])
        y_out = cast(Series, deterministic_slice[target_col])
        y_out.name = target_col
        t_out = cast(Series, deterministic_slice[treatment_col])
        if t_out.name is None:
            t_out.name = treatment_col
        return X_out, y_out, t_out

    return X_full, y_full, t_full


def _ensure_processed_dir(base: Union[str, Path] = DEFAULT_DATA_DIR) -> Path:
    """
    Ensure that a 'Processed' subdirectory exists under the given base data dir.
    Return the Path to that folder.
    """
    base_path = Path(base)
    processed = base_path / "Processed"
    processed.mkdir(parents=True, exist_ok=True)
    return processed


if __name__ == "__main__":
    # Lightweight sanity check & CSV export
    processed_dir = _ensure_processed_dir()

    print("=== Kaggle customer profile ===")
    try:
        kaggle_df = load_kaggle_customer_profile()
        print("Shape:", kaggle_df.shape)
        kaggle_path = processed_dir / "kaggle_customer_profile.csv"
        kaggle_df.to_csv(kaggle_path, index=False)
        print("Saved:", kaggle_path)
    except Exception as exc:  # noqa: BLE001
        print("Kaggle load FAILED:", exc)

    print("\n=== Hillstrom (visit) ===")
    try:
        X_h, y_h, t_h = load_hillstrom(target_col="visit")
        print("X shape:", X_h.shape)
        print("y mean:", float(y_h.mean()))
        print("treatment counts:\n", t_h.value_counts())
        hill_path = processed_dir / "hillstrom_visit.csv"
        df_h = X_h.copy()
        df_h["y_visit"] = y_h
        df_h["treatment_raw"] = t_h
        df_h.to_csv(hill_path, index=False)
        print("Saved:", hill_path)
    except Exception as exc:  # noqa: BLE001
        print("Hillstrom load FAILED:", exc)

    print("\n=== Criteo (conversion, 10%) ===")
    try:
        X_c, y_c, t_c = load_criteo(target_col="conversion", percent10=True)
        print("X shape:", X_c.shape)
        print("y mean:", float(y_c.mean()))
        print("treatment counts:\n", t_c.value_counts())
        cri_path = processed_dir / "criteo_conversion_10pct.csv"
        df_c = X_c.copy()
        df_c["y_conversion"] = y_c
        df_c["treatment"] = t_c
        df_c.to_csv(cri_path, index=False)
        print("Saved:", cri_path)
    except Exception as exc:  # noqa: BLE001
        print("Criteo load FAILED:", exc)
