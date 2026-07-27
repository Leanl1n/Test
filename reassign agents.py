"""
Agency Orphan Reassignment Script
==================================
Reassigns "Agency Orphan" policies to an active agent using a priority
waterfall: UCM file (same UM code -> same agency) then SAKE file
(same UM code -> same agency), respecting a 100-policy cap per agent,
with an overflow "Queued" fallback.

HOW TO USE
----------
1. Edit the CONFIG block below to match your real column names.
2. Point MASTER_PATH / UCM_PATH / SAKE_PATH at your files (.csv or .xlsx).
3. Run: python reassign_agents.py
4. Output written to reassigned_output.xlsx (or .csv) with new columns:
   - New_Agent          : the reassigned agent id (unchanged for non-orphans)
   - Reassign_Source    : 'UCM_UM' | 'UCM_Agency' | 'SAKE_UM' | 'SAKE_Agency' | 'Unresolved' | ''
   - Queue_Status       : 'Queued' or '' 
   Plus an agent_load_summary.csv showing each agent's final handled count.
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


def build_agent_load(master: pd.DataFrame) -> dict:
    """
    Starting load per agent = count of UNIQUE CUSTOMERS in the masterfile,
    not policy rows (a customer can have multiple policies with the same
    agent, and that should only count once toward the 100 cap).
    """
    load = defaultdict(int)
    counts = master.drop_duplicates(subset=[COL_AGENT, COL_CUSTOMER])[COL_AGENT].value_counts()
    for agent, cnt in counts.items():
        load[agent] = int(cnt)
    return load


def build_agent_customer_sets(master: pd.DataFrame) -> dict:
    """agent_id -> set of customer_ids currently assigned, used to avoid
    double-counting a customer when they have multiple orphan policies
    reassigned to the same agent in this same run."""
    sets = defaultdict(set)
    for agent, cust in zip(master[COL_AGENT], master[COL_CUSTOMER]):
        sets[agent].add(cust)
    return sets


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


def get_candidate_pool(um_code, agency_name, sup_name, ucm_um, ucm_agency, sake_um, sake_agency):
    """
    Returns an ordered list of tiers: [(source_tag, [agent_id, ...]), ...].
    Order matters: earlier tiers are tried first. Each tier's agent list is
    deduped but NOT pre-shuffled — the caller explicitly random-picks among
    whichever agents in a tier are actually eligible (under the cap).

    sup_name is checked against the agency index at the SAME priority tier
    as agency_name — the SUP column sometimes actually holds an agency
    name instead of a real supervisor name, so we treat it as an extra
    agency-name source rather than a separate tier.
    """
    def build_tier(index, keys):
        agents = []
        for key in keys:
            if key in index and index[key]:
                agents.extend(index[key])
        return list(set(agents))  # dedupe

    tiers = [
        ("UCM_UM", build_tier(ucm_um, [um_code])),
        ("UCM_Agency", build_tier(ucm_agency, [agency_name, sup_name])),
        ("SAKE_UM", build_tier(sake_um, [um_code])),
        ("SAKE_Agency", build_tier(sake_agency, [agency_name, sup_name])),
    ]
    # Drop empty tiers so the caller doesn't need to check length itself
    return [(tag, agents) for tag, agents in tiers if agents]


def reassign(master: pd.DataFrame, ucm: pd.DataFrame, sake: pd.DataFrame):
    agent_load = build_agent_load(master)
    agent_customers = build_agent_customer_sets(master)  # agent -> set of customer_ids already counted

    ucm_um, ucm_agency = build_candidate_index(ucm)
    sake_um, sake_agency = build_candidate_index(sake)

    new_agent_col = []
    source_col = []
    queue_col = []

    for _, row in master.iterrows():
        if row[COL_STATUS] != ORPHAN_VALUE:
            # Non-orphan rows pass through unchanged
            new_agent_col.append(row[COL_AGENT])
            source_col.append("")
            queue_col.append("")
            continue

        um_code = row.get(COL_UM)
        agency_name = row.get(COL_AGENCY)
        sup_name = row.get(COL_SUP)
        customer_id = row[COL_CUSTOMER]

        pool = get_candidate_pool(um_code, agency_name, sup_name, ucm_um, ucm_agency, sake_um, sake_agency)

        if not pool:
            # No candidates anywhere -> flag for manual review
            new_agent_col.append(None)
            source_col.append("Unresolved")
            queue_col.append("")
            continue

        # Walk tiers in priority order. Within the first tier that has ANY
        # agent under the cap, randomly pick among just those eligible agents.
        chosen_agent, chosen_source = None, None
        for tag, agents in pool:
            eligible = [a for a in agents if agent_load[a] < MAX_LOAD]
            if eligible:
                chosen_agent = random.choice(eligible)
                chosen_source = tag
                break

        if chosen_agent is not None:
            queue_col.append("")
        else:
            # Nobody in any tier is under the cap -> random pick across the
            # full combined pool (all tiers), tag Queued.
            all_agents = [(a, tag) for tag, agents in pool for a in agents]
            chosen_agent, chosen_source = random.choice(all_agents)
            queue_col.append("Queued")

        # Only increment the load if this customer isn't already counted
        # for this agent (handles customers with multiple orphan policies
        # landing on the same agent in this same run).
        if customer_id not in agent_customers[chosen_agent]:
            agent_customers[chosen_agent].add(customer_id)
            agent_load[chosen_agent] += 1

        new_agent_col.append(chosen_agent)
        source_col.append(chosen_source)

    master = master.copy()
    master["New_Agent"] = new_agent_col
    master["Reassign_Source"] = source_col
    master["Queue_Status"] = queue_col

    summary = (
        pd.Series(agent_load, name="Final_Handled_Count")
        .rename_axis("agent_id")
        .reset_index()
        .sort_values("Final_Handled_Count", ascending=False)
    )

    return master, summary


def main():
    master, ucm, sake = load_data()
    result, summary = reassign(master, ucm, sake)

    if OUTPUT_PATH.endswith((".xlsx", ".xls")):
        result.to_excel(OUTPUT_PATH, index=False)
    else:
        result.to_csv(OUTPUT_PATH, index=False)

    summary.to_csv(SUMMARY_PATH, index=False)

    print(f"Done. {len(result)} rows processed.")
    print(f"Unresolved rows: {(result['Reassign_Source'] == 'Unresolved').sum()}")
    print(f"Queued rows: {(result['Queue_Status'] == 'Queued').sum()}")
    print(f"Output -> {OUTPUT_PATH}")
    print(f"Agent load summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
