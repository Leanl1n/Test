"""
01_retention_lapse_analysis.py
-------------------------------
GOAL: Reduce customer churn & improve retention.

Analyses included:
  1. Overall persistency rates (13-month and 25-month)
  2. Lapse rates by demographics (age, gender, civil status, income)
  3. Lapse rates by payment mode
  4. Digital engagement vs retention
  5. Complaint & claims correlation with lapse
  6. Premium retention ratio (INPREM / Written_PREM)
  7. Churn risk scoring (logistic regression)

OUTPUT: Charts saved to /output/retention/
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os
import warnings
warnings.filterwarnings("ignore")

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

# Import loader
import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_loader import load_data, load_merged

OUTPUT_DIR = "output/retention"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────
def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, bbox_inches="tight", dpi=150)
    print(f"  Saved → {path}")
    plt.close(fig)


def pct_bar(ax, df, col, target, title, color="#2563EB"):
    """Bar chart: lapse/retention rate by a categorical column."""
    grp = df.groupby(col)[target].mean().sort_values(ascending=False) * 100
    grp.plot(kind="bar", ax=ax, color=color, edgecolor="white")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Rate (%)")
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.tick_params(axis="x", rotation=45)
    for p in ax.patches:
        ax.annotate(f"{p.get_height():.1f}%",
                    (p.get_x() + p.get_width() / 2, p.get_height()),
                    ha="center", va="bottom", fontsize=8)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
persistency, customer, policy = load_data()
merged = load_merged()

# ─────────────────────────────────────────────────────────────────────────────
# 1. OVERALL PERSISTENCY RATES
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 1. Overall Persistency Rates ─────────────────────────────────────")
pers13 = merged["Pers 13"].mean() * 100 if "Pers 13" in merged else None
pers25 = merged["Pers 25"].mean() * 100 if "Pers 25" in merged else None
print(f"  13-month persistency rate : {pers13:.1f}%" if pers13 else "  Pers 13 not found")
print(f"  25-month persistency rate : {pers25:.1f}%" if pers25 else "  Pers 25 not found")

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, (label, val, color) in zip(axes, [
    ("13-Month Persistency", pers13, "#16A34A"),
    ("25-Month Persistency", pers25, "#2563EB"),
]):
    if val is not None:
        ax.pie([val, 100 - val], labels=["Active", "Lapsed"],
               colors=[color, "#E5E7EB"], autopct="%1.1f%%", startangle=90)
        ax.set_title(label, fontweight="bold")
fig.suptitle("Overall Persistency Rates", fontsize=14, fontweight="bold")
save(fig, "1_overall_persistency.png")


# ─────────────────────────────────────────────────────────────────────────────
# 2. LAPSE RATES BY DEMOGRAPHICS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. Lapse Rates by Demographics ──────────────────────────────────")
demo_cols = {
    "AGE_Range":          "Age Range",
    "Owner_Gender":       "Gender",
    "OWNER_CIVIL_STATUS": "Civil Status",
    "EDUC_ATTAINMENT":    "Education",
}

fig, axes = plt.subplots(2, 2, figsize=(16, 10))
axes = axes.flatten()
colors = ["#DC2626", "#7C3AED", "#059669", "#D97706"]

for ax, (col, label), color in zip(axes, demo_cols.items(), colors):
    if col in merged.columns and "Pers 13" in merged.columns:
        pct_bar(ax, merged, col, "Pers 13", f"13-Month Retention by {label}", color)
    else:
        ax.set_visible(False)

fig.suptitle("Retention Rates by Demographics (13-Month)", fontsize=14, fontweight="bold")
plt.tight_layout()
save(fig, "2_retention_by_demographics.png")


# ─────────────────────────────────────────────────────────────────────────────
# 3. LAPSE RATE BY PAYMENT MODE
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Lapse Rates by Payment Mode ──────────────────────────────────")
if "PAYMENT_MODE_DESC" in merged.columns and "Pers 13" in merged.columns:
    fig, ax = plt.subplots(figsize=(8, 5))
    pct_bar(ax, merged, "PAYMENT_MODE_DESC", "Pers 13",
            "13-Month Retention Rate by Payment Mode", "#0891B2")
    plt.tight_layout()
    save(fig, "3_retention_by_payment_mode.png")
else:
    print("  PAYMENT_MODE_DESC or Pers 13 not found — skipping")


# ─────────────────────────────────────────────────────────────────────────────
# 4. DIGITAL ENGAGEMENT vs RETENTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. Digital Engagement vs Retention ───────────────────────────────")
engagement_cols = ["WITH_EMAIL_IND", "WITH_MOBILE_IND", "MARKETING_CONSENT", "VITALITY_IND"]
eng_available = [c for c in engagement_cols if c in merged.columns]

if eng_available and "Pers 13" in merged.columns:
    rates = {}
    for col in eng_available:
        rates[col] = merged.groupby(col)["Pers 13"].mean() * 100

    fig, axes = plt.subplots(1, len(eng_available), figsize=(5 * len(eng_available), 5))
    if len(eng_available) == 1:
        axes = [axes]
    for ax, col in zip(axes, eng_available):
        df_plot = rates[col].reset_index()
        df_plot[col] = df_plot[col].map({0: "No", 1: "Yes"})
        ax.bar(df_plot[col], df_plot["Pers 13"], color=["#F87171", "#34D399"], edgecolor="white")
        ax.set_title(col.replace("_", " ").title(), fontweight="bold")
        ax.set_ylabel("Retention Rate (%)")
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        for p in ax.patches:
            ax.annotate(f"{p.get_height():.1f}%",
                        (p.get_x() + p.get_width() / 2, p.get_height()),
                        ha="center", va="bottom")
    fig.suptitle("Digital Engagement vs 13-Month Retention", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "4_digital_engagement_vs_retention.png")


# ─────────────────────────────────────────────────────────────────────────────
# 5. COMPLAINT & CLAIMS vs LAPSE
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Complaints & Claims vs Lapse ──────────────────────────────────")
risk_cols = ["WITH_COMPLAINT", "CLAIMS_IND", "WITH_FREELOOK_IND", "WITH_SURRENDER_IND"]
risk_available = [c for c in risk_cols if c in merged.columns]

if risk_available and "Pers 13" in merged.columns:
    lapse_rates = {}
    for col in risk_available:
        lapse_rates[col] = merged.groupby(col)["Pers 13"].mean() * 100

    fig, axes = plt.subplots(1, len(risk_available), figsize=(5 * len(risk_available), 5))
    if len(risk_available) == 1:
        axes = [axes]
    for ax, col in zip(axes, risk_available):
        df_plot = lapse_rates[col].reset_index()
        df_plot[col] = df_plot[col].map({0: "No", 1: "Yes"})
        ax.bar(df_plot[col], df_plot["Pers 13"], color=["#34D399", "#F87171"], edgecolor="white")
        ax.set_title(col.replace("_", " ").title(), fontweight="bold")
        ax.set_ylabel("Retention Rate (%)")
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    fig.suptitle("Risk Indicators vs 13-Month Retention", fontsize=13, fontweight="bold")
    plt.tight_layout()
    save(fig, "5_risk_indicators_vs_retention.png")


# ─────────────────────────────────────────────────────────────────────────────
# 6. PREMIUM RETENTION RATIO
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Premium Retention Ratios ──────────────────────────────────────")
cols_needed = ["Written_PREM", "INPREM_m13", "INPREM_m25"]
if all(c in merged.columns for c in cols_needed):
    df_prem = merged[cols_needed].dropna()
    df_prem = df_prem[df_prem["Written_PREM"] > 0]
    df_prem["ratio_13"] = df_prem["INPREM_m13"] / df_prem["Written_PREM"] * 100
    df_prem["ratio_25"] = df_prem["INPREM_m25"] / df_prem["Written_PREM"] * 100

    print(f"  Avg 13-month premium retention: {df_prem['ratio_13'].mean():.1f}%")
    print(f"  Avg 25-month premium retention: {df_prem['ratio_25'].mean():.1f}%")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(df_prem["ratio_13"], bins=40, alpha=0.6, color="#2563EB", label="13-Month")
    ax.hist(df_prem["ratio_25"], bins=40, alpha=0.6, color="#DC2626", label="25-Month")
    ax.set_xlabel("Premium Retention Ratio (%)")
    ax.set_ylabel("Number of Customers")
    ax.set_title("Distribution of Premium Retention Ratios", fontweight="bold")
    ax.legend()
    save(fig, "6_premium_retention_ratio.png")


# ─────────────────────────────────────────────────────────────────────────────
# 7. CHURN RISK SCORING (Logistic Regression)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 7. Churn Risk Scoring Model ──────────────────────────────────────")
feature_candidates = [
    "AGE_Range", "Owner_Gender", "OWNER_CIVIL_STATUS", "EDUC_ATTAINMENT",
    "Policy_Freq", "Purchase_Interval", "PAYMENT_MODE_DESC",
    "WITH_EMAIL_IND", "WITH_MOBILE_IND", "MARKETING_CONSENT",
    "WITH_COMPLAINT", "CLAIMS_IND", "MEDRATING", "OCCRATING",
    "ANNPREM_PHP", "PREMCLUB_IND", "Active_Cust_IND"
]
target = "Pers 13"

available_features = [c for c in feature_candidates if c in merged.columns]

if target in merged.columns and len(available_features) >= 3:
    df_model = merged[available_features + [target]].dropna(subset=[target])

    # Encode categoricals
    le = LabelEncoder()
    for col in df_model.select_dtypes(include="object").columns:
        df_model[col] = le.fit_transform(df_model[col].astype(str))

    df_model = df_model.fillna(df_model.median(numeric_only=True))

    X = df_model[available_features]
    y = df_model[target].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LogisticRegression(max_iter=500)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    print(f"\n  Model AUC: {auc:.3f}")
    print(classification_report(y_test, y_pred, target_names=["Lapsed", "Retained"]))

    # Feature importance
    importance = pd.Series(np.abs(model.coef_[0]), index=available_features).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(8, max(5, len(importance) * 0.4)))
    importance.plot(kind="barh", ax=ax, color="#7C3AED")
    ax.set_title("Churn Model: Feature Importance (|Coefficient|)", fontweight="bold")
    ax.set_xlabel("Absolute Coefficient")
    plt.tight_layout()
    save(fig, "7_churn_model_feature_importance.png")

    # Save churn scores to CSV
    merged_scored = merged.copy()
    df_score = df_model[available_features].fillna(df_model[available_features].median())
    merged_scored.loc[df_model.index, "churn_risk_score"] = model.predict_proba(df_score)[:, 0]
    score_output = os.path.join(OUTPUT_DIR, "churn_risk_scores.csv")
    merged_scored[["OWNER_ALPHA_ID", "churn_risk_score"]].dropna().to_csv(score_output, index=False)
    print(f"\n  Churn risk scores saved → {score_output}")
else:
    print("  Not enough features available for model — skipping")

print("\n✅ Retention & Lapse Analysis complete. See output/retention/")
