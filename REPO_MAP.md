# Repository Map

This document explains how the repository is organised and how the pieces fit together. It is intended for technical reviewers who want to understand the structure without reading source files.

---

## Pipeline Stages

The project follows a linear pipeline with six stages. Each stage mitigates a specific decision risk.

### Stage 1: Data Ingestion

Raw datasets are loaded from external sources or local files. Each dataset is standardised into a common format: features, outcome, and treatment indicator. Processed snapshots are cached to ensure consistency across runs.

For Hillstrom, the full dataset is fetched once and saved locally. For Criteo, a deterministic 10% sample is created using hash-based row selection to keep experiments lightweight while maintaining reproducibility.

**Risk mitigated:** Prevents silent data drift. Without caching, re-fetching could introduce version changes that invalidate downstream results.

### Stage 2: Exploratory Data Analysis

Before modelling, the data is examined for quality and structure. This stage produces summary tables showing:

- Treatment group sizes and distributions
- Outcome rates by treatment arm
- Covariate balance between treatment and control (measured by standardised mean difference)
- Missingness patterns

These tables are saved to `Outputs/EDA/` and are designed to be included directly in reports.

**Risk mitigated:** Catches data quality issues early. Imbalanced groups or unexpected missingness can invalidate causal claims.

### Stage 3: Splitting

Data is divided into train, validation, and test sets using stratified sampling. The stratification preserves the joint distribution of treatment and outcome across splits.

Split assignments are saved as a separate file. If the split file exists, it is reused. This ensures that repeated runs of the pipeline use identical partitions.

An integrity guard compares the current data snapshot hash against the hash stored when splits were created. If they differ, the pipeline halts with an error to prevent silent misalignment.

**Risk mitigated:** Prevents train/test leakage and accidental re-randomisation. Both can produce misleadingly optimistic results.

### Stage 4: Modelling

Two types of models are trained on the training set:

**Baseline Propensity Model**  
Predicts the probability of the outcome given features, ignoring treatment. This represents conventional response modelling.

**T-Learner Uplift Model**  
Trains separate models for treated and control groups. Uplift is estimated as the difference in predicted probabilities: P(outcome | treated) minus P(outcome | control).

Both models use logistic regression with default hyperparameters. The focus is on evaluation methodology, not model performance.

**Risk mitigated:** Overfitting. Simple models with no hyperparameter tuning are less likely to exploit noise in the training data.

### Stage 5: Evaluation

Models are evaluated on the held-out test set using the Horvitz–Thompson inverse probability weighting (IPW) estimator. This estimator computes the incremental effect of targeting a subset of customers.

The evaluation compares three targeting policies:

- **Random**: Customers selected at random
- **Propensity**: Customers ranked by predicted response probability
- **Uplift**: Customers ranked by predicted treatment effect

For each policy, the pipeline computes incremental conversions per 1,000 contacts at multiple budget levels (1%, 5%, 10%, 20%, 30%, 50%).

**Risk mitigated:** Misaligned metrics. Accuracy or AUC do not measure policy value. This stage reports what actually matters for targeting decisions.

### Stage 6: Visualisation

Charts are generated from the evaluation outputs:

- Targeting curves: incremental value by strategy across budget levels
- Qini curves: cumulative uplift relative to random baseline
- Score distributions: histogram of uplift scores on the test set

All figures are saved as PNG files.

**Risk mitigated:** Misinterpretation. Visual comparisons are harder to over-interpret than raw numbers.

---

## Key Design Principles

### Determinism

Every random operation uses an explicit seed. Splits are saved and reused. Results are identical across runs on the same data.

### Separation of Concerns

Each module has a single responsibility:

- Data loading is separate from modelling
- Splitting is separate from evaluation
- Visualisation reads from saved outputs, not from in-memory objects

This makes the pipeline easier to debug, extend, and audit.

### Policy-First Evaluation

The pipeline does not report model accuracy or AUC on outcome prediction. These metrics are irrelevant for uplift. Instead, it reports policy value: how many incremental conversions would a strategy produce under budget constraints?

This framing aligns evaluation with the actual business decision.

### Reproducibility

All outputs can be regenerated from the same inputs. Cached data includes metadata (hash, creation timestamp). If inputs change, the system detects it.

### Deliberate Simplicity

This repository deliberately avoids a "model zoo" approach. There is one uplift learner, one baseline, and one evaluation framework. This is a conscious design choice: robustness and interpretability are prioritised over leaderboard performance. A model that looks good but can't be trusted is worse than a simple model that can be audited.

---

## Outputs Explained

All Step 3 outputs are saved to `Outputs/Models/`. Each file serves a specific purpose.

**If you're short on time, start with `targeting_simulation.csv`.** It directly compares all three strategies and answers the core question: which policy wins at each budget level?

### Split Indices

**File pattern:** `<variant>_split_indices.csv`

Contains row identifiers and their assigned split (train, valid, test). Used to ensure consistent partitioning.

### Uplift Scores

**File pattern:** `<variant>_uplift_scores_tlearner.csv`

Contains the estimated treatment effect for each customer. Higher scores indicate customers predicted to be more persuadable.

### Baseline Propensity Scores

**File pattern:** `<variant>_baseline_propensity_scores.csv`

Contains predicted probability of conversion for each customer, ignoring treatment. Used for propensity-based targeting.

### Targeting Simulation

**File pattern:** `<variant>_targeting_simulation.csv`

Compares all three strategies at each budget level. Shows incremental conversions per 1,000 contacts. This is the primary policy comparison table.

### Policy Table

**File pattern:** `<variant>_policy_table.csv`

Shows incremental value at each budget level for uplift targeting only. Designed for business reporting.

### Uplift Curve Points

**File pattern:** `<variant>_uplift_curve_points.csv`

Cumulative incremental conversions as a function of fraction contacted. Used to plot targeting curves.

### Qini Curve Points

**File pattern:** `<variant>_qini_curve_points.csv`

Qini values at each fraction contacted. Qini is defined as model uplift minus random baseline. The Qini coefficient (area under the curve) summarises overall model quality.

### Summary Metrics

**File pattern:** `<variant>_summary_metrics.csv`

Single-row table with key metrics: sample sizes, treatment rates, ATE, AUUC, and Qini coefficient.

### Bootstrap Confidence Intervals

**File patterns:**
- `<variant>_targeting_simulation_ci.csv`
- `<variant>_uplift_minus_propensity_ci.csv`
- `<variant>_policy_table_ci.csv`

Point estimates with 95% confidence intervals computed via bootstrap resampling. These files quantify uncertainty in the policy comparisons.

### Figures

**Location:** `Outputs/Models/Figures/`

PNG images:
- Targeting curves (all strategies)
- Qini curves
- Policy incremental bar charts
- Uplift score histograms

---

## Why This Is Not a "Model Zoo"

This repository does not chase model performance.

There is one uplift learner (T-Learner with logistic regression). There is no hyperparameter tuning, no model selection, no ensemble stacking.

This is intentional.

The purpose of this project is to demonstrate a methodology for evaluating targeting policies, not to claim state-of-the-art uplift prediction. The learner is simple because the evaluation framework is the contribution.

A more complex model might produce better scores. But without the evaluation infrastructure—stratified splits, IPW estimation, bootstrap uncertainty, policy simulation—those scores would be meaningless. Complexity without rigour is noise.

The pipeline is designed so that additional learners can be added later. The evaluation framework will work the same way regardless of what model produces the scores.
