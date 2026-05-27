"""
02_crosssell_upsell_targeting.py
----------------------------------
GOAL: Grow revenue through cross-sell and upsell targeting.

Analyses included:
  1. Active single-policy holders (prime cross-sell candidates)
  2. Near Premier Club qualifiers (upsell targets)
  3. Purchase interval distribution (timing for next offer)
  4. Product gap analysis (what customers DON'T have yet)
  5. Contactability matrix (who can actually be reached)
  6. Cross-sell candidate export (scored list)

OUTPUT: Charts + CSV saved to output/crosssell/
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

OUTPUT_DIR = "output/crosssell"
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
# 1. ACTIVE SINGLE-POLICY HOLDERS (Cross-sell candidates)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 1. Cross-Sell Candidate Pool ─────────────────────────────────────")

filters = {}
if "Active_Cust_IND" in merged.columns:
    filters["Active"] = merged["Active_Cust_IND"] == 1
if "Policy_Freq" in merged.columns:
    filters["Single-Policy"] = merged["Policy_Freq"] == 1
if "POLICY_STATUS" in merged.columns:
    filters["In-Force"] = merged["POLICY_STATUS"].str.lower().str.contains("in-force", na=False)

mask = pd.Series([True] * len(merged), index=merged.index)
for f in filters.values():
    mask = mask & f

candidates = merged[mask].copy()
print(f"  Total records:          {len(merged):,}")
print(f"  Cross-sell candidates:  {len(candidates):,} ({len(candidates)/len(merged)*100:.1f}%)")

# Pie chart
fig, ax = plt.subplots(figsize=(6, 6))
ax.pie(
    [len(candidates), len(merged) - len(candidates)],
    labels=["Cross-sell Candidates", "Others"],
    colors=["#16A34A", "#E5E7EB"],
    autopct="%1.1f%%",
    startangle=90,
)
ax.set_title("Active Single-Policy Holders\n(Cross-Sell Candidate Pool)", fontweight="bold")
save(fig, "1_crosssell_candidate_pool.png")


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEAR PREMIER CLUB QUALIFIERS (Upsell targets)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. Near Premier Club Qualifiers ──────────────────────────────────")
if "NEAR_PREMCLUB_IND" in merged.columns and "PREMCLUB_IND" in merged.columns:
    premclub = merged.groupby(["PREMCLUB_IND", "NEAR_PREMCLUB_IND"]).size().reset_index(name="count")
    print(premclub.to_string(index=False))

    near_quals = merged[
        (merged["PREMCLUB_IND"] == 0) & (merged["NEAR_PREMCLUB_IND"] == 1)
    ]
    print(f"\n  Near-qualifier upsell targets: {len(near_quals):,}")

    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["Non-Member\n(not near)", "Near Qualifier\n(upsell target)", "Member"]
    counts = [
        len(merged[(merged["PREMCLUB_IND"] == 0) & (merged["NEAR_PREMCLUB_IND"] == 0)]),
        len(near_quals),
        len(merged[merged["PREMCLUB_IND"] == 1]),
    ]
    colors = ["#94A3B8", "#F59E0B", "#16A34A"]
    bars = ax.bar(labels, counts, color=colors, edgecolor="white")
    ax.set_title("Premier Club Membership Segmentation", fontweight="bold")
    ax.set_ylabel("Number of Customers")
    for bar in bars:
        ax.annotate(f"{bar.get_height():,}",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontweight="bold")
    save(fig, "2_premier_club_segmentation.png")


# ─────────────────────────────────────────────────────────────────────────────
# 3. PURCHASE INTERVAL DISTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Purchase Interval Distribution ───────────────────────────────")
if "Purchase_Interval" in merged.columns:
    pi = merged["Purchase_Interval"].dropna()
    print(f"  Mean interval:   {pi.mean():.1f} days")
    print(f"  Median interval: {pi.median():.1f} days")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(pi, bins=40, color="#2563EB", edgecolor="white", alpha=0.85)
    ax.axvline(pi.mean(), color="#DC2626", linestyle="--", label=f"Mean: {pi.mean():.0f}d")
    ax.axvline(pi.median(), color="#16A34A", linestyle="--", label=f"Median: {pi.median():.0f}d")
    ax.set_xlabel("Purchase Interval (days)")
    ax.set_ylabel("Number of Customers")
    ax.set_title("Customer Purchase Interval Distribution", fontweight="bold")
    ax.legend()
    save(fig, "3_purchase_interval_distribution.png")


# ─────────────────────────────────────────────────────────────────────────────
# 4. PRODUCT CATEGORY PENETRATION (What do customers own?)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. Product Category Penetration ─────────────────────────────────")
if "PRODUCT_CATEGORY" in merged.columns:
    prod_dist = merged["PRODUCT_CATEGORY"].value_counts()
    print(prod_dist.to_string())

    fig, ax = plt.subplots(figsize=(9, 5))
    prod_dist.plot(kind="bar", ax=ax, color="#7C3AED", edgecolor="white")
    ax.set_title("Product Category Distribution", fontweight="bold")
    ax.set_ylabel("Number of Policies")
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=45)
    for p in ax.patches:
        ax.annotate(f"{int(p.get_height()):,}",
                    (p.get_x() + p.get_width() / 2, p.get_height()),
                    ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    save(fig, "4_product_category_distribution.png")


# ─────────────────────────────────────────────────────────────────────────────
# 5. CONTACTABILITY MATRIX
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Contactability Matrix ─────────────────────────────────────────")
contact_cols = {
    "WITH_EMAIL_IND":   "Has Email",
    "WITH_MOBILE_IND":  "Has Mobile",
    "WITH_ADDRESS_IND": "Has Address",
    "MARKETING_CONSENT":"Marketing Consent",
    "DP_CONSENT":       "Data Privacy Consent",
}
available_contact = {k: v for k, v in contact_cols.items() if k in merged.columns}

if available_contact:
    contact_rates = {
        label: merged[col].mean() * 100
        for col, label in available_contact.items()
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    labels = list(contact_rates.keys())
    values = list(contact_rates.values())
    colors = ["#16A34A" if v >= 70 else "#F59E0B" if v >= 40 else "#DC2626" for v in values]
    bars = ax.barh(labels, values, color=colors, edgecolor="white")
    ax.set_xlabel("% of Customers")
    ax.set_title("Customer Contactability Matrix", fontweight="bold")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.axvline(50, color="#6B7280", linestyle="--", alpha=0.5)
    for bar, val in zip(bars, values):
        ax.annotate(f"{val:.1f}%",
                    (val + 0.5, bar.get_y() + bar.get_height() / 2),
                    va="center", fontsize=10)
    plt.tight_layout()
    save(fig, "5_contactability_matrix.png")


# ─────────────────────────────────────────────────────────────────────────────
# 6. CROSS-SELL CANDIDATE SCORED LIST EXPORT
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Exporting Scored Cross-Sell Candidate List ────────────────────")

score_cols = ["OWNER_ALPHA_ID"]
optional = [
    "AGE_Range", "Owner_Gender", "OWNER_ANNUAL_INCOME",
    "Policy_Freq", "Purchase_Interval", "REGENCY",
    "WITH_EMAIL_IND", "WITH_MOBILE_IND", "MARKETING_CONSENT",
    "PRODUCT_CATEGORY", "ANNPREM_PHP", "PREMCLUB_IND",
    "NEAR_PREMCLUB_IND", "Active_Cust_IND", "Pers 13", "Pers 25"
]
score_cols += [c for c in optional if c in merged.columns]

export_df = candidates[score_cols].copy() if len(candidates) > 0 else merged[score_cols].copy()

# Simple scoring: rank by premium desc (higher value customers first)
if "ANNPREM_PHP" in export_df.columns:
    export_df = export_df.sort_values("ANNPREM_PHP", ascending=False)

out_path = os.path.join(OUTPUT_DIR, "crosssell_candidates.csv")
export_df.to_csv(out_path, index=False)
print(f"  {len(export_df):,} records exported → {out_path}")

print("\n✅ Cross-sell & Upsell Analysis complete. See output/crosssell/")
