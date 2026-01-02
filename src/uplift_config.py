"""
Step 3 Uplift Pipeline Configuration.

All global constants and hyperparameters are defined here for reproducibility.
"""
from __future__ import annotations

# ============================================================
# RANDOM SEEDS
# ============================================================
GLOBAL_SEED = 42  # Used for splits, model training, etc.
RANDOM_BASELINE_SEED = 123  # Used for random targeting baseline

# ============================================================
# TRAIN/VALID/TEST SPLIT FRACTIONS
# ============================================================
# Split scheme: stratified by joint (treatment, outcome) label
# Order: train first, then valid, then test
TRAIN_FRAC = 0.6  # 60% training
VALID_FRAC = 0.2  # 20% validation
TEST_FRAC = 0.2   # 20% test (1 - TRAIN_FRAC - VALID_FRAC)

# ============================================================
# EVALUATION CONFIGURATION
# ============================================================
N_BINS = 10  # Number of bins for uplift/Qini curve points

# Policy table: percentages of population to contact
POLICY_PCTS = [0.01, 0.05, 0.10, 0.20, 0.30, 0.50]

# ============================================================
# MODEL DEFAULTS
# ============================================================
# Using Logistic Regression as stable default (no deep tuning)
MODEL_FAMILY = "logistic_regression"
MODEL_MAX_ITER = 1000
MODEL_C = 1.0  # Regularization strength (inverse)
