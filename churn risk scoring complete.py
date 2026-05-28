"""
churn_risk_scoring_complete.py
================================
Complete churn risk scoring script using XGBoost.

What this script does:
  1. Loads and merges all 3 CSVs
  2. Prepares features for the model
  3. Trains XGBoost churn prediction model
  4. Evaluates model accuracy (AUC, classification report)
  5. Scores ALL customers
  6. Exports 3 output files:
       - churn_scores_policy_level.csv       (one row per policy)
       - churn_scores_customer_highest.csv   (one row per customer, worst policy shown)
       - churn_scores_customer_average.csv   (one row per customer, averaged across policies)
  7. Saves charts:
       - ROC curve
       - Feature importance
       - SHAP summary (explainability)
       - Risk category distribution

Install requirements first:
  pip install pandas numpy matplotlib scikit-learn xgboost shap

UPDATE FILE PATHS BELOW BEFORE RUNNING.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os
import warnings
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    roc_curve,
    confusion_matrix,
    ConfusionMatrixDisplay,
)
from xgboost import XGBClassifier
import shap

# ─────────────────────────────────────────────────────────────────────────────
# FILE PATHS — UPDATE THESE
# ─────────────────────────────────────────────────────────────────────────────
PERSISTENCY_CSV = "customer_persistency.csv"
CUSTOMER_CSV    = "inf_customer.csv"
POLICY_CSV      = "inf_policy.csv"

OUTPUT_DIR      = "output/churn_scoring"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET          = "Pers 13"   # change to "Pers 25" for 25-month model


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────
def save_chart(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, bbox_inches="tight", dpi=150)
    print(f"  Chart saved → {path}")
    plt.close(fig)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — LOAD & MERGE DATA
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 1 — Loading & Merging Data")

persistency = pd.read_csv(PERSISTENCY_CSV)
customer    = pd.read_csv(CUSTOMER_CSV)
policy      = pd.read_csv(POLICY_CSV)

# Strip whitespace from column names
for df in [persistency, customer, policy]:
    df.columns = df.columns.str.strip()

# Standardize join key
persistency.rename(columns={"Owner Alpha Id": "OWNER_ALPHA_ID"}, inplace=True)
customer.rename(columns={"Customer Alpha Id": "OWNER_ALPHA_ID"}, inplace=True)

print(f"  Persistency : {persistency.shape[0]:>8,} rows  |  {persistency.shape[1]} cols")
print(f"  Customer    : {customer.shape[0]:>8,} rows  |  {customer.shape[1]} cols")
print(f"  Policy      : {policy.shape[0]:>8,} rows  |  {policy.shape[1]} cols")

# Merge: Persistency + Customer (one-to-one)
merged = pd.merge(persistency, customer, on="OWNER_ALPHA_ID", how="left", suffixes=("", "_cust"))

# Merge: + Policy (one-to-many → one customer, multiple policies)
merged = pd.merge(merged, policy, on="OWNER_ALPHA_ID", how="left", suffixes=("", "_pol"))

print(f"\n  Merged      : {merged.shape[0]:>8,} rows  |  {merged.shape[1]} cols")
print(f"  Unique customers: {merged['OWNER_ALPHA_ID'].nunique():,}")
print(f"  Avg policies per customer: {merged.shape[0] / merged['OWNER_ALPHA_ID'].nunique():.1f}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — DEFINE FEATURES
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 2 — Defining Features")

# All candidate features based on schema
# Grouped by category for clarity
FEATURE_CANDIDATES = {

    # --- DEMOGRAPHICS ---
    "AGE_Range":            "Age bracket of policy owner",
    "Owner_Gender":         "Gender",
    "OWNER_CIVIL_STATUS":   "Civil status (Single, Married, etc.)",
    "EDUC_ATTAINMENT":      "Highest education level",
    "OWNER_ANNUAL_INCOME":  "Annual income",
    "OCC_INDUSTRY":         "Industry / occupation type",
    "OWNER_RES_AREA":       "Residential area",

    # --- BEHAVIOR ---
    "Policy_Freq":          "Number of policies owned",
    "Purchase_Interval":    "Avg days between policy purchases",
    "REGENCY":              "Recency of last transaction",
    "EC_Tag":               "Existing customer tag",
    "New FTM IND":          "First-time buyer indicator",

    # --- PAYMENT ---
    "PAYMENT_MODE_DESC":    "Monthly / Quarterly / Annual",
    "WITH_PAYMODE_CHANGE_IND": "Did they change payment mode?",
    "ANNPREM_PHP":          "Annualized premium (PHP)",
    "MODE_PREM_PHP":        "Premium per billing cycle",

    # --- ENGAGEMENT ---
    "WITH_EMAIL_IND":       "Has email on file",
    "WITH_MOBILE_IND":      "Has mobile on file",
    "WITH_ADDRESS_IND":     "Has address on file",
    "MARKETING_CONSENT":    "Agreed to marketing",
    "DP_CONSENT":           "Data privacy consent given",
    "VITALITY_IND":         "Enrolled in vitality/wellness program",

    # --- RISK SIGNALS ---
    "WITH_COMPLAINT":       "Filed a complaint before",
    "CLAIMS_IND":           "Made a claim",
    "WITH_FREELOOK_IND":    "Cancelled within free-look period",
    "WITH_SURRENDER_IND":   "Surrendered a policy before",
    "WITH_LOAN_IND":        "Took a policy loan",
    "RPU_IND":              "Converted to Reduced Paid-Up",
    "WITH_REQUEST_24":      "Had a service request in last 24 months",
    "MEDRATING":            "Medical risk rating",
    "OCCRATING":            "Occupational risk rating",

    # --- LOYALTY ---
    "PREMCLUB_IND":         "Premier Club member",
    "PREMCLUB_TIER":        "Premier Club tier (Silver/Gold/Platinum)",
    "NEAR_PREMCLUB_IND":    "Near Premier Club qualification",
    "Active_Cust_IND":      "Currently active customer",

    # --- CHANNEL / SEGMENT ---
    "WORKSITE_IND":         "Acquired via worksite channel",
    "OFW_IND":              "Overseas Filipino Worker",
    "PREFERRED_IND":        "High-income / preferred segment",
    "PERSONAL_IND":         "Personal / individual channel",
    "PRIVATE_IND":          "Private segment",
    "Pure_WS_Group":        "Purely worksite customer",
    "Company_Own_IND":      "Company-owned policy",

    # --- PRODUCT ---
    "PRODUCT_CATEGORY":     "Traditional / VUL / Health / Group",
    "PLAN_CODE":            "Specific plan code",
    "PAYMENT_MODE_DESC":    "Payment mode (duplicate — handled below)",
}

# Only keep features that actually exist in the merged dataset
features = [col for col in FEATURE_CANDIDATES.keys() if col in merged.columns]
features = list(dict.fromkeys(features))  # remove duplicates

print(f"\n  Features available in your data: {len(features)} / {len(FEATURE_CANDIDATES)}")
print(f"\n  {'Column':<30} {'Description'}")
print(f"  {'-'*60}")
for col in features:
    desc = FEATURE_CANDIDATES.get(col, "")
    print(f"  {col:<30} {desc}")

missing = [col for col in FEATURE_CANDIDATES.keys()
           if col not in merged.columns and col != "PAYMENT_MODE_DESC"]
if missing:
    print(f"\n  Columns NOT found in your data (skipped):")
    for col in missing:
        print(f"    - {col}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — PREPARE DATA FOR MODEL
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 3 — Preparing Data for Model")

# Drop rows where target is missing
df_model = merged[features + [TARGET]].dropna(subset=[TARGET]).copy()
print(f"  Rows with valid target ({TARGET}): {len(df_model):,}")

# Encode categorical (text) columns to numbers
# XGBoost needs numbers — LabelEncoder converts each unique text to an integer
le_dict = {}
for col in df_model.select_dtypes(include="object").columns:
    if col in features:
        le = LabelEncoder()
        df_model[col] = le.fit_transform(df_model[col].astype(str))
        le_dict[col] = le
        print(f"  Encoded: {col} → {list(le.classes_[:5])} ...")

# XGBoost handles missing values natively — no need to fill them
X = df_model[features]
y = df_model[TARGET].astype(int)

print(f"\n  Class distribution (target = {TARGET}):")
vc = y.value_counts()
for val, count in vc.items():
    label = "Retained (1)" if val == 1 else "Lapsed   (0)"
    pct   = count / len(y) * 100
    bar   = "█" * int(pct / 2)
    print(f"    {label}:  {count:>7,}  ({pct:.1f}%)  {bar}")

# Handle class imbalance
# If 80% retained and 20% lapsed → model ignores lapsed
# scale_pos_weight tells XGBoost to pay MORE attention to lapsed
lapse_count  = (y == 0).sum()
stayed_count = (y == 1).sum()
scale_weight = stayed_count / lapse_count
print(f"\n  Class imbalance ratio (scale_pos_weight): {scale_weight:.2f}")
print(f"  → Model will weight lapsed customers {scale_weight:.1f}x more")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — TRAIN / TEST SPLIT
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 4 — Train / Test Split")

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y       # same lapse ratio in both train and test
)

print(f"  Training set : {len(X_train):>8,} rows  (80%)")
print(f"  Test set     : {len(X_test):>8,} rows  (20%)")
print(f"\n  Lapse rate in training set : {(y_train==0).mean()*100:.1f}%")
print(f"  Lapse rate in test set     : {(y_test==0).mean()*100:.1f}%")
print(f"  ✅ Consistent — stratify worked correctly")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — TRAIN XGBOOST MODEL
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 5 — Training XGBoost Model")

model = XGBClassifier(
    n_estimators=300,         # 300 decision trees
    max_depth=5,              # each tree goes 5 levels deep
    learning_rate=0.05,       # slow learner = more careful = better accuracy
    subsample=0.8,            # use 80% of rows per tree (prevents overfitting)
    colsample_bytree=0.8,     # use 80% of features per tree
    scale_pos_weight=scale_weight,  # handle class imbalance
    eval_metric="auc",
    random_state=42,
    verbosity=0,
)

print("  Training model... (this may take 10-30 seconds)")
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False,
)
print("  ✅ Training complete")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — EVALUATE MODEL
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 6 — Evaluating Model Accuracy")

y_pred       = model.predict(X_test)
y_pred_proba = model.predict_proba(X_test)

auc = roc_auc_score(y_test, y_pred_proba[:, 1])

print(f"\n  AUC Score: {auc:.4f}")
if auc >= 0.90:
    print("  → Excellent model")
elif auc >= 0.80:
    print("  → Good model")
elif auc >= 0.70:
    print("  → Decent model — consider adding more features")
else:
    print("  → Weak model — review features and data quality")

print(f"\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Lapsed (0)", "Retained (1)"]))

# Cross-validation — tests on 5 different splits for more reliable accuracy
print("  Running 5-fold cross-validation...")
cv       = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_aucs  = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
print(f"  CV AUC scores : {[round(s, 4) for s in cv_aucs]}")
print(f"  CV Mean AUC   : {cv_aucs.mean():.4f} ± {cv_aucs.std():.4f}")


# ── ROC Curve Chart ───────────────────────────────────────────────────────────
fpr, tpr, _ = roc_curve(y_test, y_pred_proba[:, 1])
fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(fpr, tpr, color="#2563EB", linewidth=2.5,
        label=f"XGBoost  AUC = {auc:.3f}")
ax.plot([0, 1], [0, 1], color="#9CA3AF", linestyle="--",
        linewidth=1.5, label="Random Guess  AUC = 0.500")
ax.fill_between(fpr, tpr, alpha=0.08, color="#2563EB")
ax.set_xlabel("False Positive Rate\n(Customers flagged as at-risk but actually fine)")
ax.set_ylabel("True Positive Rate\n(At-risk customers correctly caught)")
ax.set_title("ROC Curve — Churn Prediction Model", fontweight="bold", fontsize=13)
ax.legend(fontsize=11)
ax.grid(alpha=0.3)
save_chart(fig, "1_roc_curve.png")


# ── Confusion Matrix ──────────────────────────────────────────────────────────
cm  = confusion_matrix(y_test, y_pred)
fig, ax = plt.subplots(figsize=(6, 5))
ConfusionMatrixDisplay(cm, display_labels=["Lapsed", "Retained"]).plot(
    ax=ax, colorbar=False, cmap="Blues"
)
ax.set_title("Confusion Matrix", fontweight="bold")
save_chart(fig, "2_confusion_matrix.png")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — FEATURE IMPORTANCE
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 7 — Feature Importance")

importance_df = pd.DataFrame({
    "feature":     features,
    "importance":  model.feature_importances_,
    "description": [FEATURE_CANDIDATES.get(f, "") for f in features],
}).sort_values("importance", ascending=False)

print(f"\n  Top 15 most important features:\n")
print(f"  {'Rank':<5} {'Feature':<30} {'Importance':>10}  Description")
print(f"  {'-'*80}")
for i, row in importance_df.head(15).iterrows():
    bar = "█" * int(row["importance"] * 200)
    print(f"  {importance_df.index.get_loc(i)+1:<5} {row['feature']:<30} "
          f"{row['importance']:>10.4f}  {bar}")

# Chart
fig, ax = plt.subplots(figsize=(10, max(6, len(features) * 0.38)))
sorted_imp = importance_df.sort_values("importance", ascending=True)
colors = [
    "#DC2626" if v > sorted_imp["importance"].quantile(0.75) else
    "#F59E0B" if v > sorted_imp["importance"].quantile(0.50) else
    "#94A3B8"
    for v in sorted_imp["importance"]
]
ax.barh(sorted_imp["feature"], sorted_imp["importance"], color=colors, edgecolor="white")
ax.set_title("XGBoost Feature Importance\nRed = High Impact  |  Yellow = Medium  |  Grey = Low",
             fontweight="bold")
ax.set_xlabel("Importance Score")
ax.axvline(sorted_imp["importance"].quantile(0.75), color="#DC2626",
           linestyle="--", alpha=0.5, label="Top 25% threshold")
ax.legend()
plt.tight_layout()
save_chart(fig, "3_feature_importance.png")

# Export importance table
importance_df.to_csv(os.path.join(OUTPUT_DIR, "feature_importance.csv"), index=False)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — SHAP VALUES (WHY did each customer get their score?)
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 8 — SHAP Explainability")

print("  Calculating SHAP values (explains WHY each customer scored high/low)...")
print("  This may take 20-60 seconds...")

explainer   = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# SHAP Summary — shows which features push scores up or down
fig = plt.figure(figsize=(10, 8))
shap.summary_plot(shap_values, X_test, feature_names=features, show=False)
plt.title("SHAP Summary Plot\nWhat drives churn risk up (red) or down (blue)?",
          fontweight="bold", pad=20)
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "4_shap_summary.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("  SHAP summary chart saved")

# SHAP Bar — mean absolute impact per feature
fig = plt.figure(figsize=(10, 6))
shap.summary_plot(shap_values, X_test, feature_names=features,
                  plot_type="bar", show=False)
plt.title("SHAP Mean Impact per Feature", fontweight="bold", pad=20)
plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "5_shap_bar.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("  SHAP bar chart saved")

print("""
  How to read SHAP:
    → Red dots on the right  = that feature VALUE pushes churn risk UP
    → Blue dots on the left  = that feature VALUE pushes churn risk DOWN
    → Width of spread        = how much that feature varies in impact
    → Features at top        = most influential on churn prediction
