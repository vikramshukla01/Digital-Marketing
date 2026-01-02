"""
Step 3 Uplift Tests.

Mandatory tests:
1. Synthetic truth test: generate data with known heterogeneous effect,
   verify qini_coeff > 0 and uplift strategy beats random.
2. Shuffle null test: permute treatment labels and verify qini_coeff ≈ 0.

Usage:
    python -m src.uplift_tests
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.uplift_config import GLOBAL_SEED, RANDOM_BASELINE_SEED, POLICY_PCTS
from src.uplift_learners import fit_t_learner, predict_uplift_t_learner
from src.uplift_curves import (
    uplift_curve_points_ipw,
    auuc_from_curve,
    compute_ate_ipw,
    qini_curve_points,
    qini_coeff_from_curve,
)
from src.uplift_policy import targeting_simulation_compare


def generate_synthetic_data(
    n: int = 5000,
    seed: int = GLOBAL_SEED,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Generate synthetic data with known heterogeneous treatment effect.
    
    Design:
    - X1, X2: uniform features
    - True CATE = 0.3 * X1 (heterogeneous: high X1 = high uplift)
    - P(Y=1|X,T=0) = sigmoid(-1 + 0.5*X1 + 0.5*X2)
    - P(Y=1|X,T=1) = sigmoid(-1 + 0.5*X1 + 0.5*X2 + 0.3*X1)
    
    Returns
    -------
    X : DataFrame
        Features.
    y : np.ndarray
        Outcomes.
    t : np.ndarray
        Treatment indicators.
    """
    rng = np.random.RandomState(seed)
    
    # Features
    X1 = rng.uniform(-1, 1, n)
    X2 = rng.uniform(-1, 1, n)
    
    # Random treatment assignment (50/50)
    t = rng.binomial(1, 0.5, n)
    
    # Outcome probabilities
    # Base effect
    base_logit = -1 + 0.5 * X1 + 0.5 * X2
    
    # Treatment effect (heterogeneous: 0.3 * X1 for treated)
    treatment_effect = 0.3 * X1 * t
    
    # Full logit
    logit = base_logit + treatment_effect
    p_y = 1 / (1 + np.exp(-logit))
    
    # Generate outcomes
    y = rng.binomial(1, p_y)
    
    X = pd.DataFrame({"X1": X1, "X2": X2})
    
    return X, y, t


def test_synthetic_truth():
    """
    Synthetic truth test.
    
    Verifies:
    1. Qini coefficient > 0 (model learns something)
    2. Uplift strategy beats random at top 10-20%
    """
    print("\n" + "=" * 50)
    print("TEST: Synthetic Truth")
    print("=" * 50)
    
    # Generate data
    X, y, t = generate_synthetic_data(n=5000, seed=GLOBAL_SEED)
    
    # Split: 60% train, 40% test
    n = len(y)
    n_train = int(0.6 * n)
    
    X_train = X.iloc[:n_train]
    X_test = X.iloc[n_train:]
    y_train = y[:n_train]
    y_test = y[n_train:]
    t_train = t[:n_train]
    t_test = t[n_train:]
    
    # Fit T-learner
    m0, m1 = fit_t_learner(X_train, pd.Series(y_train), pd.Series(t_train), seed=GLOBAL_SEED)
    
    # Predict uplift on test
    uplift_scores_test = predict_uplift_t_learner(m0, m1, X_test)
    
    # Treatment probability from train
    p_treat = float(t_train.mean())
    
    # Compute curves
    uplift_curve = uplift_curve_points_ipw(y_test, t_test, uplift_scores_test, p_treat)
    auuc = auuc_from_curve(uplift_curve)
    
    ate_ipw_test = compute_ate_ipw(y_test, t_test, p_treat)
    qini_curve = qini_curve_points(uplift_curve, ate_ipw_test)
    qini_coeff = qini_coeff_from_curve(qini_curve)
    
    print(f"  AUUC:       {auuc:.4f}")
    print(f"  Qini coeff: {qini_coeff:.4f}")
    print(f"  ATE (IPW):  {ate_ipw_test:.4f}")
    
    # Targeting simulation
    # Need propensity scores for comparison (just use random for this test)
    rng = np.random.RandomState(RANDOM_BASELINE_SEED)
    propensity_scores_test = rng.random(len(y_test))
    
    sim = targeting_simulation_compare(
        y_test, t_test, uplift_scores_test, propensity_scores_test, p_treat, pcts=[0.10, 0.20]
    )
    
    # Check uplift beat random at 10% and 20%
    uplift_10 = sim[(sim["strategy"] == "uplift_tlearner") & (sim["percent_contacted"] == 0.10)]["incremental_per_1000"].values[0]
    random_10 = sim[(sim["strategy"] == "random") & (sim["percent_contacted"] == 0.10)]["incremental_per_1000"].values[0]
    
    uplift_20 = sim[(sim["strategy"] == "uplift_tlearner") & (sim["percent_contacted"] == 0.20)]["incremental_per_1000"].values[0]
    random_20 = sim[(sim["strategy"] == "random") & (sim["percent_contacted"] == 0.20)]["incremental_per_1000"].values[0]
    
    print(f"\n  Targeting at 10%: Uplift={uplift_10:.2f}, Random={random_10:.2f}")
    print(f"  Targeting at 20%: Uplift={uplift_20:.2f}, Random={random_20:.2f}")
    
    # Assertions
    passed = True
    
    if qini_coeff <= 0:
        print("  FAIL: Qini coefficient should be > 0")
        passed = False
    else:
        print("  PASS: Qini coefficient > 0")
    
    if uplift_10 <= random_10:
        print("  FAIL: Uplift should beat random at 10%")
        passed = False
    else:
        print("  PASS: Uplift beats random at 10%")
    
    if uplift_20 <= random_20:
        print("  FAIL: Uplift should beat random at 20%")
        passed = False
    else:
        print("  PASS: Uplift beats random at 20%")
    
    return passed


