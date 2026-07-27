import pandas as pd
import reassign_agents as ra


def test_agent_load_counts_unique_customers_not_policies():
    master = pd.DataFrame({
        ra.COL_CUSTOMER: ["C1", "C1", "C2"],
        ra.COL_AGENT: ["A1", "A1", "A1"],
        ra.COL_STATUS: ["Active", "Active", "Active"],
        ra.COL_AGENCY: ["AG1", "AG1", "AG1"],
        ra.COL_UM: ["UM1", "UM1", "UM1"],
    })
    load = ra.build_agent_load(master)
    assert load["A1"] == 2  # 2 unique customers, not 3 policy rows


def test_ucm_um_priority_over_agency():
    ucm = pd.DataFrame({
        ra.UCM_COL_UM: ["UM1", None],
        ra.UCM_COL_AGENCY: [None, "AG1"],
        ra.UCM_COL_AGENT: ["A_um", "A_agency"],
    })
    sake = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})
    ucm_um, ucm_agency = ra.build_candidate_index(ucm)
    sake_um, sake_agency = ra.build_candidate_index(sake)

    pool = ra.get_candidate_pool("UM1", "AG1", None, ucm_um, ucm_agency, sake_um, sake_agency)
    assert pool[0] == ("UCM_UM", ["A_um"])  # UM match must come before agency match


def test_falls_back_to_sake_when_ucm_has_nothing():
    ucm = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})
    sake = pd.DataFrame({
        ra.UCM_COL_UM: ["UM1"], ra.UCM_COL_AGENCY: [None], ra.UCM_COL_AGENT: ["A_sake"],
    })
    ucm_um, ucm_agency = ra.build_candidate_index(ucm)
    sake_um, sake_agency = ra.build_candidate_index(sake)

    pool = ra.get_candidate_pool("UM1", "AG1", None, ucm_um, ucm_agency, sake_um, sake_agency)
    assert pool == [("SAKE_UM", ["A_sake"])]


def test_agent_at_cap_gets_skipped_for_under_cap_peer():
    master = pd.DataFrame({
        ra.COL_CUSTOMER: [f"C{i}" for i in range(100)] + ["C_orphan"],
        ra.COL_AGENT: ["A_full"] * 100 + ["A_full"],
        ra.COL_STATUS: ["Active"] * 100 + [ra.ORPHAN_VALUE],
        ra.COL_AGENCY: ["AG1"] * 101,
        ra.COL_UM: ["UM1"] * 101,
    })
    ucm = pd.DataFrame({
        ra.UCM_COL_UM: ["UM1", "UM1"],
        ra.UCM_COL_AGENCY: [None, None],
        ra.UCM_COL_AGENT: ["A_full", "A_open"],
    })
    sake = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})

    result, summary = ra.reassign(master, ucm, sake)
    orphan_row = result[result[ra.COL_STATUS] == ra.ORPHAN_VALUE].iloc[0]
    assert orphan_row["New_Agent"] == "A_open"  # A_full is at 100, must skip to A_open
    assert orphan_row["Queue_Status"] == ""


def test_everyone_over_cap_gets_queued():
    master = pd.DataFrame({
        ra.COL_CUSTOMER: [f"C{i}" for i in range(100)] + ["C_orphan"],
        ra.COL_AGENT: ["A_full"] * 100 + ["A_full"],
        ra.COL_STATUS: ["Active"] * 100 + [ra.ORPHAN_VALUE],
        ra.COL_AGENCY: ["AG1"] * 101,
        ra.COL_UM: ["UM1"] * 101,
    })
    ucm = pd.DataFrame({
        ra.UCM_COL_UM: ["UM1"], ra.UCM_COL_AGENCY: [None], ra.UCM_COL_AGENT: ["A_full"],
    })
    sake = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})

    result, summary = ra.reassign(master, ucm, sake)
    orphan_row = result[result[ra.COL_STATUS] == ra.ORPHAN_VALUE].iloc[0]
    assert orphan_row["Queue_Status"] == "Queued"
    assert orphan_row["New_Agent"] == "A_full"


