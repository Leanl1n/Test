"""
Agency Orphan Reassignment Script
==================================
Reassigns "Agency Orphan" policies to an active agent using a priority
waterfall: UCM file (same UM code -> same agency) then SAKE file
(same UM code -> same agency), respecting a 100-cap of NEW reassignments
per agent made during this run (their existing book of business does not
count toward it), with an overflow "Queued" fallback.

HOW TO USE
----------
1. Edit the CONFIG block below to match your real column names.
2. Point MASTER_PATH / UCM_PATH / SAKE_PATH at your files (.csv or .xlsx).
3. Run: python reassign_agents.py
4. Output written to reassigned_output.xlsx (or .csv) with new columns:
   - New_Agent          : the reassigned agent id (unchanged for non-orphans)
   - Reassign_Source    : 'UCM_UM' | 'UCM_Agency' | 'SAKE_UM' | 'SAKE_Agency' | 'Unresolved' | ''
   - Queue_Status       : 'Queued' or '' 
   Plus an agent_load_summary.csv showing each agent's count of NEW
   reassignments made during this run (not their total book of business).
"""

import pandas as pd
import random
from collections import defaultdict

# ============ CONFIG — EDIT THESE TO MATCH YOUR REAL FILES ============

MASTER_PATH = "masterfile.xlsx"
UCM_PATH = "ucm.xlsx"
SAKE_PATH = "sake.xlsx"
OUTPUT_PATH = "reassigned_output.xlsx"
SUMMARY_PATH = "agent_load_summary.csv"
SOURCE_REPORT_PATH = "reassignment_source_report.csv"
AGENT_REPORT_PATH = "agent_report.csv"

# Masterfile columns
COL_CUSTOMER = "customer_id"
COL_POLICY = "policy_id"
COL_AGENT = "agent_id"
COL_STATUS = "agent_status"          # values like "Active" / "Agency Orphan"
COL_AGENCY = "agency_name"
COL_UM = "um_code"                   # unit manager code on the master row
COL_SUP = "sup_name"                 # supervisor name col — sometimes actually holds an agency name

ORPHAN_VALUE = "Agency Orphan"

# UCM / SAKE file columns (assumed same schema in both files)
UCM_COL_UM = "um_code"
UCM_COL_AGENCY = "agency_name"
UCM_COL_AGENT = "agent_id"

MAX_LOAD = 100

# ========================================================================


def load_data():
    def _read(path):
        return pd.read_excel(path) if str(path).endswith((".xlsx", ".xls")) else pd.read_csv(path)

    master = _read(MASTER_PATH)
    ucm = _read(UCM_PATH)
    sake = _read(SAKE_PATH)
    return master, ucm, sake


def build_agent_load() -> dict:
    """
    Starting load per agent = 0 for everyone. The 100-cap only tracks
    reassignments made DURING this run — an agent's existing book of
    business (their current Active customers) does NOT count toward it.
    The count only starts climbing once we actually reassign an orphan
    policy to them.
    """
    return defaultdict(int)


def build_agent_customer_sets() -> dict:
    """
    agent_id -> set of customer_ids assigned to them DURING this run.
    Used to avoid double-counting a customer when they have multiple
    orphan policies reassigned to the same agent in this same run.
    """
    return defaultdict(set)


def build_candidate_index(df: pd.DataFrame):
    """Return (um_index, agency_index): each maps key -> list of agent_ids."""
    um_index = defaultdict(list)
    agency_index = defaultdict(list)
    for _, row in df.iterrows():
        agent = row[UCM_COL_AGENT]
        um = row.get(UCM_COL_UM)
        agency = row.get(UCM_COL_AGENCY)
        if pd.notna(um):
            um_index[um].append(agent)
        if pd.notna(agency):
            agency_index[agency].append(agent)
    return um_index, agency_index


