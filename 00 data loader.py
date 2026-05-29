"""
00_data_loader.py
-----------------
Utility to load and merge the three insurance CSVs.
Run this first — all other scripts import from it.

TWO MERGE STRATEGIES:
    load_customer_level()  → 1 row per customer  (campaign targeting, cross-sell lists)
    load_policy_level()    → 1 row per policy    (portfolio health, agent performance)

USAGE:
    from 00_data_loader import load_data, load_customer_level, load_policy_level

    # Raw tables
    persistency, customer, policy = load_data()

    # For campaign targeting / cross-sell (Scripts 01, 02)
    merged = load_customer_level()

    # For portfolio health / agent performance (Scripts 03, 04)
    merged = load_policy_level()

TABLE STRUCTURE (based on schema):
    INF_Customer         → 1 row per customer   (no duplicates)
    Customer Persistency → 1 row per policy     (up to 2 rows per customer)
    Inf_Policy           → 1 row per policy     (up to 43 rows per customer)

JOIN KEY:
    Customer Persistency → OWNER_ALPHA_ID
    INF_Customer         → OWNER_ALPHA_ID  (renamed from Customer Alpha Id)
    Inf_Policy           → OWNER_ALPHA_ID
"""

import pandas as pd

# ── File paths ────────────────────────────────────────────────────────────────
PERSISTENCY_CSV = "customer_persistency.csv"
CUSTOMER_CSV    = "inf_customer.csv"
POLICY_CSV      = "inf_policy.csv"

# Columns intentionally dropped before aggregation (not analytical)
PERS_DROP_COLS   = []   # Generated_Date kept — handled in PERS_AGG_MAP
POLICY_DROP_COLS = []   # Generated_Date kept — handled in POLICY_AGG_MAP

# Known aggregation map for Customer Persistency
# Format: output_col_name: (source_col, agg_function)
PERS_AGG_MAP = {
    "Pers_13"       : ("Pers_13",      "max"),
    "Pers_13_count" : ("Pers_13",      "sum"),
    "Pers_25"       : ("Pers_25",      "max"),
    "Pers_25_count" : ("Pers_25",      "sum"),
    "Written_PREM"  : ("Written_PREM", "sum"),
    "INPREM_m13"    : ("INPREM_m13",   "sum"),
    "INPREM_m25"    : ("INPREM_m25",   "sum"),
    "Generated_Date": ("Generated_Date", "first"),  # same across all rows — kept for reference
}

# Known aggregation map for Inf_Policy
POLICY_AGG_MAP = {
    "PRODUCT_CATEGORIES"  : ("PRODUCT_CATEGORY",   "pipe"),
    "PLAN_NAMES"          : ("PLAN_NAME",           "pipe"),
    "PRODUCT_NAMES"       : ("PRODUCT_NAME",        "pipe"),
    "POLICY_STATUSES"     : ("POLICY_STATUS",       "pipe"),
    "ANNPREM_PHP_TOTAL"   : ("ANNPREM_PHP",         "sum"),
    "MODE_PREM_TOTAL"     : ("MODE_PREM_PHP",       "sum"),
    "COVANT_TOTAL"        : ("COVANT_PHP",          "sum"),
    "RIDER_COVANT_TOTAL"  : ("OTH_RID_COVANT_PHP",  "sum"),
    "FIRST_POLICY_DT"     : ("EFFECTIVE_DT",        "min"),
    "INFORCE_POLICY_COUNT": ("POLNUM",              "count"),
    "CAMPAIGN_CODES"      : ("CAMPAIGN_CODE",       "pipe"),
    "PAYMENT_MODES"       : ("PAYMENT_MODE_DESC",   "pipe"),
}


# =============================================================================
# HELPERS
# =============================================================================

def _pipe_join(x):
    return " | ".join(x.dropna().astype(str).unique())


def _check_unhandled_cols(df, agg_map, drop_cols, table_name):
    """
    Warn if any columns in df are not covered by agg_map or drop_cols.
    These columns would be silently dropped during groupby aggregation.
    """
    join_key       = {"OWNER_ALPHA_ID"}
    dropped        = set(c.upper() for c in drop_cols)
    source_cols    = {v[0] for v in agg_map.values()} | join_key

    unhandled = [
        c for c in df.columns
        if c not in source_cols
        and c.upper() not in dropped
        and c != "OWNER_ALPHA_ID"
    ]

    if unhandled:
        print(f"\n    ⚠  WARNING [{table_name}]: The following columns are NOT in the")
        print(f"       aggregation map and will be DROPPED from the merged dataset:")
        for c in unhandled:
            print(f"         - {c}")
        print(f"       → To keep them, add an entry to the AGG_MAP in 00_data_loader.py\n")
    else:
        print(f"    ✓  All {table_name} columns accounted for — nothing will be dropped.")


