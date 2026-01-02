"""
Step 3 Dataset Adapters.

Provides standardized access to datasets for uplift modeling.
All dataset loading goes through src.data_loading only.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from pandas import DataFrame, Series

from src.data_loading import (
    load_hillstrom,
    load_criteo,
    get_snapshot_meta,
)


def binarize_hillstrom_arm(
    X: DataFrame,
    y: Series,
    t: Series,
    arm: str,
) -> tuple[DataFrame, Series, Series]:
    """
    Filter Hillstrom data to binary comparison: arm vs No E-Mail.
    
    Parameters
    ----------
    X : DataFrame
        Feature matrix from load_hillstrom.
    y : Series
        Outcome series.
    t : Series
        Treatment series with values like 'Mens E-Mail', 'Womens E-Mail', 'No E-Mail'.
    arm : str
        Which email arm to compare against control.
        Must be one of: 'Mens E-Mail', 'Womens E-Mail'.
    
    Returns
    -------
    X_bin : DataFrame
        Features for rows in {arm, 'No E-Mail'}.
    y_bin : Series
        Outcome for those rows.
    t_bin : Series
        Binary treatment: 1 if arm, 0 if 'No E-Mail'.
    """
    valid_arms = ["Mens E-Mail", "Womens E-Mail"]
    if arm not in valid_arms:
        raise ValueError(f"arm must be one of {valid_arms}, got '{arm}'")
    
    control_label = "No E-Mail"
    
    # Convert to string and strip for safety
    t_clean = t.astype(str).str.strip()
    
    # Create mask for rows in this binary comparison
    mask = t_clean.isin([arm, control_label])
    
    # Filter
    X_bin = X.loc[mask].reset_index(drop=True)
    y_bin = y.loc[mask].reset_index(drop=True)
    t_filtered = t_clean.loc[mask].reset_index(drop=True)
    
    # Binarize treatment: 1 = arm (treated), 0 = control
    t_bin = (t_filtered == arm).astype(int)
    t_bin.name = "treatment"
    
    return X_bin, y_bin, t_bin


def get_dataset_variant(
    dataset: str,
    target: str,
    arm: Optional[str] = None,
) -> dict[str, Any]:
    """
    Load a dataset variant in standardized format for uplift modeling.
    
    Parameters
    ----------
    dataset : str
        One of 'hillstrom', 'criteo'.
    target : str
        Outcome column name ('visit', 'conversion', etc.).
    arm : str, optional
        For Hillstrom, which arm to binarize against control.
        Required for Hillstrom, ignored for Criteo.
    
    Returns
    -------
    dict with keys:
        - variant_key : str
            Unique identifier for this variant (e.g., 'hillstrom_mens_visit').
        - X_raw : DataFrame
            Raw feature matrix.
        - y : Series
            Outcome series (int or float).
        - t : Series
            Binary treatment series (0/1 int).
        - snapshot_hash : str or None
            Hash of the source snapshot for integrity.
        - treatment_name : str
            Human-readable treatment description.
        - outcome_name : str
            Outcome column name.
    """
    if dataset == "hillstrom":
        if arm is None:
            raise ValueError("arm is required for Hillstrom dataset")
        
        # Load full Hillstrom data
        X_full, y_full, t_full = load_hillstrom(target_col=target, use_cache=True)
        
        # Binarize to specific arm vs control
        X_raw, y, t = binarize_hillstrom_arm(X_full, y_full, t_full, arm)
        
        # Build variant key
        arm_short = arm.lower().replace(" e-mail", "").replace(" ", "_")
        variant_key = f"hillstrom_{arm_short}_{target}"
        
        # Get snapshot meta
        meta = get_snapshot_meta("hillstrom", target)
        snapshot_hash = meta.get("snapshot_hash") if meta else None
        
        return {
            "variant_key": variant_key,
            "X_raw": X_raw,
            "y": y,
            "t": t,
            "snapshot_hash": snapshot_hash,
            "treatment_name": f"{arm} vs No E-Mail",
            "outcome_name": target,
        }
    
    elif dataset == "criteo":
        # Load Criteo 10% sample
        X_raw, y, t = load_criteo(target_col=target, percent10=True)
        
        # Ensure treatment is int
        t = t.astype(int)
        t.name = "treatment"
        
        variant_key = f"criteo_{target}"
        
        # Get snapshot meta
        meta = get_snapshot_meta("criteo", target, percent10=True)
        snapshot_hash = meta.get("snapshot_hash") if meta else None
        
        return {
            "variant_key": variant_key,
            "X_raw": X_raw,
            "y": y,
            "t": t,
            "snapshot_hash": snapshot_hash,
            "treatment_name": "treatment=1 vs treatment=0",
            "outcome_name": target,
        }
    
    else:
        raise ValueError(f"Unknown dataset: {dataset}. Must be 'hillstrom' or 'criteo'.")
