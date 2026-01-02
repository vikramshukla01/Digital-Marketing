"""
Step 3 CLI Orchestrator.

Run the complete uplift pipeline for a dataset variant.

Usage:
    python -m src.uplift_run --dataset hillstrom --target visit --arm "Mens E-Mail"
    python -m src.uplift_run --dataset hillstrom --target visit --arm "Womens E-Mail"
    python -m src.uplift_run --dataset criteo --target conversion
"""
from __future__ import annotations

import argparse
from typing import Optional

import numpy as np
import pandas as pd

from src.uplift_config import GLOBAL_SEED, POLICY_PCTS
from src.uplift_dataset_adapters import get_dataset_variant
from src.uplift_splits import make_row_id, make_or_load_splits, get_split_masks
from src.uplift_features import fit_transform_train, transform, assert_no_leakage
from src.uplift_baselines import (
    fit_response_propensity_model,
    predict_response_propensity,
    save_propensity_scores,
)
from src.uplift_learners import (
    fit_t_learner,
    predict_uplift_t_learner,
    save_uplift_scores,
)
from src.uplift_policy import (
    policy_table_from_scores,
    targeting_simulation_compare,
    save_policy_table,
    save_targeting_simulation,
)
from src.uplift_curves import (
    uplift_curve_points_ipw,
    auuc_from_curve,
    compute_ate_ipw,
    qini_curve_points,
    qini_coeff_from_curve,
    save_uplift_curve,
    save_qini_curve,
    save_summary_metrics,
)
from src.paths import outputs_models_dir


