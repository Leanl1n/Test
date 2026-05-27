"""
03_risk_portfolio_health.py
----------------------------
GOAL: Monitor risk & portfolio health.

Analyses included:
  1. Policy status breakdown (In-Force, Lapsed, Surrendered, etc.)
  2. Premium at risk (lapsed policies by product category)
  3. Risk rating distribution (MEDRATING, OCCRATING)
  4. RPU, Surrender, and Loan indicators
  5. Cohort vintage analysis (persistency by issue year)
  6. Portfolio value summary (ANP, ANNPREM, coverage)

OUTPUT: Charts + CSV saved to output/risk/
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os
import warnings
warnings.filterwarnings("ignore")

import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_loader import load_data, load_merged

OUTPUT_DIR = "output/risk"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, bbox_inches="tight", dpi=150)
    print(f"  Saved → {path}")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
persistency, customer, policy = load_data()
merged = load_merged()


# ─────────────────────────────────────────────────────────────────────────────
# 1. POLICY STATUS BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 1. Policy Status Breakdown ───────────────────────────────────────")
if "POLICY_STATUS" in merged.columns:
    status = merged["POLICY_STATUS"].value_counts()
    print(status.to_string())

    fig, ax = plt.subplots(figsize=(8, 8))
    colors = ["#16A34A", "#DC2626", "#F59E0B", "#6B7280", "#2563EB", "#7C3AED"]
    ax.pie(status.values, labels=status.index, autopct="%1.1f%%",
           colors=colors[:len(status)], startangle=90)
    ax.set_title("Policy Status Distribution", fontweight="bold", fontsize=14)
    save(fig, "1_policy_status_breakdown.png")


# ─────────────────────────────────────────────────────────────────────────────
# 2. PREMIUM AT RISK BY PRODUCT CATEGORY
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. Premium at Risk by Product Category ───────────────────────────")
if all(c in merged.columns for c in ["PRODUCT_CATEGORY", "Written_PREM", "Pers 13"]):
    risk_df = merged.groupby("PRODUCT_CATEGORY").agg(
        total_written=("Written_PREM", "sum"),
        lapsed_prem=("Written_PREM", lambda x: x[merged.loc[x.index, "Pers 13"] == 0].sum()),
        avg_pers13=("Pers 13", "mean"),
    ).reset_index()
    risk_df["pct_at_risk"] = risk_df["lapsed_prem"] / risk_df["total_written"] * 100
    print(risk_df.to_string(index=False))

    fig, ax1 = plt.subplots(figsize=(10, 6))
    x = range(len(risk_df))
    bars = ax1.bar(x, risk_df["total_written"] / 1e6, color="#93C5FD", label="Total Written Premium (M)")
    ax1.bar(x, risk_df["lapsed_prem"] / 1e6, color="#FCA5A5", label="Premium at Risk (M)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(risk_df["PRODUCT_CATEGORY"], rotation=30, ha="right")
    ax1.set_ylabel("Premium (PHP Millions)")
    ax1.set_title("Premium at Risk by Product Category", fontweight="bold")
    ax1.legend()

    ax2 = ax1.twinx()
    ax2.plot(x, risk_df["pct_at_risk"], color="#DC2626", marker="o", linewidth=2, label="% at Risk")
    ax2.set_ylabel("% at Risk")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.legend(loc="upper right")
    plt.tight_layout()
    save(fig, "2_premium_at_risk_by_product.png")


# ─────────────────────────────────────────────────────────────────────────────
# 3. RISK RATING DISTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Risk Rating Distribution ──────────────────────────────────────")
for col in ["MEDRATING", "OCCRATING"]:
    if col in merged.columns:
        dist = merged[col].value_counts().sort_index()
        print(f"\n  {col}:\n{dist.to_string()}")

risk_cols_avail = [c for c in ["MEDRATING", "OCCRATING"] if c in merged.columns]
if risk_cols_avail:
    fig, axes = plt.subplots(1, len(risk_cols_avail), figsize=(7 * len(risk_cols_avail), 5))
    if len(risk_cols_avail) == 1:
        axes = [axes]
    for ax, col in zip(axes, risk_cols_avail):
        dist = merged[col].value_counts().sort_index()
        dist.plot(kind="bar", ax=ax, color="#7C3AED", edgecolor="white")
        ax.set_title(f"{col} Distribution", fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    save(fig, "3_risk_rating_distribution.png")


# ─────────────────────────────────────────────────────────────────────────────
# 4. RPU / SURRENDER / LOAN INDICATORS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. Policy Action Indicators ──────────────────────────────────────")
indicator_cols = {
    "RPU_IND":            "Reduced Paid-Up",
    "WITH_SURRENDER_IND": "Surrendered",
    "WITH_LOAN_IND":      "With Loan",
    "WITH_FREELOOK_IND":  "Free-Look",
}
avail_inds = {k: v for k, v in indicator_cols.items() if k in merged.columns}

if avail_inds:
    rates = {label: merged[col].mean() * 100 for col, label in avail_inds.items()}
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = list(rates.keys())
    values = list(rates.values())
    colors = ["#F59E0B", "#DC2626", "#2563EB", "#6B7280"]
    bars = ax.bar(labels, values, color=colors[:len(labels)], edgecolor="white")
    ax.set_title("Policy Action Indicators (% of Portfolio)", fontweight="bold")
    ax.set_ylabel("% of Policies")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    for bar, val in zip(bars, values):
        ax.annotate(f"{val:.1f}%",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontweight="bold")
    plt.tight_layout()
    save(fig, "4_policy_action_indicators.png")


# ─────────────────────────────────────────────────────────────────────────────
# 5. COHORT VINTAGE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Cohort Vintage Analysis ───────────────────────────────────────")
if "EFFECTIVE_DT" in merged.columns and "Pers 13" in merged.columns:
    merged["issue_year"] = pd.to_datetime(merged["EFFECTIVE_DT"], errors="coerce").dt.year
    cohort = merged.groupby("issue_year").agg(
        count=("OWNER_ALPHA_ID", "count"),
        pers13=("Pers 13", "mean"),
        pers25=("Pers 25", "mean") if "Pers 25" in merged.columns else ("Pers 13", "mean"),
        avg_prem=("Written_PREM", "mean") if "Written_PREM" in merged.columns else ("Pers 13", "count"),
    ).dropna(subset=["pers13"])
    print(cohort.to_string())

    fig, ax1 = plt.subplots(figsize=(12, 6))
    x = cohort.index
    ax1.bar(x, cohort["count"], color="#BFDBFE", label="Policy Count")
    ax1.set_ylabel("Policy Count")
    ax1.set_xlabel("Issue Year")

    ax2 = ax1.twinx()
    ax2.plot(x, cohort["pers13"] * 100, color="#2563EB", marker="o", linewidth=2, label="13-Month Pers %")
    if "Pers 25" in merged.columns:
        ax2.plot(x, cohort["pers25"] * 100, color="#DC2626", marker="s", linewidth=2, label="25-Month Pers %")
    ax2.set_ylabel("Persistency Rate (%)")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_title("Cohort Vintage Analysis: Policy Volume & Persistency by Issue Year",
                  fontweight="bold")
    plt.tight_layout()
    save(fig, "5_cohort_vintage_analysis.png")


# ─────────────────────────────────────────────────────────────────────────────
# 6. PORTFOLIO VALUE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Portfolio Value Summary ───────────────────────────────────────")
value_metrics = {
    "Written_PREM":  "Total Written Premium",
    "INPREM_m13":    "In-Force Premium @ 13M",
    "INPREM_m25":    "In-Force Premium @ 25M",
    "ANNPREM_PHP":   "Total Annualized Premium",
    "COVANT_PHP":    "Total Coverage (Base)",
    "ANP":           "Annualized New Premium",
}
summary = {}
for col, label in value_metrics.items():
    if col in merged.columns:
        summary[label] = merged[col].sum()

if summary:
    print("\n  Portfolio Summary (PHP):")
    for label, val in summary.items():
        print(f"    {label:<30} PHP {val:>20,.0f}")

    fig, ax = plt.subplots(figsize=(10, 5))
    labels = list(summary.keys())
    values = [v / 1e6 for v in summary.values()]
    colors = ["#2563EB", "#16A34A", "#059669", "#7C3AED", "#F59E0B", "#DC2626"]
    bars = ax.barh(labels, values, color=colors[:len(labels)], edgecolor="white")
    ax.set_xlabel("PHP (Millions)")
    ax.set_title("Portfolio Value Summary", fontweight="bold")
    for bar, val in zip(bars, values):
        ax.annotate(f"₱{val:,.1f}M",
                    (val + max(values) * 0.01, bar.get_y() + bar.get_height() / 2),
                    va="center", fontsize=9)
    plt.tight_layout()
    save(fig, "6_portfolio_value_summary.png")

    # Export summary CSV
    pd.DataFrame(list(summary.items()), columns=["Metric", "Value (PHP)"]).to_csv(
        os.path.join(OUTPUT_DIR, "portfolio_summary.csv"), index=False
    )

print("\n✅ Risk & Portfolio Health Analysis complete. See output/risk/")