def _build_agg_dict(df, agg_map):
    """Build a valid agg dict using only columns that exist in df."""
    agg_dict = {}
    pipe_join = _pipe_join
    for out_col, (src_col, func) in agg_map.items():
        if src_col in df.columns:
            agg_dict[out_col] = (src_col, pipe_join if func == "pipe" else func)
    return agg_dict


# =============================================================================
# LOAD RAW TABLES
# =============================================================================

def load_data():
    """
    Load each CSV into a DataFrame.
    Returns (persistency, customer, policy) — raw, unmerged.
    """
    print("=" * 55)
    print("LOADING RAW CSVs")
    print("=" * 55)

    persistency = pd.read_csv(PERSISTENCY_CSV)
    customer    = pd.read_csv(CUSTOMER_CSV)
    policy      = pd.read_csv(POLICY_CSV)

    # Strip whitespace from all column names
    persistency.columns = persistency.columns.str.strip()
    customer.columns    = customer.columns.str.strip()
    policy.columns      = policy.columns.str.strip()

    # Normalize join key to OWNER_ALPHA_ID across all tables
    if "Owner Alpha Id" in persistency.columns:
        persistency.rename(columns={"Owner Alpha Id": "OWNER_ALPHA_ID"}, inplace=True)
    if "Customer Alpha Id" in customer.columns:
        customer.rename(columns={"Customer Alpha Id": "OWNER_ALPHA_ID"}, inplace=True)

    # Normalize Pers column names (schema has "Pers 13" with a space)
    pers_rename = {}
    if "Pers 13" in persistency.columns:
        pers_rename["Pers 13"] = "Pers_13"
    if "Pers 25" in persistency.columns:
        pers_rename["Pers 25"] = "Pers_25"
    if pers_rename:
        persistency.rename(columns=pers_rename, inplace=True)

    print(f"  Persistency : {persistency.shape[0]:,} rows | {persistency.shape[1]} cols "
          f"| max {persistency.groupby('OWNER_ALPHA_ID').size().max()} rows per customer")
    print(f"  Customer    : {customer.shape[0]:,} rows | {customer.shape[1]} cols "
          f"| {customer['OWNER_ALPHA_ID'].duplicated().sum()} duplicates")
    print(f"  Policy      : {policy.shape[0]:,} rows | {policy.shape[1]} cols "
          f"| max {policy.groupby('OWNER_ALPHA_ID').size().max()} rows per customer")

    return persistency, customer, policy


# =============================================================================
# STRATEGY 1 — CUSTOMER LEVEL (1 row per customer)
# Use for: campaign targeting, cross-sell lists, churn scoring (Scripts 01, 02)
# =============================================================================

