from pathlib import Path

import pandas as pd

from claims_pipeline.pipeline import run_pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_pipeline_generates_powerbi_tables(tmp_path: Path) -> None:
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
    expected_files = [
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
    for file_name in expected_files:
        assert (powerbi_dir / file_name).exists(), f"Missing {file_name}"


def test_powerbi_core_table_columns(tmp_path: Path) -> None:
    processed_dir = tmp_path / "data" / "processed"
    outputs_dir = tmp_path / "outputs"
    db_path = outputs_dir / "claims_analytics.db"
    powerbi_dir = tmp_path / "powerbi" / "data"
    report_path = outputs_dir / "Claims_Analysis_Report.pdf"

    run_pipeline(
        base_dir=ROOT_DIR,
        processed_dir=processed_dir,
        outputs_dir=outputs_dir,
        db_path=db_path,
        powerbi_dir=powerbi_dir,
        report_path=report_path,
        use_llm_narrative=False,
    )

    monthly = pd.read_csv(powerbi_dir / "monthly_trend.csv")
    uw_comp = pd.read_csv(powerbi_dir / "uw_comparison.csv")
    benchmarks = pd.read_csv(powerbi_dir / "benchmarks.csv")

    assert {"month_label", "total_claims", "total_paid_usd"}.issubset(monthly.columns)
    assert {
        "source_uw",
        "country",
        "total_claims",
        "total_paid_usd",
        "loss_ratio_pct",
    }.issubset(uw_comp.columns)
    assert {"metric", "benchmark_value"}.issubset(benchmarks.columns)
