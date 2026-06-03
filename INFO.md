# 📋 INFO — EDA Flow & Business Questions

**Project:** Customer Persistency & Campaign Analysis  
**Analyst Role:** Campaign Analyst  
**Last Updated:** June 2026

-----

## Overview

This EDA connects three tables to give a 360° view of the in-force customer book:

```
Customer Persistency  ──┐
                         ├──► Merged on Owner/Customer Alpha ID ──► Analysis
INF_Customer          ──┤
                         │
Inf_Policy            ──┘
```

The goal is to answer **campaign, retention, and customer value questions** without needing a model — just clean, structured exploration.

-----

## Section-by-Section Flow

### Section 1 — Load Data

Load the three source tables. Replace sample data with your actual CSV or DB connection.

**Tables joined on:**

- `Customer Persistency.Owner_Alpha_Id`
- `INF_Customer.Customer_Alpha_Id`
- `Inf_Policy.OWNER_ALPHA_ID`

-----

### Section 2 — Merge Tables

Single flat table for analysis. All joins are **left joins** from Customer Persistency as the base.

-----

### Section 3 — Data Health Check

> *Is the data usable?*

- How many columns have missing values and how bad is it?
- What are the data types — are dates parsed, are flags numeric?
- Basic descriptive stats on premium and coverage columns.

-----

### Section 4 — Persistency Overview

> *Are customers staying?*

- What % of policies are still active at **13 months**?
- What % are still active at **25 months**?
- How many have lapsed vs retained at each milestone?

**Columns used:** `Pers_13`, `Pers_25`

-----

### Section 5 — Premium Retention Analysis

> *How much of our written premium are we keeping?*

- **13-Month Retention Ratio** = `INFPREM_m13 / Written_PREM`
- **25-Month Retention Ratio** = `INFPREM_m25 / Written_PREM`
- Distribution of retention ratios — are most policies above or below 100% retention?

**Columns used:** `Written_PREM`, `INFPREM_m13`, `INFPREM_m25`

-----

### Section 6 — Persistency by Key Segments

> *Who retains better — and who doesn’t?*

Breaks down persistency rates by:

|Dimension          |Business Question                                                 |
|-------------------|------------------------------------------------------------------|
|Age Range          |Do older customers stay longer?                                   |
|Gender             |Is there a retention gap by gender?                               |
|Product Category   |Which products (Traditional, VUL, Health) have the best retention?|
|Payment Mode       |Do annual payers persist better than monthly?                     |
|Transaction Channel|Which channel produces the most loyal customers?                  |

**Columns used:** `AGE_Range`, `Owner_Gender`, `PRODUCT_CATEGORY`, `PAYMENT_MODE_DESC`, `TRANSACTION_CHANNEL`

-----

### Section 7 — Campaign Performance

> *Which campaigns produce the best business — volume AND quality?*

For each `CAMPAIGN_CODE`:

- How many policies did it generate?
- What is the 13 and 25-month persistency rate?
- What is the total and average written premium?
- What is the average premium retention at 13 months?

A campaign with high policy count but low persistency is generating poor-quality business.

**Columns used:** `CAMPAIGN_CODE`, `Pers_13`, `Pers_25`, `Written_PREM`, `Prem_Retention_13`

-----

### Section 8 — Customer Segments

> *Do certain customer types persist more?*

Compares persistency rates across:

- **New vs Existing customers** (`EC_Tag`) — does prior relationship drive retention?
- **Premier Club members** (`PREMCLUB_IND`) — do loyalty program members stay longer?
- **First-Time Buyers** (`New_FTM_IND`) — are new-to-insurance customers riskier?

-----

### Section 9 — Contactability & Consent

> *Does being reachable improve retention?*

Compares persistency for customers who have vs don’t have:

- Email on file (`WITH_EMAIL_IND`)
- Mobile number on file (`WITH_MOBILE_IND`)
- Marketing consent given (`MARKETING_CONSENT`)

**Hypothesis:** Contactable customers receive servicing touchpoints that reduce lapse.

-----

### Section 10 — Branch & Agent Performance

> *Who are the top-performing branches and agents?*

- **Branch leaderboard** — ranked by Pers 13 rate and total written premium
- **Agent leaderboard** — top 15 agents with at least 5 policies, ranked by Pers 13 rate

Filters out agents with fewer than 5 policies to avoid small-sample noise.

**Columns used:** `BRANCH_NAME`, `SOLICIT_BSE`, `Pers_13`, `Pers_25`, `Written_PREM`

-----

### Section 11 — Policy Volume Over Time

> *When was business written, and is there a trend?*

- Monthly count of new policies issued
- Monthly total written premium
- Dual-axis chart to spot seasonality or campaign spikes

**Columns used:** `EFFECTIVE_DT`, `POLNUM`, `Written_PREM`

-----

### Section 12 — Summary Table by Product Category

> *Which products are performing across all dimensions?*

A single heatmap-styled table showing per product:

