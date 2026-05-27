"""
00_data_loader.py
-----------------
Utility to load and merge the three insurance CSVs.
Run this first — all other scripts import from it.

USAGE:
    from data_loader import load_data, load_merged
    persistency, customer, policy = load_data()
    merged = load_merged()
"""

import pandas as pd
import os

# ── File paths ────────────────────────────────────────────────────────────────
# Update these to point to your actual CSV file paths
PERSISTENCY_CSV = "customer_persistency.csv"   # Customer Persistency table
CUSTOMER_CSV    = "inf_customer.csv"            # INF_Customer table
POLICY_CSV      = "inf_policy.csv"              # Inf_Policy table


def load_data():
    """Load each CSV into a DataFrame. Returns (persistency, customer, policy)."""
    print("Loading CSVs...")

    persistency = pd.read_csv(PERSISTENCY_CSV)
    customer    = pd.read_csv(CUSTOMER_CSV)
    policy      = pd.read_csv(POLICY_CSV)

    # Standardize join key column names to a common name
    persistency.rename(columns=lambda c: c.strip(), inplace=True)
    customer.rename(columns=lambda c: c.strip(), inplace=True)
    policy.rename(columns=lambda c: c.strip(), inplace=True)

    # Normalize the join key to uppercase in all tables
    # Persistency uses "Owner Alpha Id", Customer uses "Customer Alpha Id",
    # Policy uses "OWNER_ALPHA_ID" — we align them all to OWNER_ALPHA_ID
    if "Owner Alpha Id" in persistency.columns:
        persistency.rename(columns={"Owner Alpha Id": "OWNER_ALPHA_ID"}, inplace=True)
    if "Customer Alpha Id" in customer.columns:
        customer.rename(columns={"Customer Alpha Id": "OWNER_ALPHA_ID"}, inplace=True)

    print(f"  Persistency: {persistency.shape[0]:,} rows, {persistency.shape[1]} cols")
    print(f"  Customer:    {customer.shape[0]:,} rows, {customer.shape[1]} cols")
    print(f"  Policy:      {policy.shape[0]:,} rows, {policy.shape[1]} cols")

    return persistency, customer, policy


def load_merged():
    """
    Merge all three tables into one wide DataFrame.
    Join key: OWNER_ALPHA_ID
    """
    persistency, customer, policy = load_data()

    # Step 1: Persistency + Customer (one-to-one on OWNER_ALPHA_ID)
    merged = pd.merge(persistency, customer, on="OWNER_ALPHA_ID", how="left", suffixes=("", "_cust"))

    # Step 2: Add Policy (one customer may have multiple policies — left join)
    merged = pd.merge(merged, policy, on="OWNER_ALPHA_ID", how="left", suffixes=("", "_pol"))

    print(f"\nMerged dataset: {merged.shape[0]:,} rows, {merged.shape[1]} cols")
    return merged


if __name__ == "__main__":
    persistency, customer, policy = load_data()
    merged = load_merged()
    print("\nColumn list (merged):")
    for col in merged.columns:
        print(f"  {col}")