""")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — SCORE ALL CUSTOMERS
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 9 — Scoring All Customers")

X_all        = df_model[features]
churn_prob   = model.predict_proba(X_all)[:, 0]  # probability of LAPSING (class 0)

# Risk categories
def categorize_risk(score):
    if score >= 0.80:   return "Critical Risk"
    elif score >= 0.60: return "High Risk"
    elif score >= 0.30: return "Medium Risk"
    else:               return "Low Risk"

risk_categories = pd.Categorical(
    [categorize_risk(s) for s in churn_prob],
    categories=["Critical Risk", "High Risk", "Medium Risk", "Low Risk"],
    ordered=True
)

print(f"  Scored {len(churn_prob):,} policy-level records")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 10 — BUILD ENRICHED POLICY-LEVEL TABLE
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 10 — Building Enriched Output Tables")

# All useful columns for the retention team
OUTPUT_COLS = {

    # ── IDENTIFIERS ──────────────────────────────────────────────────────────
    "OWNER_ALPHA_ID":       "Customer ID",
    "POLNUM":               "Policy Number",

    # ── POLICY INFO ──────────────────────────────────────────────────────────
    "PRODUCT_CATEGORY":     "Product Type (Traditional/VUL/Health/Group)",
    "PRODUCT_NAME":         "Product Name",
    "PLAN_NAME":            "Plan Name",
    "POLICY_STATUS":        "Current Policy Status",
    "EFFECTIVE_DT":         "Policy Start Date",
    "PAYMENT_MODE_DESC":    "Payment Mode (Monthly/Annual/etc.)",
    "ANNPREM_PHP":          "Annual Premium (PHP)",
    "MODE_PREM_PHP":        "Premium per Billing Cycle (PHP)",
    "COVANT_PHP":           "Base Coverage Amount (PHP)",
    "OTH_RID_COVANT_PHP":   "Rider Coverage Amount (PHP)",
    "CAMPAIGN_CODE":        "Acquisition Campaign",

    # ── CUSTOMER DEMOGRAPHICS ─────────────────────────────────────────────
    "AGE_Range":            "Age Bracket",
    "Owner_Gender":         "Gender",
    "OWNER_CIVIL_STATUS":   "Civil Status",
    "EDUC_ATTAINMENT":      "Education Level",
    "OWNER_ANNUAL_INCOME":  "Annual Income",
    "OCC_INDUSTRY":         "Industry",
    "OWNER_RES_AREA":       "Residential Area",

    # ── CONTACTABILITY ────────────────────────────────────────────────────
    "WITH_EMAIL_IND":       "Has Email (1=Yes)",
    "WITH_MOBILE_IND":      "Has Mobile (1=Yes)",
    "WITH_ADDRESS_IND":     "Has Address (1=Yes)",
    "MARKETING_CONSENT":    "Marketing Consent (1=Yes)",
    "DP_CONSENT":           "Data Privacy Consent (1=Yes)",

    # ── RISK SIGNALS ──────────────────────────────────────────────────────
    "WITH_COMPLAINT":       "Has Complaint (1=Yes)",
    "CLAIMS_IND":           "Has Claim (1=Yes)",
    "WITH_LOAN_IND":        "Has Policy Loan (1=Yes)",
    "WITH_SURRENDER_IND":   "Has Surrender (1=Yes)",
    "WITH_FREELOOK_IND":    "Has Free-Look Cancel (1=Yes)",
    "RPU_IND":              "Reduced Paid-Up (1=Yes)",
    "MEDRATING":            "Medical Risk Rating",
    "OCCRATING":            "Occupational Risk Rating",

    # ── LOYALTY ───────────────────────────────────────────────────────────
    "PREMCLUB_IND":         "Premier Club Member (1=Yes)",
    "PREMCLUB_TIER":        "Premier Club Tier",
    "NEAR_PREMCLUB_IND":    "Near Premier Club (1=Yes)",
    "Active_Cust_IND":      "Active Customer (1=Yes)",
    "Policy_Freq":          "Total Policies Owned",

    # ── AGENT & BRANCH ────────────────────────────────────────────────────
    "SOLICIT_BSE":          "Agent / BSE Name",
    "BSE_SEGMENT":          "Agent Segment / Tier",
    "BRANCH_NAME":          "Branch Name",
    "BRACH_CODE":           "Branch Code",
    "TRANSACTION_CHANNEL":  "Sales Channel",

    # ── PERSISTENCY ───────────────────────────────────────────────────────
    "Pers 13":              "13-Month Persistency (1=Active, 0=Lapsed)",
    "Pers 25":              "25-Month Persistency (1=Active, 0=Lapsed)",
    "Written_PREM":         "Written Premium at Issuance (PHP)",
    "INPREM_m13":           "In-Force Premium at Month 13 (PHP)",
    "INPREM_m25":           "In-Force Premium at Month 25 (PHP)",
}

available_output_cols = [c for c in OUTPUT_COLS.keys() if c in merged.columns]

# Build base policy-level table
policy_level = merged.loc[df_model.index, available_output_cols].copy()
policy_level.insert(0, "churn_risk_score",    churn_prob.round(4))
policy_level.insert(1, "churn_risk_category", risk_categories)
policy_level.insert(2, "churn_pct",           (churn_prob * 100).round(1))

# Add retention priority rank (1 = most urgent)
policy_level = policy_level.sort_values("churn_risk_score", ascending=False)
policy_level.insert(3, "priority_rank", range(1, len(policy_level) + 1))

# Add retention action guidance
def retention_action(score):
    if score >= 0.80:
        return "CALL TODAY — Critical retention priority"
    elif score >= 0.60:
        return "Call this week — High retention priority"
    elif score >= 0.30:
        return "Email/SMS campaign — Medium priority"
    else:
        return "No immediate action — Monitor"

policy_level.insert(4, "recommended_action",
                    [retention_action(s) for s in churn_prob])

print(f"  Policy-level table built: {len(policy_level):,} rows")


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT 1 — POLICY LEVEL
# One row per policy. Use to identify WHICH specific policy is at risk.
# ─────────────────────────────────────────────────────────────────────────────
out1 = os.path.join(OUTPUT_DIR, "churn_scores_policy_level.csv")
policy_level.to_csv(out1, index=False)
print(f"\n  [1] Policy-level file saved → {out1}")
print(f"      Rows: {len(policy_level):,}  |  Cols: {policy_level.shape[1]}")

print(f"\n  Sample (policy level — top 5 highest risk):")
preview_cols = ["OWNER_ALPHA_ID", "POLNUM", "PRODUCT_CATEGORY",
                "churn_risk_score", "churn_risk_category",
                "recommended_action", "SOLICIT_BSE", "BRANCH_NAME"]
preview_cols = [c for c in preview_cols if c in policy_level.columns]
print(policy_level[preview_cols].head(5).to_string(index=False))


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT 2 — CUSTOMER LEVEL, HIGHEST RISK POLICY
# One row per customer — shows their WORST (highest risk) policy.
# Use this when the retention team calls customers.
# ─────────────────────────────────────────────────────────────────────────────
customer_highest = (
    policy_level
    .sort_values("churn_risk_score", ascending=False)
    .groupby("OWNER_ALPHA_ID", as_index=False)
    .first()
)

# Add total policy count per customer
policy_count = (
    policy_level
    .groupby("OWNER_ALPHA_ID")
    .agg(
        total_policies     = ("churn_risk_score", "count"),
        total_annual_prem  = ("ANNPREM_PHP", "sum"),
        policies_at_risk   = ("churn_risk_category",
                              lambda x: (x.isin(["Critical Risk", "High Risk"])).sum()),
    )
    .reset_index()
)
customer_highest = customer_highest.merge(policy_count, on="OWNER_ALPHA_ID", how="left")
customer_highest = customer_highest.sort_values("churn_risk_score", ascending=False)
customer_highest.insert(0, "customer_priority_rank", range(1, len(customer_highest) + 1))

out2 = os.path.join(OUTPUT_DIR, "churn_scores_customer_highest.csv")
customer_highest.to_csv(out2, index=False)
print(f"\n  [2] Customer-level (highest risk) saved → {out2}")
print(f"      Rows: {len(customer_highest):,}  |  Cols: {customer_highest.shape[1]}")

print(f"\n  Sample (customer level — highest risk policy per customer):")
preview2 = ["OWNER_ALPHA_ID", "total_policies", "policies_at_risk",
            "total_annual_prem", "churn_risk_score",
            "churn_risk_category", "recommended_action",
            "SOLICIT_BSE", "BRANCH_NAME", "PRODUCT_CATEGORY"]
preview2 = [c for c in preview2 if c in customer_highest.columns]
print(customer_highest[preview2].head(5).to_string(index=False))


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT 3 — CUSTOMER LEVEL, AGGREGATED ACROSS ALL POLICIES
# One row per customer — summarizes ALL their policies.
# Use for dashboards, CRM uploads, and overall health view.
# ─────────────────────────────────────────────────────────────────────────────
agg_dict = {
    "churn_risk_score": ["mean", "max", "min"],
}

# Add numeric columns if available
numeric_agg = {
    "ANNPREM_PHP":       "sum",
    "Written_PREM":      "sum",
    "INPREM_m13":        "sum",
    "INPREM_m25":        "sum",
    "COVANT_PHP":        "sum",
    "Policy_Freq":       "max",
    "WITH_COMPLAINT":    "max",
    "WITH_LOAN_IND":     "max",
    "WITH_SURRENDER_IND":"max",
    "CLAIMS_IND":        "max",
    "PREMCLUB_IND":      "max",
    "Active_Cust_IND":   "max",
    "WITH_EMAIL_IND":    "max",
    "WITH_MOBILE_IND":   "max",
    "MARKETING_CONSENT": "max",
    "Pers 13":           "mean",
    "Pers 25":           "mean",
}
for col, func in numeric_agg.items():
    if col in policy_level.columns:
        agg_dict[col] = func

# Add categorical columns — take first/most common
cat_cols = ["AGE_Range", "Owner_Gender", "OWNER_CIVIL_STATUS", "OWNER_ANNUAL_INCOME",
            "SOLICIT_BSE", "BSE_SEGMENT", "BRANCH_NAME", "TRANSACTION_CHANNEL",
            "OWNER_RES_AREA", "OCC_INDUSTRY", "PREMCLUB_TIER",
            "PAYMENT_MODE_DESC", "MEDRATING"]
for col in cat_cols:
    if col in policy_level.columns:
        agg_dict[col] = "first"

customer_avg = policy_level.groupby("OWNER_ALPHA_ID").agg(agg_dict)
customer_avg.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c
                        for c in customer_avg.columns]
customer_avg = customer_avg.reset_index()

# Rename aggregated churn columns clearly
customer_avg.rename(columns={
    "churn_risk_score_mean": "avg_churn_score",
    "churn_risk_score_max":  "max_churn_score",
    "churn_risk_score_min":  "min_churn_score",
}, inplace=True)

# Add policy count
customer_avg["total_policies"] = policy_level.groupby(
    "OWNER_ALPHA_ID")["churn_risk_score"].count().values

# Re-categorize using average score
customer_avg["avg_risk_category"] = customer_avg["avg_churn_score"].apply(categorize_risk)
customer_avg["max_risk_category"] = customer_avg["max_churn_score"].apply(categorize_risk)

# Premium retention ratios (if available)
if "INPREM_m13_sum" in customer_avg.columns and "Written_PREM_sum" in customer_avg.columns:
    customer_avg["prem_retention_13_pct"] = (
        customer_avg["INPREM_m13_sum"] / customer_avg["Written_PREM_sum"] * 100
    ).round(1)
if "INPREM_m25_sum" in customer_avg.columns and "Written_PREM_sum" in customer_avg.columns:
    customer_avg["prem_retention_25_pct"] = (
        customer_avg["INPREM_m25_sum"] / customer_avg["Written_PREM_sum"] * 100
    ).round(1)

customer_avg = customer_avg.sort_values("avg_churn_score", ascending=False)
customer_avg.insert(0, "customer_priority_rank", range(1, len(customer_avg) + 1))

out3 = os.path.join(OUTPUT_DIR, "churn_scores_customer_average.csv")
customer_avg.to_csv(out3, index=False)
print(f"\n  [3] Customer-level (aggregated) saved → {out3}")
print(f"      Rows: {len(customer_avg):,}  |  Cols: {customer_avg.shape[1]}")

print(f"\n  Sample (customer level — aggregated):")
preview3 = ["OWNER_ALPHA_ID", "total_policies", "avg_churn_score",
            "max_churn_score", "avg_risk_category",
            "ANNPREM_PHP_sum", "Pers 13_mean", "BRANCH_NAME", "SOLICIT_BSE"]
preview3 = [c for c in preview3 if c in customer_avg.columns]
print(customer_avg[preview3].head(5).to_string(index=False))


# ─────────────────────────────────────────────────────────────────────────────
# STEP 11 — RISK DISTRIBUTION CHARTS
# ─────────────────────────────────────────────────────────────────────────────
section("STEP 11 — Risk Distribution Charts")

cat_order  = ["Critical Risk", "High Risk", "Medium Risk", "Low Risk"]
cat_colors = ["#DC2626", "#F59E0B", "#2563EB", "#16A34A"]

# Chart A — Policy level distribution
pol_counts = policy_level["churn_risk_category"].value_counts()[cat_order]
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].bar(cat_order, pol_counts.values, color=cat_colors, edgecolor="white", linewidth=1.5)
for bar, val in zip(axes[0].patches, pol_counts.values):
    pct = val / pol_counts.sum() * 100
    axes[0].annotate(f"{val:,}\n({pct:.1f}%)",
                     (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     ha="center", va="bottom", fontweight="bold", fontsize=10)
axes[0].set_title("Churn Risk Distribution\n(Policy Level)", fontweight="bold")
axes[0].set_ylabel("Number of Policies")
axes[0].tick_params(axis="x", rotation=15)

# Chart B — Customer level distribution
cust_counts = customer_highest["churn_risk_category"].value_counts().reindex(
    cat_order, fill_value=0
)
axes[1].bar(cat_order, cust_counts.values, color=cat_colors, edgecolor="white", linewidth=1.5)
for bar, val in zip(axes[1].patches, cust_counts.values):
    pct = val / cust_counts.sum() * 100
    axes[1].annotate(f"{val:,}\n({pct:.1f}%)",
                     (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     ha="center", va="bottom", fontweight="bold", fontsize=10)
axes[1].set_title("Churn Risk Distribution\n(Customer Level — Highest Risk)", fontweight="bold")
axes[1].set_ylabel("Number of Customers")
axes[1].tick_params(axis="x", rotation=15)

plt.suptitle("Churn Risk Scoring Summary", fontsize=14, fontweight="bold", y=1.02)
plt.tight_layout()
save_chart(fig, "6_risk_distribution.png")


# ── Chart C — Revenue at risk by category ────────────────────────────────────
if "ANNPREM_PHP" in policy_level.columns:
    rev_at_risk = policy_level.groupby(
        "churn_risk_category"
    )["ANNPREM_PHP"].sum().reindex(cat_order, fill_value=0) / 1e6

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(cat_order, rev_at_risk.values, color=cat_colors,
                  edgecolor="white", linewidth=1.5)
    for bar, val in zip(bars, rev_at_risk.values):
        ax.annotate(f"₱{val:,.1f}M",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontweight="bold")
    ax.set_title("Annual Premium at Risk by Churn Category\n(PHP Millions)",
                 fontweight="bold")
    ax.set_ylabel("Annual Premium (PHP Millions)")
    ax.tick_params(axis="x", rotation=15)
    plt.tight_layout()
    save_chart(fig, "7_revenue_at_risk.png")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
section("FINAL SUMMARY")

print(f"""
  Model Performance:
    AUC Score          : {auc:.4f}
    CV Mean AUC        : {cv_aucs.mean():.4f} ± {cv_aucs.std():.4f}

  Data:
    Total policies scored   : {len(policy_level):,}
    Unique customers scored : {len(customer_highest):,}

  Risk Category Breakdown (Customer Level):
