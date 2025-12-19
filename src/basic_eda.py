from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.data_loading import (
    load_kaggle_customer_profile,
    load_hillstrom,
    load_criteo,
)


def _project_root() -> Path:
    # Assumes this file lives in <root>/src/basic_eda.py
    return Path(__file__).resolve().parents[1]


def _processed_dir() -> Path:
    out_dir = _project_root() / "Data" / "Processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _print_kv(label: str, value) -> None:
    print(f"{label}: {value}")


def _print_dist_table(name: str, dist_df: pd.DataFrame, key_col: str) -> None:
    """
    Pretty-print a distribution table with controlled decimals and no index.
    Formats pct columns to 4 decimals and mean/rate columns to 6 decimals.
    """
    print(f"\n--- {name} ---")
    display = dist_df.copy()
    for col in display.columns:
        if col == "pct":
            display[col] = display[col].astype(float).map(lambda x: f"{x:.4f}")
        elif "mean" in col or "rate" in col:
            display[col] = display[col].astype(float).map(lambda x: f"{x:.6f}")
    print(display.to_string(index=False))


def _clean_label_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip()


def _format_label(val) -> str:
    try:
        fval = float(val)
        if fval.is_integer():
            return str(int(fval))
    except Exception:
        pass
    return str(val)


def _missingness_table(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    records = []
    for col in df.columns:
        missing = int(df[col].isna().sum())
        pct = float(missing / total) if total else 0.0
        records.append(
            {
                "column": col,
                "dtype": str(df[col].dtype),
                "missing_count": missing,
                "missing_pct": pct,
            }
        )
    return pd.DataFrame.from_records(records)


def _robust_numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    num_df = df.select_dtypes(include="number")
    records = []
    total = len(num_df)
    quantiles = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    for col in num_df.columns:
        s = num_df[col]
        non_null = s.dropna()
        count = int(non_null.shape[0])
        missing = int(total - count)
        if count == 0:
            records.append(
                {
                    "column": col,
                    "count": count,
                    "missing_count": missing,
                    "min": None,
                    "p01": None,
                    "p05": None,
                    "p25": None,
                    "median": None,
                    "p75": None,
                    "p95": None,
                    "p99": None,
                    "max": None,
                    "iqr": None,
                }
            )
            continue
        q = non_null.quantile(quantiles)
        p25 = float(q.loc[0.25])
        p75 = float(q.loc[0.75])
        records.append(
            {
                "column": col,
                "count": count,
                "missing_count": missing,
                "min": float(non_null.min()),
                "p01": float(q.loc[0.01]),
                "p05": float(q.loc[0.05]),
                "p25": p25,
                "median": float(q.loc[0.5]),
                "p75": p75,
                "p95": float(q.loc[0.95]),
                "p99": float(q.loc[0.99]),
                "max": float(non_null.max()),
                "iqr": float(p75 - p25),
            }
        )
    return pd.DataFrame.from_records(records)


def _proportion_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    se = (p * (1 - p) / n) ** 0.5
    low = max(0.0, min(1.0, p - z * se))
    high = max(0.0, min(1.0, p + z * se))
    return low, high


def _outcome_summary_with_ci(
    df: pd.DataFrame, outcome_col: str, treatment_col: str, control_value
) -> pd.DataFrame:
    grouped = df.groupby(treatment_col)
    rows = []
    control_row = None
    for treatment, sub in grouped:
        n = int(sub.shape[0])
        rate = float(sub[outcome_col].mean()) if n else 0.0
        ci_low, ci_high = _proportion_ci(rate, n)
        row = {
            "treatment": treatment,
            "count": n,
            "rate": rate,
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
        rows.append(row)
        if treatment == control_value:
            control_row = row

    control_rate = control_row["rate"] if control_row else None
    control_n = control_row["count"] if control_row else None
    control_se = (
        (control_rate * (1 - control_rate) / control_n) ** 0.5
        if control_row and control_n
        else None
    )

    for row in rows:
        if control_rate is None or control_se is None or row["treatment"] == control_value:
            row["uplift_vs_control"] = None
            row["uplift_ci_low"] = None
            row["uplift_ci_high"] = None
            continue
        diff = row["rate"] - control_rate
        se_t = (row["rate"] * (1 - row["rate"]) / row["count"]) ** 0.5 if row["count"] else 0.0
        se_diff = (se_t ** 2 + control_se ** 2) ** 0.5
        delta = 1.96 * se_diff
        row["uplift_vs_control"] = diff
        row["uplift_ci_low"] = diff - delta
        row["uplift_ci_high"] = diff + delta
    return pd.DataFrame(rows)


def _smd_vs_control(
    df: pd.DataFrame, treatment_col: str, control_value, treatment_values: list | None = None
) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    records = []
    control_df = df[df[treatment_col] == control_value]
    n_c = int(control_df.shape[0])
    values = treatment_values if treatment_values is not None else df[treatment_col].unique().tolist()
    for treatment in values:
        if treatment == control_value:
            continue
        treat_df = df[df[treatment_col] == treatment]
        n_t = int(treat_df.shape[0])
        for col in numeric_cols:
            mean_t = float(treat_df[col].mean()) if n_t else float("nan")
            mean_c = float(control_df[col].mean()) if n_c else float("nan")
            std_t = float(treat_df[col].std(ddof=1)) if n_t > 1 else float("nan")
            std_c = float(control_df[col].std(ddof=1)) if n_c > 1 else float("nan")
            pooled_var = (
                ((std_t ** 2) if pd.notna(std_t) else 0.0)
                + ((std_c ** 2) if pd.notna(std_c) else 0.0)
            ) / 2
            pooled_std = pooled_var ** 0.5
            smd = (mean_t - mean_c) / pooled_std if pooled_std > 0 else float("nan")
            records.append(
                {
                    "treatment": treatment,
                    "feature": col,
                    "n_t": n_t,
                    "n_c": n_c,
                    "mean_t": mean_t,
                    "mean_c": mean_c,
                    "std_t": std_t,
                    "std_c": std_c,
                    "smd": smd,
                }
            )
    return pd.DataFrame.from_records(records)


def _require_column(df: pd.DataFrame, col: str) -> str:
    if col in df.columns:
        return col
    raise ValueError(
        f"Required column '{col}' not found. Available columns: {list(df.columns)}"
    )


def _value_counts_table(
    s: pd.Series, segment_var: str
) -> pd.DataFrame:
    vc = s.value_counts(dropna=False)
    pct = s.value_counts(normalize=True, dropna=False)
    out = pd.DataFrame(
        {
            "segment_var": segment_var,
            "category": vc.index.astype(str),
            "count": vc.values.astype("int64"),
            "pct": pct.values.astype("float64"),
        }
    )
    return out.sort_values(
        by=["segment_var", "count", "category"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def _print_value_counts_with_pct(s: pd.Series, label: str) -> None:
    vc = s.value_counts(dropna=False)
    pct = s.value_counts(normalize=True, dropna=False)
    out = pd.DataFrame(
        {
            label: vc.index.astype(str),
            "count": vc.values.astype("int64"),
            "pct": pct.values.astype("float64"),
        }
    )
    out = out.sort_values(by=["count", label], ascending=[False, True]).reset_index(drop=True)
    _print_dist_table(f"{label} (count, pct)", out, label)


def eda_kaggle() -> None:
    print("\n=== Kaggle: Customer Profile ===")

    df = load_kaggle_customer_profile()
    _print_kv("Shape (rows, cols)", df.shape)

    print("\n--- dtypes ---")
    print(df.dtypes.to_string())

    # Required segment columns
    seg_cols = ["Type", "Status", "GenderCode", "Living status"]
    for col in seg_cols:
        _require_column(df, col)

    # Value counts for each segment variable (console + artifact)
    segment_tables: list[pd.DataFrame] = []
    for col in seg_cols:
        cleaned = _clean_label_series(df[col])
        _print_value_counts_with_pct(cleaned, col)
        segment_tables.append(_value_counts_table(cleaned, col))

    # Age distribution
    age_col = _require_column(df, "age_years")
    print("\n--- Age distribution: age_years.describe() ---")
    print(df[age_col].describe().to_string())

    # Data quality flags
    underage = int((df[age_col] < 18).sum())
    overage = int((df[age_col] > 100).sum())
    _print_kv("Count age_years < 18", underage)
    _print_kv("Count age_years > 100", overage)

    # Normalization checks
    status_col = _require_column(df, "Status")
    norm_status = df[status_col].astype(str).str.strip().str.lower()
    if norm_status.nunique(dropna=False) < df[status_col].nunique(dropna=False):
        _print_kv("Status normalization reduced levels", norm_status.nunique(dropna=False))
        status_table = pd.DataFrame(
            {
                "Status": norm_status.value_counts(dropna=False).index.astype(str),
                "count": norm_status.value_counts(dropna=False).values.astype("int64"),
                "pct": norm_status.value_counts(normalize=True, dropna=False).values.astype("float64"),
            }
        )
        _print_dist_table("Normalized Status (count, pct)", status_table, "Status")

    living_col = _require_column(df, "Living status")
    norm_living = df[living_col].astype(str).str.strip().str.lower()
    if norm_living.nunique(dropna=False) < df[living_col].nunique(dropna=False):
        _print_kv("Living status normalization reduced levels", norm_living.nunique(dropna=False))
        living_table = pd.DataFrame(
            {
                "Living status": norm_living.value_counts(dropna=False).index.astype(str),
                "count": norm_living.value_counts(dropna=False).values.astype("int64"),
                "pct": norm_living.value_counts(normalize=True, dropna=False).values.astype("float64"),
            }
        )
        _print_dist_table("Normalized Living status (count, pct)", living_table, "Living status")

    # Missingness and robust summaries
    out_dir = _processed_dir()
    missing_df = _missingness_table(df)
    missing_path = out_dir / "kaggle_missingness.csv"
    missing_df.to_csv(missing_path, index=False)
    print("\n--- Missingness summary saved ---")
    _print_kv("Missingness shape", missing_df.shape)
    _print_kv("Saved", missing_path.as_posix())

    robust_df = _robust_numeric_summary(df)
    robust_path = out_dir / "kaggle_numeric_robust_summary.csv"
    robust_df.to_csv(robust_path, index=False)
    print("\n--- Robust numeric summary saved ---")
    _print_kv("Numeric summary shape", robust_df.shape)
    _print_kv("Saved", robust_path.as_posix())

    # Gender by Status cross-tab
    gender_col = _require_column(df, "GenderCode")
    status_col_for_tab = _require_column(df, "Status")
    counts = (
        pd.DataFrame(
            {
                gender_col: _clean_label_series(df[gender_col]),
                status_col_for_tab: _clean_label_series(df[status_col_for_tab]),
            }
        )
        .groupby([gender_col, status_col_for_tab])
        .size()
        .reset_index(name="count")
    )
    totals = counts.groupby(gender_col)["count"].transform("sum")
    counts["row_pct"] = counts["count"] / totals
    counts = counts.sort_values(
        by=[gender_col, "count", status_col_for_tab], ascending=[True, False, True]
    ).reset_index(drop=True)
    gender_status_path = out_dir / "kaggle_gender_by_status.csv"
    counts.to_csv(gender_status_path, index=False)
    _print_kv("Saved", gender_status_path.as_posix())

    # Save combined segment distribution table
    seg_dist = pd.concat(segment_tables, ignore_index=True)
    out_path = out_dir / "kaggle_segment_distribution.csv"
    seg_dist.to_csv(out_path, index=False)
    _print_kv("Saved", out_path.as_posix())


def eda_hillstrom() -> None:
    print("\n=== Hillstrom: Visit outcome ===")

    X, y, t = load_hillstrom(target_col="visit")

    _print_kv("X shape (rows, cols)", X.shape)

    df = X.copy()
    df["visit"] = pd.Series(y, index=df.index, name="visit")
    df["treatment_raw"] = pd.Series(t, index=df.index, name="treatment_raw")
    treatment_clean = _clean_label_series(df["treatment_raw"])

    _print_kv("Number of treatments", treatment_clean.nunique())

    # Treatment distribution
    treat_counts = treatment_clean.value_counts(dropna=False)
    treat_pct = treatment_clean.value_counts(normalize=True, dropna=False)
    treat_dist = pd.DataFrame(
        {
            "treatment_raw": treat_counts.index.astype(str),
            "count": treat_counts.values.astype("int64"),
            "pct": treat_pct.values.astype("float64"),
        }
    )
    treat_dist = treat_dist.sort_values(by=["treatment_raw"], ascending=True).reset_index(drop=True)
    _print_dist_table("Treatment distribution (count, pct)", treat_dist, "treatment_raw")

    # Overall visit rate
    overall_visit = float(df["visit"].mean())
    _print_kv("Overall visit rate (mean)", overall_visit)

    # Visit rate by treatment
    by_treat = (
        pd.DataFrame({"treatment_raw": treatment_clean, "visit": df["visit"]})
        .groupby("treatment_raw")["visit"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "mean_visit"})
    ).sort_values(by=["treatment_raw"], ascending=True).reset_index(drop=True)
    _print_dist_table("Visit rate by treatment (mean, count)", by_treat, "treatment_raw")

    # Raw uplift vs control (No E-Mail)
    control_label = "No E-Mail"
    control_mean = by_treat.loc[by_treat["treatment_raw"] == control_label, "mean_visit"]
    if not control_mean.empty:
        base = float(control_mean.iloc[0])
        print("\n--- Raw uplift vs control (No E-Mail) ---")
        for _, row in by_treat.iterrows():
            uplift = float(row["mean_visit"]) - base
            label = _format_label(row["treatment_raw"])
            _print_kv(f"{label} uplift", f"{uplift:.6f}")

    # Optional narrative-friendly checks
    if "channel" in df.columns:
        print("\n--- channel.value_counts() ---")
        print(df["channel"].value_counts(dropna=False).to_string())

    if "recency" in df.columns:
        print("\n--- recency.describe() ---")
        print(df["recency"].describe().to_string())

    # Save artifacts
    out_dir = _processed_dir()

    visit_by_segment = by_treat.rename(columns={"treatment_raw": "treatment_raw"})
    (out_dir / "hillstrom_visit_by_segment.csv").write_text(
        visit_by_segment.to_csv(index=False),
        encoding="utf-8",
    )
    _print_kv("Saved", (out_dir / "hillstrom_visit_by_segment.csv").as_posix())

    (out_dir / "hillstrom_treatment_distribution.csv").write_text(
        treat_dist.to_csv(index=False),
        encoding="utf-8",
    )
    _print_kv("Saved", (out_dir / "hillstrom_treatment_distribution.csv").as_posix())

    # Missingness and robust summaries
    full_df = df
    missing_df = _missingness_table(full_df)
    missing_path = out_dir / "hillstrom_missingness.csv"
    missing_df.to_csv(missing_path, index=False)
    _print_kv("Missingness shape", missing_df.shape)
    _print_kv("Saved", missing_path.as_posix())

    numeric_summary_df = _robust_numeric_summary(X)
    numeric_summary_path = out_dir / "hillstrom_numeric_robust_summary.csv"
    numeric_summary_df.to_csv(numeric_summary_path, index=False)
    _print_kv("Numeric summary shape", numeric_summary_df.shape)
    _print_kv("Saved", numeric_summary_path.as_posix())

    # Outcome summary with CI
    ci_df = pd.DataFrame({"treatment_raw": treatment_clean, "visit": df["visit"]})
    outcome_ci = _outcome_summary_with_ci(ci_df, "visit", "treatment_raw", control_value="No E-Mail")
    outcome_ci = outcome_ci.sort_values(by=["treatment"], ascending=True).reset_index(drop=True)
    outcome_ci_path = out_dir / "hillstrom_outcome_summary_with_ci.csv"
    outcome_ci.to_csv(outcome_ci_path, index=False)
    _print_kv("Saved", outcome_ci_path.as_posix())

    # Balance table (SMD)
    balance_df = _smd_vs_control(
        pd.concat([X, treatment_clean.rename("treatment_raw")], axis=1),
        treatment_col="treatment_raw",
        control_value="No E-Mail",
        treatment_values=["Mens E-Mail", "Womens E-Mail"],
    )
    if not balance_df.empty:
        balance_df = balance_df.assign(smd_abs=balance_df["smd"].abs()).sort_values(
            by=["treatment", "smd_abs"], ascending=[True, False]
        ).drop(columns=["smd_abs"]).reset_index(drop=True)
    balance_path = out_dir / "hillstrom_balance_smd_vs_control.csv"
    balance_df.to_csv(balance_path, index=False)
    _print_kv("Saved", balance_path.as_posix())


def eda_criteo() -> None:
    print("\n=== Criteo: Conversion outcome (10% sample) ===")

    X, y, t = load_criteo(target_col="conversion", percent10=True)

    _print_kv("X shape (rows, cols)", X.shape)

    df = X.copy()
    df["conversion"] = pd.Series(y, index=df.index, name="conversion")
    df["treatment"] = pd.Series(t, index=df.index, name="treatment")

    _print_kv("Number of treatments", df["treatment"].nunique())

    # Treatment distribution
    treat_counts = df["treatment"].value_counts(dropna=False)
    treat_pct = df["treatment"].value_counts(normalize=True, dropna=False)
    treat_dist = pd.DataFrame(
        {
            "treatment": treat_counts.index.astype(str),
            "count": treat_counts.values.astype("int64"),
            "pct": treat_pct.values.astype("float64"),
        }
    )
    treat_dist = treat_dist.sort_values(by=["treatment"], ascending=True).reset_index(drop=True)
    _print_dist_table("Treatment distribution (count, pct)", treat_dist, "treatment")

    # Overall conversion rate
    overall_conv = float(df["conversion"].mean())
    _print_kv("Overall conversion rate (mean)", overall_conv)

    # Conversion rate by treatment
    by_treat = (
        df.groupby("treatment")["conversion"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "mean_conversion"})
    ).sort_values(by=["treatment"], ascending=True).reset_index(drop=True)
    _print_dist_table("Conversion rate by treatment (mean, count)", by_treat, "treatment")

    # Raw uplift vs control (0)
    control_value = 0
    control_mean = by_treat.loc[by_treat["treatment"] == control_value, "mean_conversion"]
    if not control_mean.empty:
        base = float(control_mean.iloc[0])
        print("\n--- Raw uplift vs control (0) ---")
        for _, row in by_treat.iterrows():
            uplift = float(row["mean_conversion"]) - base
            label = _format_label(row["treatment"])
            _print_kv(f"{label} uplift", f"{uplift:.6f}")

    # Sanity summary (numeric columns only)
    print("\n--- Numeric summary (mean, std, min, max) ---")
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.shape[1] == 0:
        print("No numeric columns found for describe().")
    else:
        summary = numeric_df.describe().transpose()[["mean", "std", "min", "max"]]
        print(summary.to_string())

    # Save artifacts
    out_dir = _processed_dir()

    (out_dir / "criteo_conversion_by_treatment.csv").write_text(
        by_treat.to_csv(index=False),
        encoding="utf-8",
    )
    _print_kv("Saved", (out_dir / "criteo_conversion_by_treatment.csv").as_posix())

    (out_dir / "criteo_treatment_distribution.csv").write_text(
        treat_dist.to_csv(index=False),
        encoding="utf-8",
    )
    _print_kv("Saved", (out_dir / "criteo_treatment_distribution.csv").as_posix())

    # Missingness and robust summaries
    missing_df = _missingness_table(df)
    missing_path = out_dir / "criteo_missingness.csv"
    missing_df.to_csv(missing_path, index=False)
    _print_kv("Missingness shape", missing_df.shape)
    _print_kv("Saved", missing_path.as_posix())

    numeric_summary_df = _robust_numeric_summary(X)
    numeric_summary_path = out_dir / "criteo_numeric_robust_summary.csv"
    numeric_summary_df.to_csv(numeric_summary_path, index=False)
    _print_kv("Numeric summary shape", numeric_summary_df.shape)
    _print_kv("Saved", numeric_summary_path.as_posix())

    # Outcome summary with CI
    outcome_ci = _outcome_summary_with_ci(df, "conversion", "treatment", control_value=0)
    outcome_ci = outcome_ci.sort_values(by=["treatment"], ascending=True).reset_index(drop=True)
    outcome_ci_path = out_dir / "criteo_outcome_summary_with_ci.csv"
    outcome_ci.to_csv(outcome_ci_path, index=False)
    _print_kv("Saved", outcome_ci_path.as_posix())

    # Balance table (SMD)
    balance_df = _smd_vs_control(
        pd.concat([X, df["treatment"]], axis=1),
        treatment_col="treatment",
        control_value=0,
        treatment_values=[1],
    )
    if not balance_df.empty:
        balance_df = balance_df.assign(smd_abs=balance_df["smd"].abs()).sort_values(
            by=["treatment", "smd_abs"], ascending=[True, False]
        ).drop(columns=["smd_abs"]).reset_index(drop=True)
    balance_path = out_dir / "criteo_balance_smd.csv"
    balance_df.to_csv(balance_path, index=False)
    _print_kv("Saved", balance_path.as_posix())


def main() -> None:
    eda_kaggle()
    eda_hillstrom()
    eda_criteo()


if __name__ == "__main__":
    main()
