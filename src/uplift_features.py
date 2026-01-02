"""
Step 3 Feature Engineering.

Handles encoding of categorical features with no leakage:
- Fit on train only
- Transform valid/test using fitted encoder
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Tuple

import pandas as pd
from pandas import DataFrame

from src.paths import outputs_models_dir


def _get_numeric_cols(X: DataFrame) -> list[str]:
    """Get numeric column names."""
    return X.select_dtypes(include=["number"]).columns.tolist()


def _get_categorical_cols(X: DataFrame) -> list[str]:
    """Get categorical/object column names."""
    return X.select_dtypes(include=["object", "category"]).columns.tolist()


def fit_transform_train(
    X_train_raw: DataFrame,
    variant_key: str,
) -> Tuple[DataFrame, dict[str, Any]]:
    """
    Fit encoders on training data and transform.
    
    Uses one-hot encoding for categorical columns (simple, stable approach).
    
    Parameters
    ----------
    X_train_raw : DataFrame
        Raw training features.
    variant_key : str
        Variant identifier for saving encoder artifact.
    
    Returns
    -------
    X_train : DataFrame
        Encoded training features.
    artifact : dict
        Encoding artifact containing:
        - numeric_cols: list of numeric column names
        - categorical_cols: list of categorical column names  
        - onehot_columns: list of column names after one-hot encoding
        - category_mappings: dict of col -> sorted unique values
    """
    numeric_cols = _get_numeric_cols(X_train_raw)
    categorical_cols = _get_categorical_cols(X_train_raw)
    
    # Build category mappings from training data
    category_mappings = {}
    for col in categorical_cols:
        unique_vals = sorted(X_train_raw[col].dropna().astype(str).unique().tolist())
        category_mappings[col] = unique_vals
    
    # Create encoded DataFrame
    encoded_parts = []
    
    # Add numeric columns as-is (with NaN handling)
    if numeric_cols:
        numeric_df = X_train_raw[numeric_cols].copy()
        # Fill NaN with 0 for numeric (simple approach)
        numeric_df = numeric_df.fillna(0)
        encoded_parts.append(numeric_df)
    
    # One-hot encode categorical columns
    onehot_columns = list(numeric_cols)
    for col in categorical_cols:
        # Get dummies using only categories seen in training
        col_data = X_train_raw[col].astype(str).fillna("_missing_")
        for cat in category_mappings[col]:
            new_col_name = f"{col}_{cat}"
            encoded_parts.append(pd.DataFrame({new_col_name: (col_data == cat).astype(int)}))
            onehot_columns.append(new_col_name)
    
    X_train = pd.concat(encoded_parts, axis=1) if encoded_parts else pd.DataFrame(index=X_train_raw.index)
    
    # Build artifact
    artifact = {
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "onehot_columns": onehot_columns,
        "category_mappings": category_mappings,
    }
    
    # Save artifact
    out_dir = outputs_models_dir()
    artifact_path = out_dir / f"{variant_key}_encoder.json"
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    
    print(f"Saved encoder artifact to {artifact_path}")
    
    return X_train, artifact


def transform(X_raw: DataFrame, artifact: dict[str, Any]) -> DataFrame:
    """
    Transform features using fitted encoder artifact.
    
    Parameters
    ----------
    X_raw : DataFrame
        Raw features to transform.
    artifact : dict
        Encoding artifact from fit_transform_train.
    
    Returns
    -------
    DataFrame
        Encoded features with same columns as training.
    """
    numeric_cols = artifact["numeric_cols"]
    categorical_cols = artifact["categorical_cols"]
    category_mappings = artifact["category_mappings"]
    
    encoded_parts = []
    
    # Add numeric columns
    if numeric_cols:
        numeric_df = X_raw[numeric_cols].copy()
        numeric_df = numeric_df.fillna(0)
        encoded_parts.append(numeric_df)
    
    # One-hot encode categorical columns (using only training categories)
    for col in categorical_cols:
        col_data = X_raw[col].astype(str).fillna("_missing_")
        for cat in category_mappings[col]:
            new_col_name = f"{col}_{cat}"
            encoded_parts.append(pd.DataFrame({new_col_name: (col_data == cat).astype(int)}, index=X_raw.index))
    
    X = pd.concat(encoded_parts, axis=1) if encoded_parts else pd.DataFrame(index=X_raw.index)
    
    return X


def load_encoder_artifact(variant_key: str) -> dict[str, Any]:
    """Load encoder artifact from disk."""
    artifact_path = outputs_models_dir() / f"{variant_key}_encoder.json"
    with open(artifact_path, "r", encoding="utf-8") as f:
        return json.load(f)


def assert_no_leakage(X: DataFrame, outcome_name: str, treatment_name: str) -> None:
    """
    Verify that outcome and treatment columns are not in features.
    
    Raises
    ------
    ValueError
        If leakage detected.
    """
    cols = set(X.columns)
    leaked = []
    
    if outcome_name in cols:
        leaked.append(outcome_name)
    if treatment_name in cols:
        leaked.append(treatment_name)
    
    # Also check common variants
    for variant in ["treatment", "treatment_raw", "y", "outcome", "target"]:
        if variant in cols:
            leaked.append(variant)
    
    if leaked:
        raise ValueError(f"Leakage detected! Found these columns in features: {leaked}")
