# 📊 EDA — Customer Persistency & Campaign Analysis

**Role:** Campaign Analyst  
**Domain:** Insurance — In-Force Portfolio  
**Tables:** Customer Persistency · INF_Customer · Inf_Policy

-----

## What Is This?

This project is an Exploratory Data Analysis (EDA) notebook built for campaign analysts working on an insurance in-force book. It helps you understand **who your customers are, whether they stay, and which campaigns, agents, and products drive the most value.**

-----

## Files

|File                        |Description                                                 |
|----------------------------|------------------------------------------------------------|
|`EDA_Campaign_Analyst.ipynb`|Main analysis notebook — run this                           |
|`README.md`                 |This file — start here                                      |
|`INFO.md`                   |Detailed flow, business questions answered, and column guide|

-----

## How to Run

1. Open `EDA_Campaign_Analyst.ipynb` in Jupyter or VS Code
1. Go to **Section 1 — Load Data** and replace the sample data block with your actual file paths:
   
   ```python
   persistency = pd.read_csv('your_persistency_file.csv')
   customers   = pd.read_csv('your_inf_customer_file.csv')
   policies    = pd.read_csv('your_inf_policy_file.csv')
   ```
1. Run all cells top to bottom (`Kernel > Restart & Run All`)

-----

## Requirements

```
pandas
numpy
matplotlib
seaborn
```

Install with:

```bash
pip install pandas numpy matplotlib seaborn
```

-----

## Key Outputs

- Persistency rates at 13 and 25 months
- Premium retention ratios
- Campaign quality rankings (count + ANP + persistency)
- Agent volume vs quality scatter
- Customer value matrix (ANP × policy frequency)
- Branch leaderboard
- Monthly issuance trend

-----

> For the full business question breakdown, see **INFO.md**.