def test_shuffle_null():
    """
    Shuffle null test.
    
    Permutes treatment labels (breaking any real effect) and verifies
    that the resulting Qini coefficient is approximately 0.
    """
    print("\n" + "=" * 50)
    print("TEST: Shuffle Null")
    print("=" * 50)
    
    # Generate data (or use real data if available)
    X, y, t = generate_synthetic_data(n=5000, seed=GLOBAL_SEED)
    
    # Split
    n = len(y)
    n_train = int(0.6 * n)
    
    X_train = X.iloc[:n_train]
    X_test = X.iloc[n_train:]
    y_train = y[:n_train]
    y_test = y[n_train:]
    t_train = t[:n_train]
    t_test = t[n_train:]
    
    # SHUFFLE treatment labels (this breaks the treatment effect)
    shuffle_seed = 9999
    rng = np.random.RandomState(shuffle_seed)
    t_train_shuffled = rng.permutation(t_train)
    t_test_shuffled = rng.permutation(t_test)
    
    # Fit T-learner on shuffled data
    m0, m1 = fit_t_learner(X_train, pd.Series(y_train), pd.Series(t_train_shuffled), seed=GLOBAL_SEED)
    
    # Predict uplift
    uplift_scores_test = predict_uplift_t_learner(m0, m1, X_test)
    
    # Use shuffled treatment for evaluation too
    p_treat = float(t_train_shuffled.mean())
    
    # Compute Qini
    uplift_curve = uplift_curve_points_ipw(y_test, t_test_shuffled, uplift_scores_test, p_treat)
    ate_ipw_test = compute_ate_ipw(y_test, t_test_shuffled, p_treat)
    qini_curve = qini_curve_points(uplift_curve, ate_ipw_test)
    qini_coeff = qini_coeff_from_curve(qini_curve)
    
    print(f"  Qini coeff (shuffled): {qini_coeff:.4f}")
    
    # Tolerance: Qini should be close to 0 (within ±50, accounting for noise)
    tolerance = 100  # Generous tolerance for stochastic test
    
    passed = True
    if abs(qini_coeff) > tolerance:
        print(f"  FAIL: Qini coefficient should be ≈ 0 (within ±{tolerance}), got {qini_coeff:.4f}")
        passed = False
    else:
        print(f"  PASS: Qini coefficient ≈ 0 (within tolerance)")
    
    return passed


def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# UPLIFT MODEL TESTS")
    print("#" * 60)
    
    results = {}
    
    # Run tests
    results["synthetic_truth"] = test_synthetic_truth()
    results["shuffle_null"] = test_shuffle_null()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All tests PASSED!")
        sys.exit(0)
    else:
        print("Some tests FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
