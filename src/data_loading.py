from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple, Union, cast

import numpy as np
import pandas as pd
from pandas import DataFrame, Series

from sklift.datasets import fetch_hillstrom, fetch_criteo
from src.paths import data_processed_dir


XType = DataFrame
YType = Series
TType = Series

# Default data directory (adjust if your layout is different)
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "Data"

# Constants for deterministic sampling
CRITEO_SAMPLE_SEED = 42
CRITEO_SAMPLE_METHOD = "hash"  # Options: "hash" or "seeded_permutation"


def snapshot_hash_df(df: DataFrame) -> str:
    """
    Compute SHA256 hash of a DataFrame for integrity checking.
    
    Uses stable CSV serialization (no index, Unix line endings).
    """
    csv_bytes = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def _write_meta_json(path: Path, meta: dict[str, Any]) -> None:
    """Write metadata JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)


def _read_meta_json(path: Path) -> dict[str, Any]:
    """Read metadata JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dtypes_summary(df: DataFrame) -> dict[str, str]:
    """Return dict of column -> dtype as string."""
    return {col: str(dtype) for col, dtype in df.dtypes.items()}


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
    processed = data_processed_dir() / "kaggle_customer_profile.csv"

    if processed.exists():
        header = pd.read_csv(processed, nrows=0)
        parse_cols = [c for c in ["BirthDate", "Enrolled on", "Enrolled on "] if c in header.columns]
        df = pd.read_csv(processed, parse_dates=parse_cols, keep_default_na=True)
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

    df.to_csv(processed, index=False)

    return df


