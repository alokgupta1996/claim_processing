from pathlib import Path

from pypdf import PdfReader

from claims_pipeline.pipeline import run_pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_report_pdf_is_generated_with_multiple_pages(tmp_path: Path) -> None:
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
    assert report_path.exists()
    assert report_path.stat().st_size > 0

    reader = PdfReader(str(report_path))
    assert len(reader.pages) >= 5
