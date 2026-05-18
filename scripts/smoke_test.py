from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd


def assert_exists(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"Missing required artifact: {path}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    master_census = root / "data" / "processed" / "master_census.csv"
    master_claims = root / "data" / "processed" / "master_claims.csv"
    validation = root / "outputs" / "validation_report.json"
    db_path = root / "outputs" / "claims_analytics.db"
    report_pdf = root / "outputs" / "Claims_Analysis_Report.pdf"
    powerbi_dir = root / "powerbi" / "data"

    for p in [master_census, master_claims, validation, db_path, report_pdf, powerbi_dir]:
        assert_exists(p)

    census_df = pd.read_csv(master_census)
    claims_df = pd.read_csv(master_claims)
    report = json.loads(validation.read_text(encoding="utf-8"))

    if len(census_df) != 32:
        raise AssertionError(f"Unexpected census row count: {len(census_df)}")
    if len(claims_df) != 36:
        raise AssertionError(f"Unexpected claims row count: {len(claims_df)}")
    if not report.get("passed", False):
        raise AssertionError("Validation report indicates failed checks.")

    required_powerbi_files = [
        "monthly_trend.csv",
        "quarterly_summary.csv",
        "benefit_split.csv",
        "relationship_age.csv",
        "age_group_analysis.csv",
        "pec_diagnosis_top10.csv",
        "provider_top5.csv",
        "uw_comparison.csv",
        "benchmarks.csv",
    ]
    for name in required_powerbi_files:
        assert_exists(powerbi_dir / name)

    with sqlite3.connect(db_path) as conn:
        table_names = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn
        )["name"].tolist()
        if table_names != ["claims", "kpi_summary", "members"]:
            raise AssertionError(f"Unexpected DB tables: {table_names}")

    print("Smoke test passed: artifacts, row counts, DB tables, and Power BI pack are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
