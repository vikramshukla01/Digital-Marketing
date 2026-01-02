"""
Step 3 Baseline Models.

Implements response propensity model P(Y|X) as baseline.
Uses stable Logistic Regression with no deep tuning.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
from sklearn.linear_model import LogisticRegression

from src.paths import outputs_models_dir
from src.uplift_config import GLOBAL_SEED, MODEL_MAX_ITER, MODEL_C


def fit_response_propensity_model(
    X_train: DataFrame,
    y_train: Series,
    seed: int = GLOBAL_SEED,
) -> LogisticRegression:
    """
    Train baseline response propensity model P(Y|X).
    
    This model predicts the probability of the outcome
    given features, ignoring treatment. Used as baseline
    for comparison with uplift models.
    
    Parameters
    ----------
    X_train : DataFrame
        Encoded training features.
    y_train : Series
        Training outcomes (binary).
    seed : int
        Random seed.
    
    Returns
    -------
    LogisticRegression
        Fitted model.
    """
    model = LogisticRegression(
        max_iter=MODEL_MAX_ITER,
        C=MODEL_C,
        random_state=seed,
        solver="lbfgs",
        n_jobs=-1,
    )
    
    model.fit(X_train, y_train)
    
    return model


def predict_response_propensity(
    model: LogisticRegression,
    X: DataFrame,
) -> np.ndarray:
    """
    Predict response propensity P(Y=1|X).
    
    Parameters
    ----------
    model : LogisticRegression
        Fitted propensity model.
    X : DataFrame
        Encoded features.
    
    Returns
    -------
    np.ndarray
        Probability scores P(Y=1|X).
    """
    return model.predict_proba(X)[:, 1]


def save_propensity_scores(
    row_id: Series,
    split_labels: Series,
    scores: np.ndarray,
    variant_key: str,
) -> Path:
    """
    Save baseline propensity scores to CSV.
    
    Parameters
    ----------
    row_id : Series
        Row identifiers.
    split_labels : Series
        Split assignments ('train', 'valid', 'test').
    scores : np.ndarray
        Propensity scores.
    variant_key : str
        Variant identifier.
    
    Returns
    -------
    Path
        Path to saved CSV.
    """
    df = pd.DataFrame({
        "row_id": row_id.values,
        "split": split_labels.values,
        "propensity_score": scores,
    })
    
    out_path = outputs_models_dir() / f"{variant_key}_baseline_propensity_scores.csv"
    df.to_csv(out_path, index=False)
    
    return out_path