def load_hillstrom(target_col: str = "visit", use_cache: bool = True) -> Tuple[XType, YType, TType]:
    """
    Load the Hillstrom email marketing uplift dataset.

    Parameters
    ----------
    target_col : {'visit', 'conversion', 'spend'}
        Outcome to model.
    use_cache : bool, default True
        If True and cached snapshot exists, load from disk instead of fetching.

    Returns
    -------
    X : DataFrame
        Customer features (RFM, channel, demographics, etc.).
    y : Series
        Outcome Series (chosen target_col).
    t : Series
        Treatment assignment (email segment / control).
    """
    cache_path = data_processed_dir() / f"hillstrom_{target_col}.csv"
    meta_path = data_processed_dir() / f"hillstrom_{target_col}_meta.json"

    if use_cache and cache_path.exists():
        cached = pd.read_csv(cache_path)
        
        # Identify feature columns (everything except target and treatment_raw)
        non_feature_cols = [target_col, "treatment_raw"]
        feature_cols = [c for c in cached.columns if c not in non_feature_cols]
        
        X = cached[feature_cols]
        y = cast(Series, cached[target_col])
        y.name = target_col
        t = cast(Series, cached["treatment_raw"])
        t.name = "segment"
        
        print(f"Using cached Hillstrom {target_col} snapshot at {cache_path}")
        return X, y, t

    # Fetch from sklift
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

    # Create combined DataFrame for caching
    df_cache = X.copy()
    df_cache[target_col] = y
    df_cache["treatment_raw"] = t
    
    # Save cache
    df_cache.to_csv(cache_path, index=False)
    
    # Compute hash and save meta
    snapshot_hash = snapshot_hash_df(df_cache)
    meta = {
        "dataset": "hillstrom",
        "target_col": target_col,
        "n_rows": len(df_cache),
        "columns": list(df_cache.columns),
        "dtypes_summary": _dtypes_summary(df_cache),
        "snapshot_hash": snapshot_hash,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_meta_json(meta_path, meta)
    
    print(f"Created Hillstrom {target_col} snapshot at {cache_path}")
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
        Uses deterministic hash-based sampling for reproducibility.

    Returns
    -------
    X : DataFrame
        Feature matrix (anonymised user/context features).
    y : Series
        Outcome (chosen target_col).
    t : Series
        Binary treatment indicator.
    """
    cache_path = data_processed_dir() / f"criteo_{target_col}_10pct.csv"
    meta_path = data_processed_dir() / f"criteo_{target_col}_10pct_meta.json"

    if percent10 and cache_path.exists():
        cached = pd.read_csv(cache_path)
        if target_col in cached.columns and treatment_col in cached.columns:
            X_cached = cached.drop(columns=[target_col, treatment_col])
            y_cached = cast(Series, cached[target_col])
            y_cached.name = target_col
            t_cached = cast(Series, cached[treatment_col])
            if t_cached.name is None:
                t_cached.name = treatment_col
            print(f"Using cached Criteo 10% sample at {cache_path}")
            return X_cached, y_cached, t_cached
        else:
            print(f"Cached file {cache_path} missing required columns; regenerating deterministic 10% sample.")

    X_full, y_raw, t_raw = fetch_criteo(
        target_col=target_col,
        treatment_col=treatment_col,
        return_X_y_t=True,
        percent10=False,
    )

    y_full = cast(Series, y_raw)
    y_full.name = target_col

    t_full = cast(Series, t_raw)
    if t_full.name is None:
        t_full.name = treatment_col

    if percent10:
        # Combine into single DataFrame for sampling
        combined = X_full.copy()
        combined[target_col] = y_full
        combined[treatment_col] = t_full
        
        n_full = len(combined)
        
        # Deterministic hash-based 10% sampling
        # Method: hash each row and keep rows where hash % 10 == 0
        if CRITEO_SAMPLE_METHOD == "hash":
            row_hash = pd.util.hash_pandas_object(combined, index=True).astype("uint64")
            keep_mask = (row_hash % 10) == 0
            sampled = combined[keep_mask].reset_index(drop=True)
            sampling_info = {"method": "hash", "hash_modulo": 10, "keep_value": 0}
        else:
            # Alternative: seeded permutation (if hash method not preferred)
            rng = np.random.RandomState(CRITEO_SAMPLE_SEED)
            n_take = max(1, int(n_full * 0.10))
            indices = rng.permutation(n_full)[:n_take]
            sampled = combined.iloc[indices].reset_index(drop=True)
            sampling_info = {"method": "seeded_permutation", "seed": CRITEO_SAMPLE_SEED}
        
        n_sample = len(sampled)
        
        # Save cache
        sampled.to_csv(cache_path, index=False)
        
        # Compute hash and save meta
        snapshot_hash = snapshot_hash_df(sampled)
        meta = {
            "dataset": "criteo",
            "target_col": target_col,
            "treatment_col": treatment_col,
            "sampling": sampling_info,
            "n_full": n_full,
            "n_sample": n_sample,
            "sample_fraction": n_sample / n_full,
            "columns": list(sampled.columns),
            "dtypes_summary": _dtypes_summary(sampled),
            "snapshot_hash": snapshot_hash,
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
        _write_meta_json(meta_path, meta)
        
        print(f"Created deterministic Criteo 10% sample ({sampling_info['method']}) at {cache_path}")
        print(f"  Full size: {n_full}, Sample size: {n_sample} ({100*n_sample/n_full:.2f}%)")
        
        X_out = sampled.drop(columns=[target_col, treatment_col])
        y_out = cast(Series, sampled[target_col])
        y_out.name = target_col
        t_out = cast(Series, sampled[treatment_col])
        if t_out.name is None:
            t_out.name = treatment_col
        return X_out, y_out, t_out

    return X_full, y_full, t_full


def get_snapshot_meta(dataset: str, target_col: str, percent10: bool = True) -> dict[str, Any] | None:
    """
    Retrieve metadata for a dataset snapshot if it exists.
    
    Returns None if meta file doesn't exist.
    """
    if dataset == "hillstrom":
        meta_path = data_processed_dir() / f"hillstrom_{target_col}_meta.json"
    elif dataset == "criteo":
        suffix = "_10pct" if percent10 else ""
        meta_path = data_processed_dir() / f"criteo_{target_col}{suffix}_meta.json"
    else:
        return None
    
    if meta_path.exists():
        return _read_meta_json(meta_path)
    return None


if __name__ == "__main__":
    # Lightweight sanity check & CSV export
    processed_dir = data_processed_dir()

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
        X_h, y_h, t_h = load_hillstrom(target_col="visit", use_cache=False)
        print("X shape:", X_h.shape)
        print("y mean:", float(y_h.mean()))
        print("treatment counts:\n", t_h.value_counts())
    except Exception as exc:  # noqa: BLE001
        print("Hillstrom load FAILED:", exc)

    print("\n=== Criteo (conversion, 10%) ===")
    try:
        # Delete old cache to regenerate with new sampling method
        old_cache = processed_dir / "criteo_conversion_10pct.csv"
        if old_cache.exists():
            old_cache.unlink()
            print("Deleted old Criteo cache to regenerate with hash-based sampling")
        
        X_c, y_c, t_c = load_criteo(target_col="conversion", percent10=True)
        print("X shape:", X_c.shape)
        print("y mean:", float(y_c.mean()))
        print("treatment counts:\n", t_c.value_counts())
    except Exception as exc:  # noqa: BLE001
        print("Criteo load FAILED:", exc)
