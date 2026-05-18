import sqlite3
from pathlib import Path

import pandas as pd

from claims_pipeline.database import build_kpi_summary
from claims_pipeline.ingestion import read_underwriter_sources
from claims_pipeline.pipeline import run_pipeline
from claims_pipeline.transform import transform_sources


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_sqlite_contains_expected_tables_and_counts(tmp_path: Path) -> None:
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

    with sqlite3.connect(db_path) as conn:
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn
        )
        members_count = pd.read_sql_query("SELECT COUNT(*) AS c FROM members", conn)["c"].iloc[0]
        claims_count = pd.read_sql_query("SELECT COUNT(*) AS c FROM claims", conn)["c"].iloc[0]
        kpi_count = pd.read_sql_query("SELECT COUNT(*) AS c FROM kpi_summary", conn)["c"].iloc[0]

    assert tables["name"].tolist() == ["claims", "kpi_summary", "members"]
    assert members_count == 32
    assert claims_count == 36
    assert kpi_count == 9


def test_kpi_summary_matches_dataframe_aggregation(tmp_path: Path) -> None:
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

    sources = read_underwriter_sources(ROOT_DIR)
    _, master_claims = transform_sources(sources)
    expected_kpi = build_kpi_summary(master_claims).sort_values(["source_uw", "quarter"])
    expected_kpi = expected_kpi.reset_index(drop=True)

    with sqlite3.connect(db_path) as conn:
        actual_kpi = pd.read_sql_query(
            "SELECT * FROM kpi_summary ORDER BY source_uw, quarter", conn
        )
    actual_kpi = actual_kpi.reset_index(drop=True)

    pd.testing.assert_frame_equal(actual_kpi, expected_kpi, check_dtype=False, rtol=1e-6)