def test_sup_name_checked_as_agency_source():
    # agency_name col is missing/blank, but sup_name actually holds an agency name.
    # Should still resolve via the Agency tier using sup_name.
    ucm = pd.DataFrame({
        ra.UCM_COL_UM: [None],
        ra.UCM_COL_AGENCY: ["AG_from_sup"],
        ra.UCM_COL_AGENT: ["A_agency"],
    })
    sake = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})
    ucm_um, ucm_agency = ra.build_candidate_index(ucm)
    sake_um, sake_agency = ra.build_candidate_index(sake)

    pool = ra.get_candidate_pool(None, None, "AG_from_sup", ucm_um, ucm_agency, sake_um, sake_agency)
    assert pool == [("UCM_Agency", ["A_agency"])]


def test_agency_name_and_sup_name_combine_in_same_tier():
    # If both agency_name and sup_name independently match agents in UCM,
    # both should show up in the same UCM_Agency tier (no duplicates).
    ucm = pd.DataFrame({
        ra.UCM_COL_UM: [None, None],
        ra.UCM_COL_AGENCY: ["AG1", "AG_from_sup"],
        ra.UCM_COL_AGENT: ["A_from_agency_col", "A_from_sup_col"],
    })
    sake = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})
    ucm_um, ucm_agency = ra.build_candidate_index(ucm)
    sake_um, sake_agency = ra.build_candidate_index(sake)

    pool = ra.get_candidate_pool(None, "AG1", "AG_from_sup", ucm_um, ucm_agency, sake_um, sake_agency)
    assert len(pool) == 1
    tag, agents = pool[0]
    assert tag == "UCM_Agency"
    assert set(agents) == {"A_from_agency_col", "A_from_sup_col"}


def test_random_pick_among_eligible_in_tier_reaches_all_candidates():
    # 2 eligible agents in the same tier, 1 already at cap. Run many times
    # and confirm both eligible agents get picked (not just one, always).
    master = pd.DataFrame({
        ra.COL_CUSTOMER: [f"C{i}" for i in range(100)] + ["C_orphan"],
        ra.COL_AGENT: ["A_full"] * 100 + ["A_full"],
        ra.COL_STATUS: ["Active"] * 100 + [ra.ORPHAN_VALUE],
        ra.COL_AGENCY: ["AG1"] * 101,
        ra.COL_UM: ["UM1"] * 101,
    })
    ucm = pd.DataFrame({
        ra.UCM_COL_UM: ["UM1", "UM1", "UM1"],
        ra.UCM_COL_AGENCY: [None, None, None],
        ra.UCM_COL_AGENT: ["A_full", "A_open1", "A_open2"],
    })
    sake = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})

    seen = set()
    for _ in range(30):
        result, _ = ra.reassign(master.copy(), ucm, sake)
        orphan_row = result[result[ra.COL_STATUS] == ra.ORPHAN_VALUE].iloc[0]
        seen.add(orphan_row["New_Agent"])

    assert seen == {"A_open1", "A_open2"}  # both eligible agents reachable, A_full never picked


def test_no_candidates_anywhere_is_unresolved():
    master = pd.DataFrame({
        ra.COL_CUSTOMER: ["C1"],
        ra.COL_AGENT: [None],
        ra.COL_STATUS: [ra.ORPHAN_VALUE],
        ra.COL_AGENCY: ["AG_missing"],
        ra.COL_UM: ["UM_missing"],
    })
    empty = pd.DataFrame({ra.UCM_COL_UM: [], ra.UCM_COL_AGENCY: [], ra.UCM_COL_AGENT: []})

    result, summary = ra.reassign(master, empty, empty)
    assert result.iloc[0]["Reassign_Source"] == "Unresolved"
