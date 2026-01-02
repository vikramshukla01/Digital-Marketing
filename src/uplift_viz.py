"""
Step 3 Visualization Module.

Generates PNG figures from Step 3 output CSVs.
Does NOT retrain models or modify any outputs.

Usage:
    python -m src.uplift_viz --variant hillstrom_mens_visit
    python -m src.uplift_viz --all
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.paths import outputs_models_dir


# Configuration
FIGURE_SIZE = (10, 6)
DPI = 150
HIST_BINS = 50

# Variants
ALL_VARIANTS = [
    "hillstrom_mens_visit",
    "hillstrom_womens_visit",
    "criteo_conversion",
]


def _figures_dir() -> Path:
    """Get or create Figures directory inside Outputs/Models."""
    fig_dir = outputs_models_dir() / "Figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    return fig_dir


def _load_csv(path: Path, required_cols: List[str] | None = None) -> pd.DataFrame:
    """
    Load CSV and validate required columns.
    
    Raises
    ------
    FileNotFoundError
        If file doesn't exist.
    ValueError
        If required columns are missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    
    df = pd.read_csv(path)
    
    if required_cols:
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns in {path.name}: {missing}\n"
                f"Available columns: {list(df.columns)}"
            )
    
    return df


def _save_figure(fig: plt.Figure, path: Path) -> None:
    """Save figure with tight layout."""
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def plot_targeting_incremental(variant_key: str) -> Path:
    """
    Plot targeting simulation: percent_contacted vs incremental_per_1000.
    
    One line per strategy: uplift_tlearner, propensity, random.
    """
    csv_path = outputs_models_dir() / f"{variant_key}_targeting_simulation.csv"
    df = _load_csv(csv_path)
    
    # Dynamically validate columns
    required = ["strategy", "percent_contacted", "incremental_per_1000"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {csv_path.name}: {missing}. Available: {list(df.columns)}")
    
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    
    # Color and style for each strategy
    styles = {
        "uplift_tlearner": {"color": "#2ecc71", "linestyle": "-", "marker": "o", "label": "Uplift (T-Learner)"},
        "propensity": {"color": "#3498db", "linestyle": "--", "marker": "s", "label": "Propensity P(Y|X)"},
        "random": {"color": "#95a5a6", "linestyle": ":", "marker": "^", "label": "Random"},
    }
    
    for strategy, style in styles.items():
        subset = df[df["strategy"] == strategy].sort_values("percent_contacted")
        if len(subset) > 0:
            ax.plot(
                subset["percent_contacted"] * 100,  # Convert to percentage
                subset["incremental_per_1000"],
                color=style["color"],
                linestyle=style["linestyle"],
                marker=style["marker"],
                markersize=6,
                linewidth=2,
                label=style["label"],
            )
    
    ax.axhline(y=0, color="#bdc3c7", linestyle="-", linewidth=0.8, zorder=0)
    
    ax.set_xlabel("Percent Contacted (%)", fontsize=12)
    ax.set_ylabel("Incremental per 1000 Contacted", fontsize=12)
    ax.set_title(f"Targeting Simulation: {variant_key}", fontsize=14, fontweight="bold")
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    
    out_path = _figures_dir() / f"{variant_key}_targeting_incremental_per_1000.png"
    _save_figure(fig, out_path)
    return out_path


def plot_qini_curve(variant_key: str) -> Path:
    """
    Plot Qini curve: fraction_contacted vs qini.
    """
    csv_path = outputs_models_dir() / f"{variant_key}_qini_curve_points.csv"
    df = _load_csv(csv_path)
    
    # Dynamically validate columns
    required = ["fraction_contacted", "qini"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {csv_path.name}: {missing}. Available: {list(df.columns)}")
    
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    
    # Sort and add origin point for complete curve
    df_sorted = df.sort_values("fraction_contacted")
    x = np.concatenate([[0], df_sorted["fraction_contacted"].values])
    y = np.concatenate([[0], df_sorted["qini"].values])
    
    ax.fill_between(x, y, alpha=0.3, color="#9b59b6")
    ax.plot(x, y, color="#9b59b6", linewidth=2, marker="o", markersize=5)
    
    # Reference line at y=0
    ax.axhline(y=0, color="#e74c3c", linestyle="--", linewidth=1.5, label="y = 0 (random baseline)")
    
    ax.set_xlabel("Fraction Contacted", fontsize=12)
    ax.set_ylabel("Qini (Uplift - Random Baseline)", fontsize=12)
    ax.set_title(f"Qini Curve: {variant_key}", fontsize=14, fontweight="bold")
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    
    out_path = _figures_dir() / f"{variant_key}_qini_curve.png"
    _save_figure(fig, out_path)
    return out_path


def plot_policy_table(variant_key: str) -> Path:
    """
    Plot policy table: percent_contacted vs incremental_per_1000.
    """
    csv_path = outputs_models_dir() / f"{variant_key}_policy_table.csv"
    df = _load_csv(csv_path)
    
    # Dynamically validate columns
    required = ["percent_contacted", "incremental_per_1000"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {csv_path.name}: {missing}. Available: {list(df.columns)}")
    
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    
    df_sorted = df.sort_values("percent_contacted")
    
    ax.plot(
        df_sorted["percent_contacted"] * 100,
        df_sorted["incremental_per_1000"],
        color="#e67e22",
        linewidth=2,
        marker="D",
        markersize=8,
        markerfacecolor="#f39c12",
        markeredgecolor="#d35400",
    )
    
    ax.axhline(y=0, color="#bdc3c7", linestyle="-", linewidth=0.8, zorder=0)
    
    ax.set_xlabel("Percent Contacted (%)", fontsize=12)
    ax.set_ylabel("Incremental per 1000 Contacted", fontsize=12)
    ax.set_title(f"Policy Table: {variant_key}", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    
    out_path = _figures_dir() / f"{variant_key}_policy_incremental_per_1000.png"
    _save_figure(fig, out_path)
    return out_path


def plot_uplift_score_histogram(variant_key: str) -> Path:
    """
    Plot histogram of uplift scores on test set.
    """
    csv_path = outputs_models_dir() / f"{variant_key}_uplift_scores_tlearner.csv"
    df = _load_csv(csv_path)
    
    # Dynamically validate columns
    if "uplift_score" not in df.columns:
        raise ValueError(f"Missing 'uplift_score' column in {csv_path.name}. Available: {list(df.columns)}")
    
    # Filter to test split if column exists
    if "split" in df.columns:
        df = df[df["split"] == "test"]
        subset_label = " (Test Set)"
    else:
        subset_label = ""
    
    if len(df) == 0:
        raise ValueError(f"No test rows found in {csv_path.name}")
    
    fig, ax = plt.subplots(figsize=FIGURE_SIZE)
    
    scores = df["uplift_score"].values
    
    ax.hist(
        scores,
        bins=HIST_BINS,
        color="#1abc9c",
        edgecolor="#16a085",
        alpha=0.8,
    )
    
    # Vertical line at 0
    ax.axvline(x=0, color="#e74c3c", linestyle="--", linewidth=2, label="Uplift = 0")
    
    # Statistics annotation
    mean_uplift = np.mean(scores)
    median_uplift = np.median(scores)
    pct_positive = 100 * np.mean(scores > 0)
    
    stats_text = f"Mean: {mean_uplift:.4f}\nMedian: {median_uplift:.4f}\n% Positive: {pct_positive:.1f}%"
    ax.text(
        0.95, 0.95, stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )
    
    ax.set_xlabel("Uplift Score (p1 - p0)", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title(f"Uplift Score Distribution: {variant_key}{subset_label}", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")
    
    out_path = _figures_dir() / f"{variant_key}_uplift_score_hist_test.png"
    _save_figure(fig, out_path)
    return out_path


def generate_all_figures(variant_key: str) -> List[Path]:
    """
    Generate all 4 figures for a variant.
    
    Returns list of saved file paths.
    """
    print(f"\nGenerating figures for: {variant_key}")
    print("-" * 40)
    
    paths = []
    
    try:
        paths.append(plot_targeting_incremental(variant_key))
    except (FileNotFoundError, ValueError) as e:
        print(f"  SKIP targeting_incremental: {e}")
    
    try:
        paths.append(plot_qini_curve(variant_key))
    except (FileNotFoundError, ValueError) as e:
        print(f"  SKIP qini_curve: {e}")
    
    try:
        paths.append(plot_policy_table(variant_key))
    except (FileNotFoundError, ValueError) as e:
        print(f"  SKIP policy_table: {e}")
    
    try:
        paths.append(plot_uplift_score_histogram(variant_key))
    except (FileNotFoundError, ValueError) as e:
        print(f"  SKIP uplift_score_hist: {e}")
    
    return paths


def main():
    parser = argparse.ArgumentParser(description="Generate uplift visualization figures")
    parser.add_argument("--variant", type=str, help="Variant key to visualize")
    parser.add_argument("--all", action="store_true", help="Generate for all variants")
    
    args = parser.parse_args()
    
    if not args.variant and not args.all:
        parser.error("Specify --variant <name> or --all")
    
    print("=" * 50)
    print("UPLIFT VISUALIZATION")
    print("=" * 50)
    print(f"Output directory: {_figures_dir()}")
    
    if args.all:
        variants_to_run = ALL_VARIANTS
    else:
        variants_to_run = [args.variant]
    
    all_paths = []
    for variant in variants_to_run:
        paths = generate_all_figures(variant)
        all_paths.extend(paths)
    
    print("\n" + "=" * 50)
    print(f"Generated {len(all_paths)} figures")
    print("=" * 50)


if __name__ == "__main__":
    main()
