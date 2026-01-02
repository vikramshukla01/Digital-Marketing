"""
Step 3 Policy Evaluation.

Implements Horvitz-Thompson IPW estimator for policy value
and targeting simulations comparing uplift vs propensity vs random.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from pandas import Series

from src.paths import outputs_models_dir
from src.uplift_config import POLICY_PCTS, RANDOM_BASELINE_SEED


def estimate_policy_value_ipw(
    y: np.ndarray,
    t: np.ndarray,
    selected_mask: np.ndarray,
    p_treat: float,
) -> float:
    """
    Horvitz-Thompson IPW estimator for policy value.
    
    Estimates the incremental conversions from targeting
    the selected population.
    
    Formula:
    Delta_hat(S) = sum_{i in S} (T_i * Y_i / p - (1-T_i) * Y_i / (1-p))
    
    Parameters
    ----------
    y : np.ndarray
        Outcome values (0/1).
    t : np.ndarray
        Treatment indicators (0/1).
    selected_mask : np.ndarray
        Boolean mask for selected (targeted) population.
    p_treat : float
        Treatment probability (proportion treated in train).
    
    Returns
    -------
    float
        Estimated incremental value for selected population.
    """
    if p_treat <= 0 or p_treat >= 1:
        raise ValueError(f"p_treat must be in (0, 1), got {p_treat}")
    
    y_sel = y[selected_mask]
    t_sel = t[selected_mask]
    
    if len(y_sel) == 0:
        return 0.0
    
    # IPW formula: T*Y/p - (1-T)*Y/(1-p)
    treated_term = t_sel * y_sel / p_treat
    control_term = (1 - t_sel) * y_sel / (1 - p_treat)
    
    return float(np.sum(treated_term - control_term))


def policy_table_from_scores(
    row_id: np.ndarray,
    y_test: np.ndarray,
    t_test: np.ndarray,
    score: np.ndarray,
    p_treat: float,
    pcts: List[float] = POLICY_PCTS,
) -> pd.DataFrame:
    """
    Create policy table showing incremental value at each targeting percentage.
    
    Parameters
    ----------
    row_id : np.ndarray
        Row identifiers.
    y_test : np.ndarray
        Test outcomes.
    t_test : np.ndarray
        Test treatment indicators.
    score : np.ndarray
        Uplift scores for ranking (higher = target first).
    p_treat : float
        Treatment probability from training.
    pcts : list of float
        Percentages to evaluate (e.g., [0.01, 0.05, 0.10, ...]).
    
    Returns
    -------
    pd.DataFrame
        Columns: percent_contacted, n_contacted, incremental_hat, incremental_per_1000.
    """
    n = len(y_test)
    
    # Sort by score descending
    sort_idx = np.argsort(-score)
    y_sorted = y_test[sort_idx]
    t_sorted = t_test[sort_idx]
    
    rows = []
    for pct in pcts:
        n_contacted = max(1, int(n * pct))
        selected_mask = np.zeros(n, dtype=bool)
        selected_mask[:n_contacted] = True
        
        incremental = estimate_policy_value_ipw(y_sorted, t_sorted, selected_mask, p_treat)
        
        # Scale to per 1000 contacted
        incremental_per_1000 = (incremental / n_contacted) * 1000 if n_contacted > 0 else 0.0
        
        rows.append({
            "percent_contacted": pct,
            "n_contacted": n_contacted,
            "incremental_hat": incremental,
            "incremental_per_1000": incremental_per_1000,
        })
    
    return pd.DataFrame(rows)


def targeting_simulation_compare(
    y_test: np.ndarray,
    t_test: np.ndarray,
    uplift_score: np.ndarray,
    propensity_score: np.ndarray,
    p_treat: float,
    pcts: List[float] = POLICY_PCTS,
    seed: int = RANDOM_BASELINE_SEED,
) -> pd.DataFrame:
    """
    Compare targeting strategies: uplift vs propensity vs random.
    
    Parameters
    ----------
    y_test : np.ndarray
        Test outcomes.
    t_test : np.ndarray
        Test treatment indicators.
    uplift_score : np.ndarray
        Uplift scores (T-learner).
    propensity_score : np.ndarray
        Response propensity scores P(Y|X).
    p_treat : float
        Treatment probability from training.
    pcts : list of float
        Percentages to evaluate.
    seed : int
        Seed for random baseline.
    
    Returns
    -------
    pd.DataFrame
        Columns: strategy, percent_contacted, n_contacted, incremental_hat, incremental_per_1000.
    """
    n = len(y_test)
    rng = np.random.RandomState(seed)
    random_score = rng.random(n)
    
    strategies = {
        "uplift_tlearner": uplift_score,
        "propensity": propensity_score,
        "random": random_score,
    }
    
    rows = []
    for strategy_name, scores in strategies.items():
        table = policy_table_from_scores(
            row_id=np.arange(n),
            y_test=y_test,
            t_test=t_test,
            score=scores,
            p_treat=p_treat,
            pcts=pcts,
        )
        table["strategy"] = strategy_name
        rows.append(table)
    
    result = pd.concat(rows, ignore_index=True)
    
    # Reorder columns
    cols = ["strategy", "percent_contacted", "n_contacted", "incremental_hat", "incremental_per_1000"]
    return result[cols]


def save_policy_table(
    table: pd.DataFrame,
    variant_key: str,
) -> Path:
    """Save policy table to CSV."""
    out_path = outputs_models_dir() / f"{variant_key}_policy_table.csv"
    table.to_csv(out_path, index=False)
    return out_path


def save_targeting_simulation(
    table: pd.DataFrame,
    variant_key: str,
) -> Path:
    """Save targeting simulation to CSV."""
    out_path = outputs_models_dir() / f"{variant_key}_targeting_simulation.csv"
    table.to_csv(out_path, index=False)
    return out_path
