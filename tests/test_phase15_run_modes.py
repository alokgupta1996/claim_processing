from pathlib import Path

from claims_pipeline.pipeline import run_pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_pdf_only_mode_skips_powerbi_exports(tmp_path: Path) -> None:
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
        run_mode="pdf_only",
    )

    assert result["status"] == "success"
    assert report_path.exists()
    assert result["powerbi_outputs"] == {}
    assert result["pbix_handoff"] is None
    assert not (powerbi_dir / "monthly_trend.csv").exists()


def test_powerbi_handoff_mode_generates_package(tmp_path: Path) -> None:
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
        run_mode="powerbi_handoff",
        pbix_file_name="claims_dashboard.pbix",
    )

    assert result["status"] == "success"
    assert report_path.exists()
    assert (powerbi_dir / "monthly_trend.csv").exists()
    assert result["pbix_handoff"] is not None
    handoff = result["pbix_handoff"]
    assert Path(handoff["package_dir"]).exists()
    assert Path(handoff["build_guide"]).exists()
