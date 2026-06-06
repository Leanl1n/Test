# Check what's close to 74
exclusion_check = {}

# Nulls
for col in df_customer.columns:
    null_count = df_customer[col].isna().sum()
    if null_count > 0:
        exclusion_check[f"{col} nulls"] = null_count

# Indicator columns = 1
indicator_cols = [col for col in df_customer.columns if col.endswith("_IND")]
for col in indicator_cols:
    exclusion_check[f"{col} = 1"] = (df_customer[col] == 1).sum()

# Print sorted — closest to 74 at top
import pandas as pd
check_df = pd.DataFrame.from_dict(exclusion_check, orient="index", columns=["count"])
check_df["diff_from_74"] = (check_df["count"] - 74).abs()
print(check_df.sort_values("diff_from_74").head(20))
