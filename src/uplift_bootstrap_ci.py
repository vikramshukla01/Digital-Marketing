"""
Step 3 Bootstrap Confidence Intervals.

Computes bootstrap CIs for targeting simulation strategies.
Does NOT retrain models - reads from existing Step 3 CSVs.

Usage:
    python -m src.uplift_bootstrap_ci --variant hillstrom_mens_visit --B 300 --seed 123
    python -m src.uplift_bootstrap_ci --all --B 300 --seed 123
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

from src.paths import outputs_models_dir
from src.uplift_config import POLICY_PCTS
from src.uplift_dataset_adapters import get_dataset_variant


# Variants
ALL_VARIANTS = [
    "hillstrom_mens_visit",
    "hillstrom_womens_visit",
    "criteo_conversion",
]


def _load_csv(path: Path) -> pd.DataFrame:
    """Load CSV or raise if not found."""
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    return pd.read_csv(path)


def _compute_incremental_per_1000_ipw(
    y: np.ndarray,
    t: np.ndarray,
    selected_mask: np.ndarray,
    p_treat: float,
) -> float:
    """
    Compute incremental per 1000 using IPW/Horvitz-Thompson estimator.
    
    Formula: Delta_hat(S) = sum_{i in S} (T_i*Y_i/p - (1-T_i)*Y_i/(1-p))
    incremental_per_1000 = 1000 * Delta_hat / |S|
    """
    n_selected = selected_mask.sum()
    if n_selected == 0:
        return 0.0
    
    y_sel = y[selected_mask]
    t_sel = t[selected_mask]
    
    treated_term = t_sel * y_sel / p_treat
    control_term = (1 - t_sel) * y_sel / (1 - p_treat)
    delta_hat = np.sum(treated_term - control_term)
    
    return 1000.0 * delta_hat / n_selected


def _get_top_k_mask(scores: np.ndarray, k: int) -> np.ndarray:
    """Return boolean mask for top-k rows by score (descending)."""
    n = len(scores)
    k = max(1, min(k, n))
    
    # Get indices of top k scores
    top_indices = np.argpartition(-scores, k - 1)[:k]
    mask = np.zeros(n, dtype=bool)
    mask[top_indices] = True
    return mask


def _bootstrap_incremental(
    y: np.ndarray,
    t: np.ndarray,
    scores: np.ndarray,
    p_treat: float,
    pct: float,
    B: int,
    rng: np.random.RandomState,
) -> Tuple[float, float, float]:
    """
    Bootstrap incremental_per_1000 for a given targeting percentage.
    
    Returns (point_estimate, ci_low, ci_high).
    """
    n = len(y)
    k = max(1, int(n * pct))
    
    # Point estimate on full sample
    mask = _get_top_k_mask(scores, k)
    point_est = _compute_incremental_per_1000_ipw(y, t, mask, p_treat)
    
    # Bootstrap
    boot_estimates = np.empty(B)
    for b in range(B):
        # Resample test rows with replacement
        idx = rng.choice(n, size=n, replace=True)
        y_b = y[idx]
        t_b = t[idx]
        scores_b = scores[idx]
        
        mask_b = _get_top_k_mask(scores_b, k)
        boot_estimates[b] = _compute_incremental_per_1000_ipw(y_b, t_b, mask_b, p_treat)
    
    ci_low = float(np.percentile(boot_estimates, 2.5))
    ci_high = float(np.percentile(boot_estimates, 97.5))
    
    return point_est, ci_low, ci_high


def run_bootstrap_ci(
    variant_key: str,
    B: int = 300,
    seed: int = 123,
) -> dict:
    """
    Compute bootstrap CIs for a variant.
    
    Returns dict with output file paths.
    """
    print(f"\n{'='*50}")
    print(f"BOOTSTRAP CI: {variant_key}")
    print(f"  B={B}, seed={seed}")
    print("=" * 50)
    
    out_dir = outputs_models_dir()
    
    # Parse dataset info from variant_key
    if variant_key.startswith("hillstrom_mens"):
        dataset, target, arm = "hillstrom", "visit", "Mens E-Mail"
    elif variant_key.startswith("hillstrom_womens"):
        dataset, target, arm = "hillstrom", "visit", "Womens E-Mail"
    elif variant_key.startswith("criteo"):
        dataset, target, arm = "criteo", "conversion", None
    else:
        raise ValueError(f"Unknown variant: {variant_key}")
    
    # Load dataset via adapter
    print("\n[1/5] Loading dataset...")
    variant = get_dataset_variant(dataset, target, arm)
    y_full = variant["y"].values
    t_full = variant["t"].values
    
    # Load split indices
    print("[2/5] Loading split indices...")
    split_df = _load_csv(out_dir / f"{variant_key}_split_indices.csv")
    
    # Match row_id order
    # The dataset adapter returns data in order, so row 0 = row_id at index 0
    # We need to identify train and test rows
    train_mask = (split_df["split"] == "train").values
    test_mask = (split_df["split"] == "test").values
    
    y_train = y_full[train_mask]
    t_train = t_full[train_mask]
    y_test = y_full[test_mask]
    t_test = t_full[test_mask]
    
    n_train = train_mask.sum()
    n_test = test_mask.sum()
    print(f"  Train: {n_train}, Test: {n_test}")
    
    # p_treat from train
    p_treat = float(t_train.mean())
    print(f"  p_treat (train): {p_treat:.4f}")
    
    # Load scores (test split only)
    print("[3/5] Loading scores...")
    uplift_df = _load_csv(out_dir / f"{variant_key}_uplift_scores_tlearner.csv")
    propensity_df = _load_csv(out_dir / f"{variant_key}_baseline_propensity_scores.csv")
    
    uplift_test = uplift_df[uplift_df["split"] == "test"]["uplift_score"].values
    propensity_test = propensity_df[propensity_df["split"] == "test"]["propensity_score"].values
    
    if len(uplift_test) != n_test:
        raise ValueError(f"Score/split mismatch: {len(uplift_test)} scores vs {n_test} test rows")
    
    # Random scores (deterministic within each run)
    rng_main = np.random.RandomState(seed)
    random_test = rng_main.random(n_test)
    
    # Prepare strategies
    strategies = {
        "uplift_tlearner": uplift_test,
        "propensity": propensity_test,
        "random": random_test,
    }
    
    # Bootstrap for each strategy and percent
    print(f"[4/5] Running bootstrap (B={B})...")
    
    targeting_rows = []
    diff_rows = []  # uplift - propensity
    policy_rows = []  # uplift only
    
    for pct in POLICY_PCTS:
        rng_boot = np.random.RandomState(seed)  # Reset for reproducibility
        
        results_by_strategy = {}
        
        for strategy_name, scores in strategies.items():
            point, ci_low, ci_high = _bootstrap_incremental(
                y_test, t_test, scores, p_treat, pct, B, rng_boot
            )
            
            targeting_rows.append({
                "strategy": strategy_name,
                "percent_contacted": pct,
                "incremental_per_1000": point,
                "ci_low": ci_low,
                "ci_high": ci_high,
            })
            
            results_by_strategy[strategy_name] = (point, ci_low, ci_high)
            
            # Policy table for uplift only
            if strategy_name == "uplift_tlearner":
                policy_rows.append({
                    "percent_contacted": pct,
                    "incremental_per_1000": point,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                })
        
        # Compute uplift - propensity difference with bootstrap
        uplift_pt, _, _ = results_by_strategy["uplift_tlearner"]
        propensity_pt, _, _ = results_by_strategy["propensity"]
        diff_point = uplift_pt - propensity_pt
        
        # Bootstrap the difference directly
        rng_diff = np.random.RandomState(seed)
        diff_boots = np.empty(B)
        for b in range(B):
            idx = rng_diff.choice(n_test, size=n_test, replace=True)
            y_b, t_b = y_test[idx], t_test[idx]
            uplift_b = uplift_test[idx]
            propensity_b = propensity_test[idx]
            
            k = max(1, int(n_test * pct))
            
            mask_u = _get_top_k_mask(uplift_b, k)
            mask_p = _get_top_k_mask(propensity_b, k)
            
            inc_u = _compute_incremental_per_1000_ipw(y_b, t_b, mask_u, p_treat)
            inc_p = _compute_incremental_per_1000_ipw(y_b, t_b, mask_p, p_treat)
            
            diff_boots[b] = inc_u - inc_p
        
        diff_rows.append({
            "percent_contacted": pct,
            "uplift_minus_propensity": diff_point,
            "ci_low": float(np.percentile(diff_boots, 2.5)),
            "ci_high": float(np.percentile(diff_boots, 97.5)),
        })
    
    # Save outputs
    print("[5/5] Saving outputs...")
    
    targeting_path = out_dir / f"{variant_key}_targeting_simulation_ci.csv"
    pd.DataFrame(targeting_rows).to_csv(targeting_path, index=False)
    print(f"  Saved: {targeting_path.name}")
    
    diff_path = out_dir / f"{variant_key}_uplift_minus_propensity_ci.csv"
    pd.DataFrame(diff_rows).to_csv(diff_path, index=False)
    print(f"  Saved: {diff_path.name}")
    
    policy_path = out_dir / f"{variant_key}_policy_table_ci.csv"
    pd.DataFrame(policy_rows).to_csv(policy_path, index=False)
    print(f"  Saved: {policy_path.name}")
    
    print("\nDone!")
    
    return {
        "targeting_simulation_ci": str(targeting_path),
        "uplift_minus_propensity_ci": str(diff_path),
        "policy_table_ci": str(policy_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Compute bootstrap CIs for targeting simulation")
    parser.add_argument("--variant", type=str, help="Variant key")
    parser.add_argument("--all", action="store_true", help="Run for all variants")
    parser.add_argument("--B", type=int, default=300, help="Number of bootstrap samples")
    parser.add_argument("--seed", type=int, default=123, help="Random seed")
    
    args = parser.parse_args()
    
    if not args.variant and not args.all:
        parser.error("Specify --variant <name> or --all")
    
    if args.all:
        variants_to_run = ALL_VARIANTS
    else:
        variants_to_run = [args.variant]
    
    for variant in variants_to_run:
        try:
            run_bootstrap_ci(variant, B=args.B, seed=args.seed)
        except Exception as e:
            print(f"ERROR for {variant}: {e}")


if __name__ == "__main__":
    main()
