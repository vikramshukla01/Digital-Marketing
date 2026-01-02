"""
Step 3 Train/Valid/Test Splits.

Provides deterministic stratified splitting with integrity guards.
Split indices are saved to Outputs/Models/ and reused if they exist.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
from sklearn.model_selection import train_test_split

from src.paths import outputs_models_dir
from src.uplift_config import GLOBAL_SEED, TRAIN_FRAC, VALID_FRAC


def make_row_id(X_raw: DataFrame) -> Series:
    """
    Create deterministic row IDs using hash of row content.
    
    Parameters
    ----------
    X_raw : DataFrame
        Raw feature matrix.
    
    Returns
    -------
    Series
        uint64 row IDs (hash-based).
    """
    row_id = pd.util.hash_pandas_object(X_raw, index=True).astype("uint64")
    row_id.name = "row_id"
    return row_id


def _create_stratified_splits(
    row_id: Series,
    y: Series,
    t: Series,
    seed: int = GLOBAL_SEED,
) -> DataFrame:
    """
    Create stratified train/valid/test splits.
    
    Stratifies by joint (treatment, outcome) label to preserve
    treatment-outcome distribution in each split.
    
    Parameters
    ----------
    row_id : Series
        Unique row identifiers.
    y : Series
        Outcome series.
    t : Series
        Treatment series.
    seed : int
        Random seed for reproducibility.
    
    Returns
    -------
    DataFrame
        Columns: [row_id, split] where split in {'train', 'valid', 'test'}.
    """
    n = len(row_id)
    
    # Create joint stratification label: "t_y"
    strat_label = t.astype(str) + "_" + y.astype(str)
    
    # First split: train vs (valid+test)
    valid_test_frac = VALID_FRAC + (1 - TRAIN_FRAC - VALID_FRAC)
    
    idx_train, idx_rest = train_test_split(
        np.arange(n),
        test_size=valid_test_frac,
        stratify=strat_label,
        random_state=seed,
    )
    
    # Second split: valid vs test from rest
    strat_rest = strat_label.iloc[idx_rest]
    test_frac_of_rest = (1 - TRAIN_FRAC - VALID_FRAC) / valid_test_frac
    
    idx_valid, idx_test = train_test_split(
        idx_rest,
        test_size=test_frac_of_rest,
        stratify=strat_rest,
        random_state=seed,
    )
    
    # Build result DataFrame
    split_labels = pd.Series(index=range(n), dtype=str)
    split_labels.iloc[idx_train] = "train"
    split_labels.iloc[idx_valid] = "valid"
    split_labels.iloc[idx_test] = "test"
    
    result = pd.DataFrame({
        "row_id": row_id.values,
        "split": split_labels.values,
    })
    
    return result


def _save_split_indices(
    split_df: DataFrame,
    variant_key: str,
    snapshot_hash: str | None,
    seed: int,
) -> Path:
    """
    Save split indices and metadata.
    
    Returns
    -------
    Path
        Path to saved split indices CSV.
    """
    out_dir = outputs_models_dir()
    
    # Save split indices
    split_path = out_dir / f"{variant_key}_split_indices.csv"
    split_df.to_csv(split_path, index=False)
    
    # Save metadata
    meta = {
        "variant_key": variant_key,
        "snapshot_hash": snapshot_hash,
        "seed": seed,
        "n_rows": len(split_df),
        "split_counts": split_df["split"].value_counts().to_dict(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = out_dir / f"{variant_key}_split_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    
    return split_path


def _load_split_meta(variant_key: str) -> dict | None:
    """Load split metadata if it exists."""
    meta_path = outputs_models_dir() / f"{variant_key}_split_meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def make_or_load_splits(
    variant_key: str,
    row_id: Series,
    y: Series,
    t: Series,
    snapshot_hash: str | None,
) -> DataFrame:
    """
    Load existing splits or create new ones if they don't exist.
    
    Parameters
    ----------
    variant_key : str
        Unique identifier for this variant.
    row_id : Series
        Row identifiers (from make_row_id).
    y : Series
        Outcome series.
    t : Series
        Treatment series.
    snapshot_hash : str or None
        Current snapshot hash for integrity checking.
    
    Returns
    -------
    DataFrame
        Columns: [row_id, split].
    
    Raises
    ------
    RuntimeError
        If split file exists but snapshot hash has changed.
    """
    out_dir = outputs_models_dir()
    split_path = out_dir / f"{variant_key}_split_indices.csv"
    
    if split_path.exists():
        # Load existing splits
        split_df = pd.read_csv(split_path)
        
        # Integrity check
        meta = _load_split_meta(variant_key)
        if meta and snapshot_hash:
            stored_hash = meta.get("snapshot_hash")
            if stored_hash and stored_hash != snapshot_hash:
                raise RuntimeError(
                    f"Snapshot hash mismatch for {variant_key}!\n"
                    f"Stored: {stored_hash}\n"
                    f"Current: {snapshot_hash}\n"
                    "Delete split files to regenerate, or investigate data change."
                )
        
        print(f"Loaded existing splits from {split_path}")
        return split_df
    
    # Create new splits
    print(f"Creating new stratified splits for {variant_key}...")
    split_df = _create_stratified_splits(row_id, y, t, seed=GLOBAL_SEED)
    
    # Save
    saved_path = _save_split_indices(split_df, variant_key, snapshot_hash, GLOBAL_SEED)
    print(f"Saved split indices to {saved_path}")
    
    return split_df


def get_split_masks(
    row_id: Series,
    split_df: DataFrame,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Get boolean masks for train/valid/test from split DataFrame.
    
    Parameters
    ----------
    row_id : Series
        Row identifiers for current data.
    split_df : DataFrame
        Split assignments with columns [row_id, split].
    
    Returns
    -------
    train_mask, valid_mask, test_mask : np.ndarray
        Boolean arrays aligned with row_id.
    """
    # Create mapping from row_id to split
    id_to_split = dict(zip(split_df["row_id"], split_df["split"]))
    
    splits = row_id.map(id_to_split)
    
    train_mask = (splits == "train").values
    valid_mask = (splits == "valid").values
    test_mask = (splits == "test").values
    
    return train_mask, valid_mask, test_mask
