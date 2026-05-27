# Insurance Analytics — Python Scripts

## Quick Start Guide

-----

## Folder Structure

```
insurance_analysis/
│
├── 00_data_loader.py               ← Shared utility (run first / imported by others)
├── 01_retention_lapse_analysis.py  ← Goal 1: Reduce churn & improve retention
├── 02_crosssell_upsell_targeting.py← Goal 2: Grow revenue (cross-sell & upsell)
├── 03_risk_portfolio_health.py     ← Goal 3: Monitor risk & portfolio health
├── 04_agent_branch_performance.py  ← Goal 4: Improve agent & branch performance
└── README.md                       ← This file
```

-----

## Step 1: Install Required Libraries

```bash
pip install pandas numpy matplotlib scikit-learn
```

-----

## Step 2: Set Your CSV File Paths

Open `00_data_loader.py` and update these three lines to match your actual file paths:

```python
PERSISTENCY_CSV = "customer_persistency.csv"   # ← your Customer Persistency CSV
CUSTOMER_CSV    = "inf_customer.csv"            # ← your INF_Customer CSV
POLICY_CSV      = "inf_policy.csv"              # ← your Inf_Policy CSV
```

**Examples:**

```python
PERSISTENCY_CSV = "C:/Users/you/data/customer_persistency.csv"
CUSTOMER_CSV    = "C:/Users/you/data/inf_customer.csv"
POLICY_CSV      = "C:/Users/you/data/inf_policy.csv"
```

-----

## Step 3: Run the Scripts

Run each script from the same folder using Python:

```bash
# Test data loading first
python 00_data_loader.py

# Run individual analyses
python 01_retention_lapse_analysis.py
python 02_crosssell_upsell_targeting.py
python 03_risk_portfolio_health.py
python 04_agent_branch_performance.py
```

-----

## Output Files

Each script saves its results to a subfolder:

|Script|Output Folder              |What’s Inside                              |
|------|---------------------------|-------------------------------------------|
|01    |`output/retention/`        |Persistency charts, churn scores CSV       |
|02    |`output/crosssell/`        |Candidate list CSV, product charts         |
|03    |`output/risk/`             |Portfolio summary CSV, vintage charts      |
|04    |`output/agent_performance/`|Branch & agent ranking CSVs, quadrant chart|

-----

## What Each Script Does

### 01 — Retention & Lapse Analysis

- Overall 13-month and 25-month persistency rates
- Lapse rates by age, gender, civil status, education
- Payment mode impact on retention
- Digital engagement vs retention
- Complaint & claims correlation
- Premium retention ratio (INPREM / Written_PREM)
- **Churn risk score per customer (Logistic Regression)**

### 02 — Cross-Sell & Upsell Targeting

- Active single-policy holder candidate pool
- Near Premier Club qualifier list
- Purchase interval distribution (timing next offer)
- Product category penetration
- Contactability matrix (email, mobile, address, consent)
- **Scored cross-sell candidate export (CSV)**

### 03 — Risk & Portfolio Health

- Policy status breakdown (pie chart)
- Premium at risk by product category
- Medical & occupational risk rating distribution
- RPU, surrender, loan, and free-look rates
- **Cohort vintage analysis** (persistency by issue year)
- Portfolio value summary (premium, coverage, ANP)

### 04 — Agent & Branch Performance

- Branch persistency rate vs volume
- **Quality vs Volume quadrant scatter** (Stars / At-Risk / Needs Attention)
- Agent composite score ranking (60% quality + 40% volume)
- New vs existing customer mix by branch
- Channel performance (Worksite, OFW, Personal, Preferred)
- Campaign attribution by persistency rate

-----

## Notes

- Scripts automatically skip any column that doesn’t exist in your data — no errors
- All charts are saved as PNG (150 DPI) — ready for presentations
- CSVs are saved alongside charts in each output folder
- The churn model in Script 01 uses logistic regression; upgrade to XGBoost for higher accuracy