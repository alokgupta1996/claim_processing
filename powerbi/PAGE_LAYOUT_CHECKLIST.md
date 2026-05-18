# Power BI Page Layout Checklist

Use this as a final QA checklist before exporting PDF.

## Page 1 - Executive Summary

- [ ] 5 KPI cards present: Total Claims, Total Paid USD, Loss Ratio %, Cost Per Claim USD, PEC Ratio %.
- [ ] Findings section has 3-4 bullet insights from actual model output.
- [ ] Recommendations section has 3 action items tied to metrics.
- [ ] Title and subtitle match assignment style.

## Page 2 - Claims Overview

- [ ] Combo chart: month-wise claims (columns) + paid USD (line).
- [ ] Quarterly table includes claims, paid, and cost/claim.
- [ ] Benefit split donut includes labels and percentages.
- [ ] Axis labels and values are readable on one screen.

## Page 3 - Demographics

- [ ] Avg age visuals for Employee, Spouse, Child.
- [ ] Age-group claims chart sorted logically by age bucket.
- [ ] Avg cost by age group visible and not clipped.
- [ ] Notes section includes one risk insight.

## Page 4 - PEC/Chronic Drilldown

- [ ] Top 10 diagnosis horizontal bar chart.
- [ ] Rank color rules applied:
- [ ] Rank 1: `#5A5A5A`
- [ ] Rank 2: `#E8A0B0`
- [ ] Rank 3+: `#9B1942`
- [ ] Clinical insights text box references top contributors.

## Page 5 - Provider & Country Comparison

- [ ] Top 5 provider bar chart by paid USD.
- [ ] Provider summary table has claims, paid, share %, avg cost.
- [ ] UW country comparison chart included.
- [ ] Benchmark reference lines added where required.

## Global Formatting and QA

- [ ] Theme imported from `powerbi/theme_assignment.json`.
- [ ] Background white, headings navy, highlights red.
- [ ] No overlapping visuals.
- [ ] No truncated labels.
- [ ] Numeric formats are consistent (USD and %).
- [ ] Filters/slicers work without breaking layout.
- [ ] PDF export renders all pages correctly.

## Final Deliverables Check

- [ ] `claims_dashboard.pbix`
- [ ] `Claims_Analysis_Report.pdf`
- [ ] Backend outputs included (`master_*.csv`, `claims_analytics.db`, `validation_report.json`)

