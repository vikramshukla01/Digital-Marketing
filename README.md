# Digital Marketing Uplift Pipeline

## Project Overview

Marketing teams face a fundamental resource constraint: they cannot contact everyone. When budgets are limited, the question becomes *who* to target—not just who is likely to respond, but who will respond *because* of the outreach. This project implements an end-to-end pipeline for evaluating targeting policies using real experimental data. It compares random, propensity-based, and uplift-based targeting strategies to measure actual incremental impact. The goal is decision quality, not prediction accuracy. The project demonstrates a core applied skill: making defensible decisions under uncertainty when resources are constrained.

---

## Why This Project Exists

Most marketing analytics focuses on predicting response likelihood: *"Which customers are most likely to convert?"* This sounds reasonable but misses a critical point. Many high-likelihood customers would convert regardless of whether they receive a message. Targeting them wastes budget on outcomes that would have happened anyway—money spent for zero incremental return.

This project takes a different approach. Instead of predicting who will convert, it estimates who will convert *because of* the intervention. This distinction—between prediction and optimisation—is the difference between forecasting behaviour and improving decisions.

---

## Datasets Used

This project evaluates targeting strategies on two publicly available experimental datasets:

**Hillstrom Email Campaign**  
A controlled email marketing experiment with three conditions: Men's promotional email, Women's promotional email, and a holdout control group. The outcome is website visit. This dataset has clear treatment structure and moderate sample size, making it suitable for uplift analysis.

**Criteo Advertising Exposure**  
A large-scale randomised advertising experiment with binary treatment (ad shown vs. not shown) and conversion as the outcome. Effects are small by design, reflecting realistic advertising conditions. This dataset tests whether methods remain stable when incremental effects are marginal.

Using multiple datasets matters. A method that works on one experiment may fail on another. Robustness across datasets provides more credible evidence than strong performance on a single benchmark.

---

## What Was Evaluated

This project compares three targeting policies under budget constraints:

**Random Targeting**  
Customers are selected at random. This establishes a baseline: how much incremental value does any targeting provide over no targeting at all?

**Propensity-Based Targeting**  
Customers are ranked by predicted probability of conversion, regardless of treatment. This represents the conventional approach: target those most likely to respond.

**Uplift-Based Targeting**  
Customers are ranked by estimated treatment effect—the predicted difference in conversion probability with versus without the intervention. This prioritises customers who are persuadable, not merely responsive.

The evaluation asks: at a fixed budget (e.g., contact the top 10%), which policy produces more incremental conversions? This is a policy comparison, not a model comparison. The focus is on downstream decisions, not upstream predictions. Policy simplicity was a deliberate constraint—these three strategies mirror what most marketing teams would realistically consider.

---

## Key Findings

- Uplift-based targeting outperformed propensity-based targeting in the Hillstrom Women's Email experiment across most budget levels.
- In the Hillstrom Men's Email experiment, differences between uplift and propensity targeting were smaller and less consistent.
- In the Criteo dataset, all strategies produced similar results. Incremental effects were small, and no method showed a reliable advantage.
- Bootstrap confidence intervals revealed that many observed differences were within the range of sampling variability.
- These results reinforce that uplift modelling is not universally superior. Its value depends on the presence of heterogeneous treatment effects and the ability of the model to detect them.

**Rule of thumb:** Uplift-based targeting helps most when customer responses to treatment vary widely—some are persuadable, others are not. When effects are uniform or very small, likelihood-based targeting is often sufficient and simpler to implement. Budget size also matters: at very high contact rates, strategy differences shrink because most customers are reached regardless of ranking.

---

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| `src/` | Core pipeline logic. Handles data loading, splitting, modelling, evaluation, and visualisation. |
| `Data/Processed/` | Cached dataset snapshots. Frozen after initial processing to ensure reproducibility. |
| `Outputs/EDA/` | Exploratory data analysis tables. Treatment distributions, covariate balance, and missingness summaries. |
| `Outputs/Models/` | All Step 3 outputs. Scores, targeting simulations, policy tables, curve points, and metrics. |
| `Outputs/Models/Figures/` | Visualisations. Targeting curves, Qini plots, and score distributions. |

---

## Reproducibility and Integrity

This project is designed for full reproducibility:

- **Deterministic splits**: Train/validation/test assignments are computed once and saved. Rerunning the pipeline produces identical partitions.
- **Cached datasets**: Processed data snapshots are stored with integrity hashes. If the underlying data changes, the pipeline refuses to proceed until splits are regenerated.
- **Fixed random seeds**: All stochastic operations (splitting, bootstrap sampling) use explicit seeds.
- **Bootstrap uncertainty**: Confidence intervals are computed for all policy comparisons. Results are reported with uncertainty, not as point estimates alone.

These safeguards exist because silent changes to data or splits can invalidate results without anyone noticing. The integrity guards make reproducibility failures loud and immediate rather than hidden and dangerous.

---

## Who This Project Is For

This project is relevant to:

- **Data scientists** evaluating causal inference methods for marketing applications.
- **Marketing analysts** exploring alternatives to response-based targeting.
- **Decision scientists** interested in policy evaluation under budget constraints.
- **Growth and experimentation teams** building internal uplift capabilities.

The pipeline is structured for extension: additional datasets, learners, or evaluation metrics can be integrated without restructuring the core workflow.
