"""
04_agent_branch_performance.py
-------------------------------
GOAL: Improve agent & branch performance evaluation.

Analyses included:
  1. Branch-level persistency (quality) vs premium volume
  2. Agent (BSE) performance ranking
  3. Quality vs volume scatter plot (quadrant analysis)
  4. New vs existing customer mix by branch
  5. Channel performance (worksite, OFW, personal, preferred)
  6. Campaign attribution by persistency rate

OUTPUT: Charts + CSV saved to output/agent_performance/
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mtick
import os
import warnings
warnings.filterwarnings("ignore")

import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_loader import load_data, load_merged

OUTPUT_DIR = "output/agent_performance"
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
# 1. BRANCH-LEVEL PERSISTENCY vs VOLUME
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 1. Branch Performance Summary ────────────────────────────────────")
if "BRANCH_NAME" in merged.columns and "Pers 13" in merged.columns:
    branch_agg = {
        "policy_count": ("OWNER_ALPHA_ID", "count"),
        "pers13_rate":  ("Pers 13", "mean"),
    }
    if "Pers 25" in merged.columns:
        branch_agg["pers25_rate"] = ("Pers 25", "mean")
    if "Written_PREM" in merged.columns:
        branch_agg["total_written_prem"] = ("Written_PREM", "sum")
    if "ANP" in merged.columns:
        branch_agg["total_anp"] = ("ANP", "sum")

    branch = merged.groupby("BRANCH_NAME").agg(**branch_agg).reset_index()
    branch["pers13_pct"] = branch["pers13_rate"] * 100
    branch = branch.sort_values("pers13_pct", ascending=False)

    print(f"  Branches found: {len(branch)}")
    print(branch.head(10).to_string(index=False))

    # Top 20 branches chart
    top_n = branch.head(20)
    fig, ax1 = plt.subplots(figsize=(14, 7))
    x = range(len(top_n))
    ax1.bar(x, top_n["policy_count"], color="#BFDBFE", label="Policy Count")
    ax1.set_ylabel("Policy Count")
    ax1.set_xlabel("Branch")
    ax1.set_xticks(x)
    ax1.set_xticklabels(top_n["BRANCH_NAME"], rotation=45, ha="right", fontsize=8)

    ax2 = ax1.twinx()
    ax2.plot(x, top_n["pers13_pct"], color="#DC2626", marker="o", linewidth=2, label="13M Persistency %")
    ax2.set_ylabel("13-Month Persistency (%)")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax2.axhline(branch["pers13_pct"].mean(), color="#6B7280", linestyle="--",
                alpha=0.7, label=f"Avg: {branch['pers13_pct'].mean():.1f}%")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    ax1.set_title("Top 20 Branches: Policy Volume vs 13-Month Persistency", fontweight="bold")
    plt.tight_layout()
    save(fig, "1_branch_volume_vs_persistency.png")

    # Export branch summary
    branch.to_csv(os.path.join(OUTPUT_DIR, "branch_performance_summary.csv"), index=False)
    print(f"  Branch summary exported → output/agent_performance/branch_performance_summary.csv")


# ─────────────────────────────────────────────────────────────────────────────
# 2. QUALITY vs VOLUME QUADRANT (Scatter)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. Quality vs Volume Quadrant Analysis ───────────────────────────")
group_col = "BRANCH_NAME" if "BRANCH_NAME" in merged.columns else "SOLICIT_BSE"

if group_col in merged.columns and "Pers 13" in merged.columns and "Written_PREM" in merged.columns:
    qv = merged.groupby(group_col).agg(
        pers13=("Pers 13", "mean"),
        total_prem=("Written_PREM", "sum"),
        count=("OWNER_ALPHA_ID", "count"),
    ).reset_index()
    qv = qv[qv["count"] >= 10]  # filter low-volume entries

    avg_pers = qv["pers13"].mean()
    avg_prem = qv["total_prem"].mean()

    fig, ax = plt.subplots(figsize=(12, 8))
    scatter = ax.scatter(
        qv["total_prem"] / 1e6,
        qv["pers13"] * 100,
        s=qv["count"] * 2,
        c=qv["pers13"],
        cmap="RdYlGn",
        alpha=0.75,
        edgecolors="white",
        linewidth=0.5,
    )
    ax.axvline(avg_prem / 1e6, color="#6B7280", linestyle="--", alpha=0.6)
    ax.axhline(avg_pers * 100, color="#6B7280", linestyle="--", alpha=0.6)

    # Quadrant labels
    ax.text(0.98, 0.98, "⭐ Stars\n(High Quality, High Volume)",
            transform=ax.transAxes, ha="right", va="top", color="#16A34A", fontsize=9, fontweight="bold")
    ax.text(0.02, 0.98, "💎 Quality Focus\n(High Quality, Low Volume)",
            transform=ax.transAxes, ha="left", va="top", color="#2563EB", fontsize=9, fontweight="bold")
    ax.text(0.98, 0.02, "⚡ Volume Risk\n(Low Quality, High Volume)",
            transform=ax.transAxes, ha="right", va="bottom", color="#F59E0B", fontsize=9, fontweight="bold")
    ax.text(0.02, 0.02, "⚠️ Needs Attention\n(Low Quality, Low Volume)",
            transform=ax.transAxes, ha="left", va="bottom", color="#DC2626", fontsize=9, fontweight="bold")

    plt.colorbar(scatter, ax=ax, label="13-Month Persistency Rate")
    ax.set_xlabel("Total Written Premium (PHP Millions)")
    ax.set_ylabel("13-Month Persistency Rate (%)")
    ax.set_title(f"Quality vs Volume Quadrant Analysis by {group_col}", fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    plt.tight_layout()
    save(fig, "2_quality_vs_volume_quadrant.png")


# ─────────────────────────────────────────────────────────────────────────────
# 3. AGENT (BSE) PERFORMANCE RANKING
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Agent (BSE) Performance Ranking ──────────────────────────────")
if "SOLICIT_BSE" in merged.columns and "Pers 13" in merged.columns:
    bse = merged.groupby("SOLICIT_BSE").agg(
        policy_count=("OWNER_ALPHA_ID", "count"),
        pers13=("Pers 13", "mean"),
        total_prem=("Written_PREM", "sum") if "Written_PREM" in merged.columns else ("Pers 13", "count"),
    ).reset_index()
    bse = bse[bse["policy_count"] >= 5]
    bse["pers13_pct"] = bse["pers13"] * 100
    bse["composite_score"] = (bse["pers13_pct"] / 100 * 0.6) + \
                              (bse["policy_count"] / bse["policy_count"].max() * 0.4)
    bse = bse.sort_values("composite_score", ascending=False)

    top20_bse = bse.head(20)
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#16A34A" if s >= 0.6 else "#F59E0B" if s >= 0.4 else "#DC2626"
              for s in top20_bse["composite_score"]]
    ax.barh(top20_bse["SOLICIT_BSE"].astype(str), top20_bse["composite_score"],
            color=colors, edgecolor="white")
    ax.set_title("Top 20 Agents: Composite Performance Score\n(60% Persistency + 40% Volume)",
                 fontweight="bold")
    ax.set_xlabel("Composite Score")
    plt.tight_layout()
    save(fig, "3_agent_performance_ranking.png")

    bse.to_csv(os.path.join(OUTPUT_DIR, "agent_performance_ranking.csv"), index=False)
    print(f"  Agent rankings exported → output/agent_performance/agent_performance_ranking.csv")


# ─────────────────────────────────────────────────────────────────────────────
# 4. NEW vs EXISTING CUSTOMER MIX BY BRANCH
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. New vs Existing Customer Mix by Branch ───────────────────────")
if all(c in merged.columns for c in ["BRANCH_NAME", "New FTM IND", "Pers 13"]):
    mix = merged.groupby(["BRANCH_NAME", "New FTM IND"])["Pers 13"].agg(["mean", "count"]).reset_index()
    mix.columns = ["BRANCH_NAME", "New FTM IND", "pers13", "count"]
    mix["type"] = mix["New FTM IND"].map({1: "New/FTM", 0: "Existing"})

    # Only show top 10 branches by volume
    top_branches = merged.groupby("BRANCH_NAME").size().nlargest(10).index
    mix_top = mix[mix["BRANCH_NAME"].isin(top_branches)]

    pivot = mix_top.pivot_table(index="BRANCH_NAME", columns="type", values="pers13").fillna(0) * 100
    fig, ax = plt.subplots(figsize=(12, 6))
    pivot.plot(kind="bar", ax=ax, color=["#F59E0B", "#2563EB"], edgecolor="white")
    ax.set_title("13-Month Persistency: New vs Existing Customers by Branch (Top 10)", fontweight="bold")
    ax.set_ylabel("Persistency Rate (%)")
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.tick_params(axis="x", rotation=45)
    ax.legend(title="Customer Type")
    plt.tight_layout()
    save(fig, "4_new_vs_existing_by_branch.png")


# ─────────────────────────────────────────────────────────────────────────────
# 5. CHANNEL PERFORMANCE
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Channel Performance ───────────────────────────────────────────")
channel_cols = {
    "WORKSITE_IND":  "Worksite",
    "OFW_IND":       "OFW",
    "PREFERRED_IND": "Preferred",
    "PERSONAL_IND":  "Personal",
    "PRIVATE_IND":   "Private",
}
avail_ch = {col: label for col, label in channel_cols.items() if col in merged.columns}

if avail_ch and "Pers 13" in merged.columns:
    ch_pers = {}
    for col, label in avail_ch.items():
        ch_data = merged[merged[col] == 1]["Pers 13"]
        if len(ch_data) > 0:
            ch_pers[label] = ch_data.mean() * 100

    if ch_pers:
        fig, ax = plt.subplots(figsize=(9, 5))
        labels = list(ch_pers.keys())
        values = list(ch_pers.values())
        avg = np.mean(values)
        colors = ["#16A34A" if v >= avg else "#DC2626" for v in values]
        bars = ax.bar(labels, values, color=colors, edgecolor="white")
        ax.axhline(avg, color="#6B7280", linestyle="--", label=f"Average: {avg:.1f}%")
        ax.set_title("13-Month Persistency Rate by Sales Channel", fontweight="bold")
        ax.set_ylabel("Persistency Rate (%)")
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.legend()
        for bar, val in zip(bars, values):
            ax.annotate(f"{val:.1f}%",
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom", fontweight="bold")
        plt.tight_layout()
        save(fig, "5_channel_performance.png")


# ─────────────────────────────────────────────────────────────────────────────
# 6. CAMPAIGN ATTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Campaign Attribution ──────────────────────────────────────────")
if "CAMPAIGN_CODE" in merged.columns and "Pers 13" in merged.columns:
    camp = merged.groupby("CAMPAIGN_CODE").agg(
        count=("OWNER_ALPHA_ID", "count"),
        pers13=("Pers 13", "mean"),
        total_prem=("Written_PREM", "sum") if "Written_PREM" in merged.columns else ("Pers 13", "count"),
    ).reset_index()
    camp = camp[camp["count"] >= 5].sort_values("pers13", ascending=False)
    camp["pers13_pct"] = camp["pers13"] * 100

    top_camp = camp.head(15)
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(top_camp["CAMPAIGN_CODE"].astype(str), top_camp["pers13_pct"],
                  color="#7C3AED", edgecolor="white")
    ax.axhline(camp["pers13_pct"].mean(), color="#DC2626", linestyle="--",
               label=f"Avg: {camp['pers13_pct'].mean():.1f}%")
    ax.set_title("Top 15 Campaigns: 13-Month Persistency Rate", fontweight="bold")
    ax.set_ylabel("Persistency Rate (%)")
    ax.set_xlabel("Campaign Code")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    plt.tight_layout()
    save(fig, "6_campaign_attribution.png")

    camp.to_csv(os.path.join(OUTPUT_DIR, "campaign_attribution.csv"), index=False)

print("\n✅ Agent & Branch Performance Analysis complete. See output/agent_performance/")