def build_agency_um_tree(df: pd.DataFrame) -> dict:
    """
    Returns a nested dict mirroring the real file structure:
        {agency_name: {um_code: [agent_id, agent_id, ...]}}

    This is NOT used for the actual reassignment lookups (um_index /
    agency_index above are already flat and O(1), which is what the
    waterfall needs) — it's a separate, human-readable view for auditing:
    "who's under Agency X, broken out by UM" or spotting an agency with
    only one thin UM vs. one with ten.

    Rows missing UM or agency are bucketed under "_NO_UM_" / "_NO_AGENCY_"
    so nothing silently disappears from the tree.
    """
    tree = defaultdict(lambda: defaultdict(list))
    for _, row in df.iterrows():
        agent = row.get(UCM_COL_AGENT)
        if pd.isna(agent):
            continue
        agency_key = row.get(UCM_COL_AGENCY)
        agency_key = agency_key if pd.notna(agency_key) else "_NO_AGENCY_"
        um_key = row.get(UCM_COL_UM)
        um_key = um_key if pd.notna(um_key) else "_NO_UM_"
        tree[agency_key][um_key].append(agent)

    # convert defaultdicts to plain dicts so it prints/serializes cleanly
    return {agency: dict(um_map) for agency, um_map in tree.items()}


def get_candidate_pool(um_code, agency_name, sup_name, ucm_um, ucm_agency, sake_um, sake_agency):
    """
    Returns an ordered list of tiers: [(source_tag, [agent_id, ...]), ...].
    Order matters: earlier tiers are tried first. Each tier's agent list is
    deduped but NOT pre-shuffled — the caller explicitly random-picks among
    whichever agents in a tier are actually eligible (under the cap).

    Both UCM_Agency and SAKE_Agency check agency_name and sup_name TOGETHER
    (merged/parallel) — the SUP column sometimes actually holds an agency
    name instead of a real supervisor name, so both are treated as
    equally-valid agency sources in both files.
    """
    def build_tier_merged(index, keys):
        """Combine agents from ALL keys into one tier."""
        agents = []
        for key in keys:
            if key in index and index[key]:
                agents.extend(index[key])
        return list(set(agents))  # dedupe

    tiers = [
        ("UCM_UM", build_tier_merged(ucm_um, [um_code])),
        ("UCM_Agency", build_tier_merged(ucm_agency, [agency_name, sup_name])),
        ("SAKE_UM", build_tier_merged(sake_um, [um_code])),
        ("SAKE_Agency", build_tier_merged(sake_agency, [agency_name, sup_name])),
    ]
    # Drop empty tiers so the caller doesn't need to check length itself
    return [(tag, agents) for tag, agents in tiers if agents]


def build_agent_report(result: pd.DataFrame) -> pd.DataFrame:
    """
    Per-agent breakdown: how many unique customers they were reassigned
    during this run, whether that hit the 100-cap, and how many of those
    customers were Queued (over-cap fallback).

    Counts UNIQUE CUSTOMERS, not policy rows -- a customer with 2 policies
    landing on the same agent counts once, matching the actual cap logic.
    """
    assigned = result[
        (result["Reassign_Source"] != "") & (result["Reassign_Source"] != "Unresolved")
    ]

    # A customer counts as Queued for an agent if ANY of their policies
    # assigned to that agent were flagged Queued.
    per_customer = (
        assigned.groupby(["New_Agent", COL_CUSTOMER])["Queue_Status"]
        .apply(lambda s: (s == "Queued").any())
        .reset_index(name="Was_Queued")
    )

    report = (
        per_customer.groupby("New_Agent")
        .agg(
            Total_Customers_Handled=("Was_Queued", "size"),
            Queued_Customers=("Was_Queued", "sum"),
        )
        .reset_index()
    )
    report["Not_Queued_Customers"] = report["Total_Customers_Handled"] - report["Queued_Customers"]
    report["At_Cap"] = report["Total_Customers_Handled"] >= MAX_LOAD
    report = report.sort_values("Total_Customers_Handled", ascending=False).reset_index(drop=True)
    return report


