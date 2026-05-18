# Phase 10 - Power BI Build Guide

This guide converts generated pipeline outputs into the 5 requested dashboard pages.

## Data Sources to Import

Use `Get Data > Text/CSV` and load:
- `data/processed/master_census.csv`
- `data/processed/master_claims.csv`
- `powerbi/data/monthly_trend.csv`
- `powerbi/data/quarterly_summary.csv`
- `powerbi/data/benefit_split.csv`
- `powerbi/data/relationship_age.csv`
- `powerbi/data/age_group_analysis.csv`
- `powerbi/data/pec_diagnosis_top10.csv`
- `powerbi/data/provider_top5.csv`
- `powerbi/data/uw_comparison.csv`
- `powerbi/data/benchmarks.csv`

## Theme

Import theme:
- `powerbi/theme_assignment.json`

Primary colors expected by assignment:
- Primary Red: `#9B1942`
- Navy: `#1F3864`
- White: `#FFFFFF`
- Alternate row gray: `#F2F2F2`

## Recommended Measures (DAX)

```DAX
Total Claims = COUNTROWS(master_claims)
Total Paid USD = SUM(master_claims[paid_amount_usd])
Total Premium USD = SUM(master_census[annual_premium_usd])
Loss Ratio % = DIVIDE([Total Paid USD], [Total Premium USD]) * 100
Cost Per Claim = DIVIDE([Total Paid USD], [Total Claims])
PEC % = DIVIDE(SUM(master_claims[pec_flag]), [Total Claims]) * 100
Oncology Cases = SUM(master_claims[oncology_flag])
Maternity Cases = SUM(master_claims[maternity_flag])
```

## Page-by-Page Build Plan

## 1) Executive Summary

- KPI cards: `Total Claims`, `Total Paid USD`, `Loss Ratio %`, `Cost Per Claim`, `PEC %`
- Text boxes for key findings and recommendations.
- Keep white background, navy headings, primary red emphasis.

## 2) Claims Overview

- Line + clustered column using `monthly_trend.csv`:
  - X: `month_label`
  - Columns: `total_claims`
  - Line: `total_paid_usd`
- Quarterly summary table from `quarterly_summary.csv`
- Donut chart from `benefit_split.csv` (`benefit_type` vs `total_claims`)

## 3) Demographics

- Gauge visuals from `relationship_age.csv` for avg age by relationship.
- Column chart from `age_group_analysis.csv` for claims by age group.
- Combo chart: age group claims and avg cost.

## 4) PEC/Chronic Drilldown

- Horizontal bar: `pec_diagnosis_top10.csv`
  - Axis: `diagnosis_description`
  - Value: `total_claims`
- Apply rank color intent:
  - Rank 1: `#5A5A5A`
  - Rank 2: `#E8A0B0`
  - Rank 3+: `#9B1942`

## 5) Provider & Country Comparison

- Top provider bar chart from `provider_top5.csv`
- Table from `provider_top5.csv` (`total_claims`, `total_paid_usd`, `paid_share_pct`, `avg_cost_per_claim`)
- Grouped comparison chart from `uw_comparison.csv`
- Add benchmark reference lines from `benchmarks.csv`:
  - Loss Ratio: 88%
  - Cost per Claim: 200
  - PEC Ratio: 65%
  - Provider Concentration: 25%

## Export

- Export report to PDF:
  - `File > Export > Export to PDF`
- Keep as:
  - `claims_dashboard.pbix`
  - `Claims_Analysis_Report.pdf`

