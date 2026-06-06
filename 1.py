# Check nulls for ALL columns, not just _IND ones
null_check = df_customer.isnull().sum().reset_index()
null_check.columns = ["column", "null_count"]
null_check["diff_from_74"] = (null_check["null_count"] - 74).abs()
null_check = null_check[null_check["null_count"] > 0]
print(null_check.sort_values("diff_from_74").head(20))


# The diff likely happened at the Individual Customers step
# Check Company_Own_IND specifically
print(df_customer["Company_Own_IND"].value_counts(dropna=False))








