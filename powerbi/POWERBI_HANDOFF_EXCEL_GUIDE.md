# Power BI Handoff and Excel Usage Guide

This guide explains:
1. How to use the pipeline-generated Power BI handoff package.
2. How to use Excel files in Power BI Desktop (if needed by client workflow).

## 1) Recommended Handoff Flow (CSV + PBIX Build Package)

This project generates Power BI-ready tables and packaging assets through pipeline run modes.

Use one of:
- Streamlit UI: `Power BI Handoff (PDF + CSV + PBIX build package)`
- CLI: `python src/main.py --run-mode powerbi_handoff --pbix-file-name claims_dashboard.pbix`
- API: `run_mode=powerbi_handoff`

After run, check:
- `outputs/<run_label>/powerbi_handoff/data/` (all CSV tables)
- `outputs/<run_label>/powerbi_handoff/docs/` (theme + page guide + DAX + QA checklist)
- `outputs/<run_label>/powerbi_handoff/PBIX_BUILD_INSTRUCTIONS.md`

## 2) Build the PBIX from Handoff Package

1. Open **Power BI Desktop**.
2. Go to **Get Data > Text/CSV**.
3. Import all files from:
   - `outputs/<run_label>/powerbi_handoff/data/`
4. Import theme:
   - `outputs/<run_label>/powerbi_handoff/docs/theme_assignment.json`
5. Add measures from:
   - `outputs/<run_label>/powerbi_handoff/docs/DAX_MEASURES.md`
6. Build pages using:
   - `outputs/<run_label>/powerbi_handoff/docs/PHASE10_PBI_BUILD_GUIDE.md`
7. Validate with:
   - `outputs/<run_label>/powerbi_handoff/docs/PAGE_LAYOUT_CHECKLIST.md`
8. Save as:
   - `claims_dashboard.pbix`

## 3) Using Excel in Power BI (Alternative Path)

If stakeholders require Excel-based import instead of CSV:

1. Create an Excel workbook (example: `powerbi_input.xlsx`).
2. Create one sheet per generated table (for example):
   - `master_census`
   - `master_claims`
   - `monthly_trend`
   - `quarterly_summary`
   - `benefit_split`
   - `relationship_age`
   - `age_group_analysis`
   - `pec_diagnosis_top10`
   - `provider_top5`
   - `uw_comparison`
   - `benchmarks`
3. Copy the data from generated CSVs into matching sheets.
4. In Power BI Desktop:
   - **Get Data > Excel Workbook**
   - Select only required sheets
   - Load/Transform as needed
5. Keep table names consistent with DAX guide references.

## 4) Which Source Should You Use?

- Use **generated CSVs** (recommended) for repeatable automation and easier refresh.
- Use **Excel workbook import** only when client governance requires Excel as handoff format.
- Avoid directly using raw UW input files in dashboard model because schema varies by template.

## 5) Refresh Strategy

When new claims files arrive:
1. Re-run pipeline.
2. Rebuild/refresh Power BI data source from latest run folder.
3. Keep the same PBIX model and visuals; only refresh data.

## 6) Common Issues and Fixes

- Missing columns in Power BI:
  - Confirm mapping was accepted in UI and pipeline completed successfully.
- Wrong metrics after refresh:
  - Verify PBIX points to latest run folder, not an old path.
- Theme/colors not matching assignment:
  - Re-import `theme_assignment.json`.
- Duplicate tables:
  - Remove stale imported tables and reconnect only to current handoff folder.