- Policy count and active customer count
- Pers 13 and Pers 25 rates
- Average written premium
- Premium retention at 13 and 25 months

Color-coded green (good) to red (bad) on persistency columns.

-----

### Section 13 — ANP Analysis

> *Which campaigns, agents, and customers generate the most new business value?*

ANP (Annualized New Premium) measures the standardized value of new business written — not just the count of policies.

#### 13a — Campaign Quality

> *Which campaign brings real value, not just volume?*

Compares campaigns on Total ANP and Avg ANP per policy alongside persistency. A campaign can rank high on policy count but low on ANP — that’s a quality issue.

#### 13b — ANP vs Persistency

> *Do high-value policies actually stay?*

Buckets ANP into quartile tiers (Low / Mid / High / Top) and compares persistency rates per tier. Identifies if expensive policies lapse at the same rate as cheap ones.

#### 13c — Agent Volume vs Quality

> *Who sells a lot AND sells well?*

Scatter plot of Total ANP (x) vs Persistency Rate (y) per agent. Bubble size = number of policies. The top-right quadrant = your star agents.

#### 13d — ANP by Channel, Product & Segment

> *Where does high-value business come from?*

- Average ANP by transaction channel (Agency, Bancassurance, Worksite, Digital)
- Average ANP by product category
- Average ANP for new vs existing customers

#### 13e — Customer Value Matrix

> *Who are your most valuable customers for upsell and Premier Club targeting?*

A heatmap crossing **ANP tier** (Low / Mid / High) with **Policy Frequency** (1 / 2 / 3+ policies). Customers in the High ANP + 3+ Policies cell are your top retention and upsell targets.

-----

## Full Question Index

|# |Business Question                                     |Section|
|--|------------------------------------------------------|-------|
|1 |Are customers staying at 13 months?                   |4      |
|2 |Are customers staying at 25 months?                   |4      |
|3 |How much written premium are we retaining?            |5      |
|4 |Which age group retains best?                         |6      |
|5 |Which product has the best persistency?               |6      |
|6 |Do annual payers persist more than monthly?           |6      |
|7 |Which channel produces the most loyal customers?      |6      |
|8 |Which campaigns drive the most policies?              |7      |
|9 |Which campaigns have the best retention quality?      |7      |
|10|Do existing customers retain better than new?         |8      |
|11|Does Premier Club membership drive retention?         |8      |
|12|Does contactability (email/mobile) affect lapse?      |9      |
|13|Which branches are top performers?                    |10     |
|14|Which agents sell quality vs just volume?             |10     |
|15|Is there seasonality in policy issuance?              |11     |
|16|Which products perform across all KPIs?               |12     |
|17|Which campaign generates the highest ANP?             |13a    |
|18|Do high-ANP policies actually stay?                   |13b    |
|19|Who are the star agents (ANP + persistency)?          |13c    |
|20|Which channel/product produces highest-value business?|13d    |
|21|Who are the top customers for upsell targeting?       |13e    |

-----

## Column Reference (Key Fields Used)

|Column                                |Table                     |Used For                      |
|--------------------------------------|--------------------------|------------------------------|
|`Owner_Alpha_Id` / `Customer_Alpha_Id`|Persistency / INF_Customer|Join key                      |
|`Pers_13`, `Pers_25`                  |Persistency               |Retention target variables    |
|`Written_PREM`                        |Persistency               |Baseline premium at issuance  |
|`INFPREM_m13`, `INFPREM_m25`          |Persistency               |Retained premium at milestones|
|`ANP`                                 |Persistency               |New business value measure    |
|`EC_Tag`, `New_FTM_IND`               |INF_Customer              |New vs existing segmentation  |
|`Active_Cust_IND`                     |INF_Customer              |Current activity status       |
|`Policy_Freq`                         |INF_Customer              |Multi-policy ownership        |
|`AGE_Range`, `Owner_Gender`           |INF_Customer              |Demographics                  |
|`PREMCLUB_IND`, `PREMCLUB_TIER`       |INF_Customer              |Loyalty program status        |
|`WITH_EMAIL_IND`, `WITH_MOBILE_IND`   |INF_Customer              |Contactability                |
|`MARKETING_CONSENT`                   |INF_Customer              |Reachability for campaigns    |
|`TRANSACTION_CHANNEL`                 |INF_Customer              |Acquisition channel           |
|`SOLICIT_BSE`, `BRANCH_NAME`          |INF_Customer              |Agent and branch attribution  |
|`CAMPAIGN_CODE`                       |Inf_Policy                |Campaign attribution          |
|`PRODUCT_CATEGORY`, `PLAN_NAME`       |Inf_Policy                |Product segmentation          |
|`PAYMENT_MODE_DESC`                   |Inf_Policy                |Payment frequency             |
|`EFFECTIVE_DT`                        |Inf_Policy                |Policy issue date / vintage   |
|`ANNPREM_PHP`, `COVANT_PHP`           |Inf_Policy                |Premium and coverage amounts  |