# Phase 9 Submission Checklist

## Core Backend

- [x] Ingest UW1/UW2/UW3 source files with source-specific parsing rules
- [x] Transform to master schema outputs
- [x] Generate validation report
- [x] Load SQLite database (`members`, `claims`, `kpi_summary`)
- [x] Single-command CLI pipeline execution (`src/main.py`)

## AI + UI

- [x] Streamlit upload and mapping confirmation UI
- [x] AI-assisted mapping suggestions with confidence levels
- [x] Low-confidence confirmation gate before pipeline run
- [x] Mapping profile save/load
- [x] Profile schema compatibility score

## Deployment

- [x] Dockerfile for application runtime
- [x] `docker-compose.yml` for UI and optional batch pipeline service
- [x] Host-mounted persistence for `outputs`, `data`, and `configs`
- [x] Environment template for optional OpenAI key

## Quality

- [x] Automated tests across phases
- [x] End-to-end run produces expected artifacts
- [x] README with architecture and runbook

## Final Assignment Layer (To Complete)

- [ ] Power BI dashboard pages (`claims_dashboard.pbix`)
- [ ] Final PDF report export and merge (`Claims_Analysis_Report.pdf`)