def build_source_report(result: pd.DataFrame) -> pd.DataFrame:
    """
    Breaks down every orphan reassignment by WHERE it came from
    (UCM_UM / UCM_Agency / SAKE_UM / SAKE_Agency / Unresolved) crossed
    with whether it was Queued (over-cap fallback) or not.

    UCM_UM and UCM_Agency rows are your priority-pool assignments;
    SAKE_UM / SAKE_Agency are fallback-file assignments; Unresolved
    means no candidate existed anywhere.
    """
    orphans = result[result["Reassign_Source"] != ""].copy()
    orphans["Queue_Status"] = orphans["Queue_Status"].replace("", "Not Queued")
    orphans.loc[orphans["Queue_Status"] != "Queued", "Queue_Status"] = "Not Queued"

    report = (
        orphans.groupby(["Reassign_Source", "Queue_Status"])
        .size()
        .reset_index(name="Count")
        .sort_values(["Reassign_Source", "Queue_Status"])
    )
    return report


def _resolve_pool(pool, agent_load):
    """
    Given a priority-ordered pool of tiers, pick ONE agent:
    - walk tiers in order, random-pick among eligible (under-cap) agents
      in the first tier that has any
    - if nobody anywhere is under the cap, random-pick across the full
      combined pool and flag Queued
    Returns (chosen_agent, chosen_source, queue_status).
    """
    chosen_agent, chosen_source = None, None
    for tag, agents in pool:
        eligible = [a for a in agents if agent_load[a] < MAX_LOAD]
        if eligible:
            chosen_agent = random.choice(eligible)
            chosen_source = tag
            break

    if chosen_agent is not None:
        return chosen_agent, chosen_source, ""

    # Nobody anywhere under cap -> random pick across the full pool, Queued
    all_agents = [(a, tag) for tag, agents in pool for a in agents]
    chosen_agent, chosen_source = random.choice(all_agents)
    return chosen_agent, chosen_source, "Queued"


def _orphan_group_key(row):
    """
    The 'sameness' key used to decide whether two of a customer's orphan
    policies should share ONE reassignment:
      - if UM code exists on the row, group by UM code
      - otherwise, group by sup_name if it exists
      - otherwise, group by agency_name
    Two policies with the same key get resolved together (one agent,
    applied to both). Different keys are resolved independently.

    NOTE: this priority order (sup before agency) is specific to the
    GROUPING decision. It's separate from the actual agent-pool lookup
    in get_candidate_pool(), which checks agency_name and sup_name
    TOGETHER at the same tier when resolving candidates.
    """
    um = row.get(COL_UM)
    if pd.notna(um):
        return ("UM", um)
    sup = row.get(COL_SUP)
    agency = row.get(COL_AGENCY)
    effective_agency = sup if pd.notna(sup) else agency
    return ("AGENCY", effective_agency)


