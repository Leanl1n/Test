
import pandas as pd

# Load both CSVs
raw = pd.read_csv('raw.csv', dtype=str)
sending_list = pd.read_csv('sending_list.csv', dtype=str)

# Get the customer IDs from the sending list
sending_ids = sending_list['customer_alpha_id'].unique()

# Filter raw CSV to only those customers
filtered = raw[raw['customer_alpha_id'].isin(sending_ids)].copy()

# Check both consent flags
filtered['consent_ok'] = (
    filtered['marketing_consent'].str.strip().str.upper() == 'Y'
) & (
    filtered['BC_mkgc'].str.strip().str.upper() == 'Y'
)

# Split results
valid = filtered[filtered['consent_ok']]
invalid = filtered[~filtered['consent_ok']]

print(f"Total in sending list: {len(sending_ids)}")
print(f"Found in raw CSV: {len(filtered)}")
print(f"Both consents = Y: {len(valid)}")
print(f"Missing/invalid consent: {len(invalid)}")

# Export results
valid.to_csv('valid_consent.csv', index=False)
invalid.to_csv('invalid_consent.csv', index=False)