def run_pipeline(
    dataset: str,
    target: str,
    arm: Optional[str] = None,
) -> dict:
    """
    Run the complete uplift pipeline for a dataset variant.
    
    Parameters
    ----------
    dataset : str
        Dataset name ('hillstrom' or 'criteo').
    target : str
        Target column name.
    arm : str, optional
        For Hillstrom, which arm to evaluate.
    
    Returns
    -------
    dict
        Summary of outputs and metrics.
    """
    print("=" * 60)
    print(f"UPLIFT PIPELINE: {dataset} / {target}" + (f" / {arm}" if arm else ""))
    print("=" * 60)
    
    # ========================================
    # Step 1: Load dataset variant
    # ========================================
    print("\n[1/7] Loading dataset...")
    variant = get_dataset_variant(dataset, target, arm)
    variant_key = variant["variant_key"]
    X_raw = variant["X_raw"]
    y = variant["y"]
    t = variant["t"]
    snapshot_hash = variant["snapshot_hash"]
    
    print(f"  Variant key: {variant_key}")
    print(f"  Shape: {X_raw.shape}")
    print(f"  Treatment: {variant['treatment_name']}")
    print(f"  Outcome: {variant['outcome_name']}")
    print(f"  Treatment rate: {t.mean():.4f}")
    print(f"  Outcome rate: {y.mean():.4f}")
    
    # ========================================
    # Step 2: Create row IDs and splits
    # ========================================
    print("\n[2/7] Creating/loading splits...")
    row_id = make_row_id(X_raw)
    split_df = make_or_load_splits(variant_key, row_id, y, t, snapshot_hash)
    
    train_mask, valid_mask, test_mask = get_split_masks(row_id, split_df)
    
    print(f"  Train: {train_mask.sum()}")
    print(f"  Valid: {valid_mask.sum()}")
    print(f"  Test:  {test_mask.sum()}")
    
    # Prepare split labels for all rows
    id_to_split = dict(zip(split_df["row_id"], split_df["split"]))
    split_labels = row_id.map(id_to_split)
    
    # ========================================
    # Step 3: Feature encoding
    # ========================================
    print("\n[3/7] Encoding features...")
    X_train_raw = X_raw[train_mask]
    X_train, encoder_artifact = fit_transform_train(X_train_raw, variant_key)
    
    X_valid = transform(X_raw[valid_mask], encoder_artifact)
    X_test = transform(X_raw[test_mask], encoder_artifact)
    X_all = transform(X_raw, encoder_artifact)
    
    # Verify no leakage
    assert_no_leakage(X_all, variant["outcome_name"], "treatment")
    print(f"  Encoded features: {X_train.shape[1]}")
    
    # Get train/valid/test y, t arrays
    y_train = y[train_mask].values
    y_valid = y[valid_mask].values
    y_test = y[test_mask].values
    
    t_train = t[train_mask].values
    t_valid = t[valid_mask].values
    t_test = t[test_mask].values
    
    # ========================================
    # Step 4: Baseline propensity model
    # ========================================
    print("\n[4/7] Training baseline propensity model P(Y|X)...")
    propensity_model = fit_response_propensity_model(X_train, y_train, seed=GLOBAL_SEED)
    propensity_scores_all = predict_response_propensity(propensity_model, X_all)
    
    propensity_path = save_propensity_scores(row_id, split_labels, propensity_scores_all, variant_key)
    print(f"  Saved: {propensity_path.name}")
    
    # ========================================
    # Step 5: T-Learner uplift model
    # ========================================
    print("\n[5/7] Training T-Learner...")
    m0, m1 = fit_t_learner(X_train, pd.Series(y_train), pd.Series(t_train), seed=GLOBAL_SEED)
    uplift_scores_all = predict_uplift_t_learner(m0, m1, X_all)
    
    uplift_path = save_uplift_scores(row_id, split_labels, uplift_scores_all, variant_key)
    print(f"  Saved: {uplift_path.name}")
    
    # Get test-set scores
    uplift_scores_test = predict_uplift_t_learner(m0, m1, X_test)
    propensity_scores_test = predict_response_propensity(propensity_model, X_test)
    
    # ========================================
    # Step 6: Curves and metrics
    # ========================================
    print("\n[6/7] Computing curves and metrics...")
    
    # Treatment probability = mean(T) from TRAIN (as per spec)
    p_treat = float(t_train.mean())
    print(f"  p_treat (from train): {p_treat:.4f}")
    
    # ATE on test set
    ate_ipw_test = compute_ate_ipw(y_test, t_test, p_treat)
    print(f"  ATE (IPW, test): {ate_ipw_test:.6f}")
    
    # Uplift curve
    uplift_curve = uplift_curve_points_ipw(y_test, t_test, uplift_scores_test, p_treat)
    auuc = auuc_from_curve(uplift_curve)
    print(f"  AUUC: {auuc:.4f}")
    
    uplift_curve_path = save_uplift_curve(uplift_curve, variant_key)
    print(f"  Saved: {uplift_curve_path.name}")
    
    # Qini curve
    qini_curve = qini_curve_points(uplift_curve, ate_ipw_test)
    qini_coeff = qini_coeff_from_curve(qini_curve)
    print(f"  Qini coefficient: {qini_coeff:.4f}")
    
    qini_curve_path = save_qini_curve(qini_curve, variant_key)
    print(f"  Saved: {qini_curve_path.name}")
    
    # Summary metrics
    metrics = {
        "variant_key": variant_key,
        "n_train": int(train_mask.sum()),
        "n_valid": int(valid_mask.sum()),
        "n_test": int(test_mask.sum()),
        "p_treat_train": p_treat,
        "outcome_rate_train": float(y_train.mean()),
        "ate_ipw_test": ate_ipw_test,
        "auuc": auuc,
        "qini_coeff": qini_coeff,
    }
    metrics_path = save_summary_metrics(metrics, variant_key)
    print(f"  Saved: {metrics_path.name}")
    
    # ========================================
    # Step 7: Policy table and targeting simulation
    # ========================================
    print("\n[7/7] Policy evaluation and targeting simulation...")
    
    # Policy table for uplift scores
    policy_table = policy_table_from_scores(
        row_id=np.arange(len(y_test)),
        y_test=y_test,
        t_test=t_test,
        score=uplift_scores_test,
        p_treat=p_treat,
        pcts=POLICY_PCTS,
    )
    policy_path = save_policy_table(policy_table, variant_key)
    print(f"  Saved: {policy_path.name}")
    
    # Targeting simulation
    targeting_sim = targeting_simulation_compare(
        y_test=y_test,
        t_test=t_test,
        uplift_score=uplift_scores_test,
        propensity_score=propensity_scores_test,
        p_treat=p_treat,
        pcts=POLICY_PCTS,
    )
    targeting_path = save_targeting_simulation(targeting_sim, variant_key)
    print(f"  Saved: {targeting_path.name}")
    
    # ========================================
    # Done
    # ========================================
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nOutputs saved to: {outputs_models_dir()}")
    print(f"\nKey metrics:")
    print(f"  AUUC:           {auuc:.4f}")
    print(f"  Qini coeff:     {qini_coeff:.4f}")
    print(f"  ATE (IPW test): {ate_ipw_test:.6f}")
    
    return {
        "variant_key": variant_key,
        "metrics": metrics,
        "output_dir": str(outputs_models_dir()),
    }


def main():
    parser = argparse.ArgumentParser(description="Run uplift modeling pipeline")
    parser.add_argument("--dataset", required=True, choices=["hillstrom", "criteo"],
                        help="Dataset to use")
    parser.add_argument("--target", required=True,
                        help="Target column (e.g., 'visit', 'conversion')")
    parser.add_argument("--arm", default=None,
                        help="For Hillstrom: 'Mens E-Mail' or 'Womens E-Mail'")
    
    args = parser.parse_args()
    
    # Validate Hillstrom requires arm
    if args.dataset == "hillstrom" and args.arm is None:
        parser.error("--arm is required for Hillstrom dataset")
    
    run_pipeline(
        dataset=args.dataset,
        target=args.target,
        arm=args.arm,
    )


if __name__ == "__main__":
    main()