def load_customer_level():
    """
    Returns a DataFrame with exactly 1 row per customer.

    Steps:
        1. Aggregate Customer Persistency  → 1 row per customer
        2. Aggregate Inf_Policy            → 1 row per customer
        3. LEFT JOIN both aggregates       → to INF_Customer (base table)
    """
    persistency, customer, policy = load_data()

    print("\n" + "=" * 55)
    print("BUILDING CUSTOMER-LEVEL DATASET")
    print("=" * 55)

    # ------------------------------------------------------------------
    # Step 1: Aggregate Customer Persistency → 1 row per customer
    # ------------------------------------------------------------------
    print("\n  Step 1: Aggregating Customer Persistency...")

    # Drop timestamp columns — same value across all rows, not analytical
    persistency.drop(
        columns=[c for c in PERS_DROP_COLS if c in persistency.columns],
        inplace=True
    )

    # Warn about any columns not in the aggregation map
    _check_unhandled_cols(persistency, PERS_AGG_MAP, PERS_DROP_COLS, "Customer Persistency")

    agg_dict = _build_agg_dict(persistency, PERS_AGG_MAP)
    if agg_dict:
        pers_agg = persistency.groupby("OWNER_ALPHA_ID").agg(**agg_dict).reset_index()
    else:
        pers_agg = persistency[["OWNER_ALPHA_ID"]].drop_duplicates()

    print(f"    {len(pers_agg):,} unique customers after aggregation")

    # ------------------------------------------------------------------
    # Step 2: Aggregate Inf_Policy → 1 row per customer
    # ------------------------------------------------------------------
    print("\n  Step 2: Aggregating Inf_Policy...")

    # Filter to In-Force only for category/plan aggregation
    if "POLICY_STATUS" in policy.columns:
        inforce = policy[
            policy["POLICY_STATUS"].astype(str).str.strip().str.lower()
            .isin(["in-force", "inforce", "in force", "active"])
        ].copy()
    else:
        inforce = policy.copy()

    # Drop timestamp columns
    inforce.drop(
        columns=[c for c in POLICY_DROP_COLS if c in inforce.columns],
        inplace=True
    )

    # Warn about any columns not in the aggregation map
    _check_unhandled_cols(inforce, POLICY_AGG_MAP, POLICY_DROP_COLS, "Inf_Policy")

    agg_dict = _build_agg_dict(inforce, POLICY_AGG_MAP)
    if agg_dict:
        pol_agg = inforce.groupby("OWNER_ALPHA_ID").agg(**agg_dict).reset_index()
    else:
        pol_agg = inforce[["OWNER_ALPHA_ID"]].drop_duplicates()

    print(f"    {len(pol_agg):,} unique customers after aggregation")

    # ------------------------------------------------------------------
    # Step 3: LEFT JOIN both aggregates to INF_Customer
    # ------------------------------------------------------------------
    print("\n  Step 3: Joining to INF_Customer (base)...")

    merged = customer.merge(pers_agg, on="OWNER_ALPHA_ID", how="left")
    merged = merged.merge(pol_agg,   on="OWNER_ALPHA_ID", how="left")

    dup_count = merged["OWNER_ALPHA_ID"].duplicated().sum()
    print(f"    Final   : {len(merged):,} rows | {merged.shape[1]} cols")
    if dup_count == 0:
        print(f"    ✓  No duplicate customer IDs — dataset is clean.")
    else:
        print(f"    ⚠  WARNING: {dup_count} duplicate OWNER_ALPHA_IDs found — investigate before use.")

    return merged


# =============================================================================
# STRATEGY 2 — POLICY LEVEL (1 row per policy)
# Use for: portfolio health, agent performance, vintage analysis (Scripts 03, 04)
# =============================================================================

def load_policy_level():
    """
    Returns a DataFrame with 1 row per policy.

    Steps:
        1. Start with Inf_Policy (base — 1 row per policy)
        2. LEFT JOIN INF_Customer → adds demographics to each policy row
        3. LEFT JOIN Persistency (aggregated to customer level first)
           → Pers_13/25 values repeat across all policies of the same customer
           → This is expected — no POLNUM in Persistency to match at policy level
    """
    persistency, customer, policy = load_data()

    print("\n" + "=" * 55)
    print("BUILDING POLICY-LEVEL DATASET")
    print("=" * 55)

    # Aggregate persistency to customer level first (can't match at policy level)
    agg_dict = _build_agg_dict(persistency, PERS_AGG_MAP)
    if agg_dict:
        pers_agg = persistency.groupby("OWNER_ALPHA_ID").agg(**agg_dict).reset_index()
    else:
        pers_agg = persistency[["OWNER_ALPHA_ID"]].drop_duplicates()

    print(f"\n  Base: Inf_Policy ({len(policy):,} rows)")

    merged = policy.merge(customer, on="OWNER_ALPHA_ID", how="left", suffixes=("", "_cust"))
    print(f"  After + Customer    : {len(merged):,} rows  (should match Policy count: {len(policy):,})")

    merged = merged.merge(pers_agg, on="OWNER_ALPHA_ID", how="left", suffixes=("", "_pers"))
    print(f"  After + Persistency : {len(merged):,} rows  (should still match Policy count: {len(policy):,})")

    if len(merged) != len(policy):
        print(f"\n  ⚠  WARNING: Row count changed! Expected {len(policy):,}, got {len(merged):,}.")
        print(f"     INF_Customer likely has duplicate OWNER_ALPHA_IDs — investigate before use.")
    else:
        print(f"\n  ✓  Row count stable — dataset is clean.")

    print(f"\n  Final: {len(merged):,} rows | {merged.shape[1]} cols")
    return merged


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    print("\n── Customer-Level Test ──")
    cust_df = load_customer_level()
    print(f"\nColumns ({len(cust_df.columns)}):")
    for c in cust_df.columns:
        print(f"  {c}")

    print("\n── Policy-Level Test ──")
    pol_df = load_policy_level()
    print(f"\nColumns ({len(pol_df.columns)}):")
    for c in pol_df.columns:
        print(f"  {c}")
