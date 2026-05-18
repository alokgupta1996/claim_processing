import json
from pathlib import Path

import pandas as pd

from claims_pipeline.pipeline import run_pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_run_pipeline_creates_expected_artifacts(tmp_path: Path) -> None:
    processed_dir = tmp_path / "data" / "processed"
    outputs_dir = tmp_path / "outputs"
    db_path = outputs_dir / "claims_analytics.db"
    powerbi_dir = tmp_path / "powerbi" / "data"
    report_path = outputs_dir / "Claims_Analysis_Report.pdf"

    result = run_pipeline(
        base_dir=ROOT_DIR,
        processed_dir=processed_dir,
        outputs_dir=outputs_dir,
        db_path=db_path,
        powerbi_dir=powerbi_dir,
        report_path=report_path,
        use_llm_narrative=False,
    )

    assert result["status"] == "success"

    master_census_path = processed_dir / "master_census.csv"
    master_claims_path = processed_dir / "master_claims.csv"
    validation_path = outputs_dir / "validation_report.json"
    database_path = outputs_dir / "claims_analytics.db"
    monthly_trend_path = powerbi_dir / "monthly_trend.csv"
    report_file_path = outputs_dir / "Claims_Analysis_Report.pdf"

    assert master_census_path.exists()
    assert master_claims_path.exists()
    assert validation_path.exists()
    assert database_path.exists()
    assert monthly_trend_path.exists()
    assert report_file_path.exists()

    master_census = pd.read_csv(master_census_path)
    master_claims = pd.read_csv(master_claims_path)
    validation_report = json.loads(validation_path.read_text(encoding="utf-8"))

    assert len(master_census) == 32
    assert len(master_claims) == 36
    assert validation_report["passed"] is True
    assert validation_report["summary"]["master_census_rows"] == 32
    assert validation_report["summary"]["master_claims_rows"] == 36
    assert result["database_rows"]["members"] == 32
    assert result["database_rows"]["claims"] == 36
    assert result["powerbi_outputs"]["monthly_trend"].endswith("monthly_trend.csv")
    assert result["report_pdf_path"].endswith("Claims_Analysis_Report.pdf")
