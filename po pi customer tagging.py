"""
PO/PI Customer-Level Tagging
-----------------------------
Goal: Tag each policy with whether the underlying customer (owner/insured,
matched across ALL their policies) is "For PO only", "For PI only", or
"For PO and PI".

Input expected: pol_level_info (DataFrame) with at least these columns:
    - POLNUM
    - OWNER_ALPHA_ID
    - INSURED_ALPHA_ID

Output: pol_level_info gets a new column INFORCE_VITALITY_FOR.
"""

import pandas as pd

# ============================================================
# STEP 1: Union-Find (manual, no networkx needed)
# Links Owner ID <-> Insured ID together for every policy row,
# so that IDs belonging to the same real customer end up grouped,
# even if they only connect indirectly through a chain of policies.
# ============================================================

parent = {}

def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]  # path compression
        x = parent[x]
    return x

def union(a, b):
    root_a, root_b = find(a), find(b)
    if root_a != root_b:
        parent[root_a] = root_b


def tag_po_pi(pol_level_info: pd.DataFrame) -> pd.DataFrame:
    """
    Takes pol_level_info (POLNUM, OWNER_ALPHA_ID, INSURED_ALPHA_ID, ...)
    and returns it with a new INFORCE_VITALITY_FOR column, tagged at
    the customer level.
    """

    # ---- Link every Owner ID with its Insured ID, per row ----
    for _, row in pol_level_info.iterrows():
        union(row['OWNER_ALPHA_ID'], row['INSURED_ALPHA_ID'])

    # ---- Assign each ID to its final customer group ----
    customer_map = {id_: find(id_) for id_ in parent}

    pol_level_info = pol_level_info.copy()
    pol_level_info['CUSTOMER_ID'] = pol_level_info['OWNER_ALPHA_ID'].map(customer_map)

    # ============================================================
    # STEP 2: Split each policy into a PO record and a PI record,
    # then stack them into one long list of (ID, role) pairs.
    # ============================================================

    po_records = pol_level_info[['POLNUM', 'OWNER_ALPHA_ID']].copy()
    po_records['ALPHA_ID'] = po_records['OWNER_ALPHA_ID']
    po_records['ROLE'] = 'PO'

    pi_records = pol_level_info[['POLNUM', 'INSURED_ALPHA_ID']].copy()
    pi_records['ALPHA_ID'] = pi_records['INSURED_ALPHA_ID']
    pi_records['ROLE'] = 'PI'

    stacked = pd.concat(
        [po_records[['POLNUM', 'ALPHA_ID', 'ROLE']],
         pi_records[['POLNUM', 'ALPHA_ID', 'ROLE']]],
        ignore_index=True
    )

    stacked['CUSTOMER_ID'] = stacked['ALPHA_ID'].map(customer_map)

    # ============================================================
    # STEP 3: Collapse to one row per customer, listing every role
    # they've played across all their policies, and turn that into
    # the final label.
    # ============================================================

    customer_roles = stacked.groupby('CUSTOMER_ID')['ROLE'].apply(lambda roles: set(roles))

    def label(roles):
        if roles == {'PO', 'PI'}:
            return 'For PO and PI'
        elif roles == {'PO'}:
            return 'For PO only'
        else:
            return 'For PI only'

    customer_roles = customer_roles.apply(label)
    customer_roles.name = 'INFORCE_VITALITY_FOR'

    # ============================================================
    # STEP 4: Map the tag back onto every original policy row.
    # ============================================================

    pol_level_info = pol_level_info.merge(customer_roles, on='CUSTOMER_ID', how='left')

    return pol_level_info


if __name__ == '__main__':
    # ---- Example usage / quick test ----
    sample = pd.DataFrame({
        'POLNUM':          [123, 456, 789, 101, 111, 112, 113],
        'OWNER_ALPHA_ID':  [1001, 1001, 1002, 1002, 1003, 1004, 1005],
        'INSURED_ALPHA_ID':[5002, 5001, 1002, 5005, 1003, 5009, 5007],
    })

    result = tag_po_pi(sample)
    print(result)