def reassign(master: pd.DataFrame, ucm: pd.DataFrame, sake: pd.DataFrame):
    agent_load = build_agent_load()
    agent_customers = build_agent_customer_sets()  # agent -> set of customer_ids already counted

    ucm_um, ucm_agency = build_candidate_index(ucm)
    sake_um, sake_agency = build_candidate_index(sake)

    n = len(master)
    new_agent_col = [None] * n
    source_col = [""] * n
    queue_col = [""] * n

    # Pass 1: non-orphan rows pass through unchanged
    orphan_positions = []  # positional indices (0..n-1) of orphan rows
    for pos, (_, row) in enumerate(master.iterrows()):
        if row[COL_STATUS] != ORPHAN_VALUE:
            new_agent_col[pos] = row[COL_AGENT]
        else:
            orphan_positions.append(pos)

    if not orphan_positions:
        result = master.copy()
        result["New_Agent"] = new_agent_col
        result["Reassign_Source"] = source_col
        result["Queue_Status"] = queue_col
        summary = pd.Series(agent_load, name="New_Reassignments_This_Run", dtype=object).rename_axis("agent_id").reset_index()
        return result, summary

    # Pass 2: group orphan rows by (customer, waterfall key) so policies
    # that should be "the same" share exactly one resolution/agent.
    orphan_master = master.iloc[orphan_positions].copy()
    orphan_master["_pos"] = orphan_positions  # remember original row position
    orphan_master["_group_key"] = orphan_master.apply(_orphan_group_key, axis=1)

    for customer_id, cust_group in orphan_master.groupby(COL_CUSTOMER, sort=False):
        for group_key, sub_group in cust_group.groupby("_group_key", sort=False):
            first_row = sub_group.iloc[0]
            um_code = first_row.get(COL_UM)
            agency_name = first_row.get(COL_AGENCY)
            sup_name = first_row.get(COL_SUP)

            pool = get_candidate_pool(um_code, agency_name, sup_name, ucm_um, ucm_agency, sake_um, sake_agency)

            if not pool:
                chosen_agent, chosen_source, chosen_queue = None, "Unresolved", ""
            else:
                chosen_agent, chosen_source, chosen_queue = _resolve_pool(pool, agent_load)
                # Count this customer once per agent, even though this
                # group may cover several of their policies.
                if customer_id not in agent_customers[chosen_agent]:
                    agent_customers[chosen_agent].add(customer_id)
                    agent_load[chosen_agent] += 1

            for pos in sub_group["_pos"]:
                new_agent_col[pos] = chosen_agent
                source_col[pos] = chosen_source
                queue_col[pos] = chosen_queue


    result = master.copy()
    result["New_Agent"] = new_agent_col
    result["Reassign_Source"] = source_col
    result["Queue_Status"] = queue_col

    summary = (
        pd.Series(agent_load, name="New_Reassignments_This_Run")
        .rename_axis("agent_id")
        .reset_index()
        .sort_values("New_Reassignments_This_Run", ascending=False)
    )

    return result, summary


def main():
    master, ucm, sake = load_data()
    result, summary = reassign(master, ucm, sake)

    if OUTPUT_PATH.endswith((".xlsx", ".xls")):
        result.to_excel(OUTPUT_PATH, index=False)
    else:
        result.to_csv(OUTPUT_PATH, index=False)

    summary.to_csv(SUMMARY_PATH, index=False)

    source_report = build_source_report(result)
    source_report.to_csv(SOURCE_REPORT_PATH, index=False)

    agent_report = build_agent_report(result)
    agent_report.to_csv(AGENT_REPORT_PATH, index=False)

    # Optional: human-readable Agency -> UM -> [agents] hierarchy, for
    # auditing/debugging (e.g. checking why a particular UM/agency
    # resolved to the agents it did).
    import json
    with open("ucm_agency_um_tree.json", "w") as f:
        json.dump(build_agency_um_tree(ucm), f, indent=2, default=str)
    with open("sake_agency_um_tree.json", "w") as f:
        json.dump(build_agency_um_tree(sake), f, indent=2, default=str)

    print(f"Done. {len(result)} rows processed.")
    print(f"Unresolved rows: {(result['Reassign_Source'] == 'Unresolved').sum()}")
    print(f"Queued rows: {(result['Queue_Status'] == 'Queued').sum()}")
    print(f"Output -> {OUTPUT_PATH}")
    print(f"Agent load summary -> {SUMMARY_PATH}")
    print(f"Source/Queued breakdown -> {SOURCE_REPORT_PATH}")
    print(f"Per-agent report -> {AGENT_REPORT_PATH}")
    print("Agency/UM hierarchy -> ucm_agency_um_tree.json, sake_agency_um_tree.json")


if __name__ == "__main__":
    main()
