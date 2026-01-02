"""
Step 3 Uplift Learners.

Implements T-Learner for uplift estimation.
Two separate models: one for treated (T=1), one for control (T=0).
Uplift = P(Y=1|X,T=1) - P(Y=1|X,T=0)
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from pandas import DataFrame, Series
from sklearn.linear_model import LogisticRegression

from src.paths import outputs_models_dir
from src.uplift_config import GLOBAL_SEED, MODEL_MAX_ITER, MODEL_C


def fit_t_learner(
    X_train: DataFrame,
    y_train: Series,
    t_train: Series,
    seed: int = GLOBAL_SEED,
) -> Tuple[LogisticRegression, LogisticRegression]:
    """
    Fit T-Learner: separate models for control and treated.
    
    Parameters
    ----------
    X_train : DataFrame
        Encoded training features.
    y_train : Series
        Training outcomes.
    t_train : Series
        Training treatment indicators (0=control, 1=treated).
    seed : int
        Random seed.
    
    Returns
    -------
    m0 : LogisticRegression
        Model trained on control group (T=0).
    m1 : LogisticRegression
        Model trained on treated group (T=1).
    """
    # Split by treatment
    control_mask = (t_train == 0).values
    treated_mask = (t_train == 1).values
    
    X_control = X_train[control_mask]
    y_control = y_train[control_mask]
    
    X_treated = X_train[treated_mask]
    y_treated = y_train[treated_mask]
    
    # Fit control model
    m0 = LogisticRegression(
        max_iter=MODEL_MAX_ITER,
        C=MODEL_C,
        random_state=seed,
        solver="lbfgs",
        n_jobs=-1,
    )
    m0.fit(X_control, y_control)
    
    # Fit treated model
    m1 = LogisticRegression(
        max_iter=MODEL_MAX_ITER,
        C=MODEL_C,
        random_state=seed,
        solver="lbfgs",
        n_jobs=-1,
    )
    m1.fit(X_treated, y_treated)
    
    return m0, m1


def predict_uplift_t_learner(
    m0: LogisticRegression,
    m1: LogisticRegression,
    X: DataFrame,
) -> np.ndarray:
    """
    Predict uplift using T-Learner.
    
    Uplift = P(Y=1|X,T=1) - P(Y=1|X,T=0)
    
    Parameters
    ----------
    m0 : LogisticRegression
        Control model.
    m1 : LogisticRegression
        Treated model.
    X : DataFrame
        Encoded features.
    
    Returns
    -------
    np.ndarray
        Uplift scores (can be negative).
    """
    p0 = m0.predict_proba(X)[:, 1]  # P(Y=1|X,T=0)
    p1 = m1.predict_proba(X)[:, 1]  # P(Y=1|X,T=1)
    
    return p1 - p0


def save_uplift_scores(
    row_id: Series,
    split_labels: Series,
    scores: np.ndarray,
    variant_key: str,
    learner_name: str = "tlearner",
) -> Path:
    """
    Save uplift scores to CSV.
    
    Parameters
    ----------
    row_id : Series
        Row identifiers.
    split_labels : Series
        Split assignments.
    scores : np.ndarray
        Uplift scores.
    variant_key : str
        Variant identifier.
    learner_name : str
        Learner identifier for filename.
    
    Returns
    -------
    Path
        Path to saved CSV.
    """
    df = pd.DataFrame({
        "row_id": row_id.values,
        "split": split_labels.values,
        "uplift_score": scores,
    })
    
    out_path = outputs_models_dir() / f"{variant_key}_uplift_scores_{learner_name}.csv"
    df.to_csv(out_path, index=False)
    
    return out_path