""")

for cat, color_label in zip(cat_order, ["🔴", "🟠", "🔵", "🟢"]):
    count = (customer_highest["churn_risk_category"] == cat).sum()
    pct   = count / len(customer_highest) * 100
    bar   = "█" * int(pct / 2)
    print(f"    {color_label} {cat:<15} {count:>7,}  ({pct:.1f}%)  {bar}")

print(f"""
  Output Files:
    [1] churn_scores_policy_level.csv
        → One row per policy
        → Use to identify WHICH specific policy is at risk
        → Share with underwriting / product team

    [2] churn_scores_customer_highest.csv
        → One row per customer (worst policy shown)
        → Use for retention team calling list
        → Sorted by priority — call rank 1 first

    [3] churn_scores_customer_average.csv
        → One row per customer (all policies summarized)
        → Use for CRM upload, dashboards, executive reports
        → Includes premium retention ratios

  Charts saved:
    1_roc_curve.png
    2_confusion_matrix.png
    3_feature_importance.png
    4_shap_summary.png
    5_shap_bar.png
    6_risk_distribution.png
    7_revenue_at_risk.png

  Recommended Next Steps:
    1. Sort churn_scores_customer_highest.csv by customer_priority_rank
    2. Filter churn_risk_category = "Critical Risk"
    3. Hand list to retention team — call in rank order
    4. For each call, check WHICH policy is at risk (from file 1)
    5. Check recommended_action column for talking points
    6. Re-run monthly as new data arrives
""")

print("✅ Churn Risk Scoring Complete.")
print(f"   All outputs saved to: {OUTPUT_DIR}/")
