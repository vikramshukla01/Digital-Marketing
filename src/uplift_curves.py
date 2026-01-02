"""
Step 3 Uplift and Qini Curves.

Computes uplift curve points, AUUC, Qini curve, and Qini coefficient
using IPW estimation.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import outputs_models_dir
from src.uplift_config import N_BINS
from src.uplift_policy import estimate_policy_value_ipw


def uplift_curve_points_ipw(
    y_test: np.ndarray,
    t_test: np.ndarray,
    score: np.ndarray,
    p_treat: float,
    n_bins: int = N_BINS,
) -> pd.DataFrame:
    """
    Compute uplift curve points using IPW estimation.
    
    Sorts by score descending and computes cumulative
    incremental conversions at each bin threshold.
    
    Parameters
    ----------
    y_test : np.ndarray
        Test outcomes.
    t_test : np.ndarray
        Test treatment indicators.
    score : np.ndarray
        Uplift scores (higher = target first).
    p_treat : float
        Treatment probability from training.
    n_bins : int
        Number of evaluation points.
    
    Returns
    -------
    pd.DataFrame
        Columns: fraction_contacted, n_contacted, incremental_hat_cum, incremental_per_1000_cum.
    """
    n = len(y_test)
    
    # Sort by score descending
    sort_idx = np.argsort(-score)
    y_sorted = y_test[sort_idx]
    t_sorted = t_test[sort_idx]
    
    # Create evaluation thresholds
    thresholds = np.linspace(0, 1, n_bins + 1)[1:]  # Skip 0%
    
    rows = []
    for frac in thresholds:
        n_contacted = max(1, int(n * frac))
        selected_mask = np.zeros(n, dtype=bool)
        selected_mask[:n_contacted] = True
        
        incremental_cum = estimate_policy_value_ipw(y_sorted, t_sorted, selected_mask, p_treat)
        incremental_per_1000_cum = (incremental_cum / n_contacted) * 1000 if n_contacted > 0 else 0.0
        
        rows.append({
            "fraction_contacted": frac,
            "n_contacted": n_contacted,
            "incremental_hat_cum": incremental_cum,
            "incremental_per_1000_cum": incremental_per_1000_cum,
        })
    
    return pd.DataFrame(rows)


def auuc_from_curve(curve_df: pd.DataFrame) -> float:
    """
    Compute Area Under Uplift Curve using trapezoidal rule.
    
    Uses fraction_contacted (x) vs incremental_per_1000_cum (y).
    
    Parameters
    ----------
    curve_df : pd.DataFrame
        Uplift curve from uplift_curve_points_ipw.
    
    Returns
    -------
    float
        AUUC value.
    """
    x = curve_df["fraction_contacted"].values
    y = curve_df["incremental_per_1000_cum"].values
    
    # Prepend origin (0, 0)
    x = np.concatenate([[0], x])
    y = np.concatenate([[0], y])
    
    # Trapezoidal integration
    return float(np.trapz(y, x))


def compute_ate_ipw(
    y: np.ndarray,
    t: np.ndarray,
    p_treat: float,
) -> float:
    """
    Compute Average Treatment Effect using IPW.
    
    ATE = E[Y(1) - Y(0)] estimated via IPW.
    
    Returns
    -------
    float
        ATE estimate.
    """
    if p_treat <= 0 or p_treat >= 1:
        raise ValueError(f"p_treat must be in (0, 1), got {p_treat}")
    
    n = len(y)
    if n == 0:
        return 0.0
    
    # IPW estimator
    treated_term = t * y / p_treat
    control_term = (1 - t) * y / (1 - p_treat)
    
    return float(np.mean(treated_term - control_term))


def qini_curve_points(
    curve_df: pd.DataFrame,
    ate_ipw_test: float,
) -> pd.DataFrame:
    """
    Compute Qini curve points.
    
    Qini = uplift curve - random baseline.
    Random baseline is linear: ATE * fraction * n_total.
    
    Parameters
    ----------
    curve_df : pd.DataFrame
        Uplift curve from uplift_curve_points_ipw.
    ate_ipw_test : float
        ATE on test set for computing random baseline.
    
    Returns
    -------
    pd.DataFrame
        Original columns plus: random_baseline, qini.
    """
    result = curve_df.copy()
    
    # Random baseline: at fraction f, expected cumulative uplift = ATE * n_contacted
    result["random_baseline"] = ate_ipw_test * result["n_contacted"]
    
    # Qini = model cumulative - random baseline
    result["qini"] = result["incremental_hat_cum"] - result["random_baseline"]
    
    return result


def qini_coeff_from_curve(qini_df: pd.DataFrame) -> float:
    """
    Compute Qini coefficient from Qini curve.
    
    Uses trapezoidal integration of qini values over fraction_contacted.
    
    Parameters
    ----------
    qini_df : pd.DataFrame
        Qini curve from qini_curve_points.
    
    Returns
    -------
    float
        Qini coefficient.
    """
    x = qini_df["fraction_contacted"].values
    y = qini_df["qini"].values
    
    # Prepend origin
    x = np.concatenate([[0], x])
    y = np.concatenate([[0], y])
    
    return float(np.trapz(y, x))


def save_uplift_curve(
    curve_df: pd.DataFrame,
    variant_key: str,
) -> Path:
    """Save uplift curve points to CSV."""
    out_path = outputs_models_dir() / f"{variant_key}_uplift_curve_points.csv"
    curve_df.to_csv(out_path, index=False)
    return out_path


def save_qini_curve(
    qini_df: pd.DataFrame,
    variant_key: str,
) -> Path:
    """Save Qini curve points to CSV."""
    out_path = outputs_models_dir() / f"{variant_key}_qini_curve_points.csv"
    qini_df.to_csv(out_path, index=False)
    return out_path


def save_summary_metrics(
    metrics: dict,
    variant_key: str,
) -> Path:
    """Save summary metrics to CSV."""
    out_path = outputs_models_dir() / f"{variant_key}_summary_metrics.csv"
    df = pd.DataFrame([metrics])
    df.to_csv(out_path, index=False)
    return out_path
