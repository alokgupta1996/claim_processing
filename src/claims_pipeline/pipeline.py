from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

import pandas as pd

from claims_pipeline.database import write_sqlite_database
from claims_pipeline.ingestion import read_underwriter_sources
from claims_pipeline.powerbi_handoff import create_pbix_handoff_package
from claims_pipeline.powerbi_prep import build_powerbi_tables, write_powerbi_tables
from claims_pipeline.report_generator import generate_claims_pdf_report
from claims_pipeline.transform import transform_sources
from claims_pipeline.usage_metrics import reset_usage_metrics, write_usage_metrics
from claims_pipeline.validation import validate_transformed_data, write_validation_report

logger = logging.getLogger(__name__)


def run_pipeline_from_sources(
    sources: Dict[str, Dict[str, pd.DataFrame]],
    processed_dir: Path,
    outputs_dir: Path,
    db_path: Path,
    powerbi_dir: Path,
    report_path: Path,
    use_llm_narrative: bool = True,
    run_mode: str = "full",
    pbix_file_name: str = "claims_dashboard.pbix",
) -> Dict[str, object]:
    valid_modes = {"full", "pdf_only", "powerbi_handoff"}
    if run_mode not in valid_modes:
        raise ValueError(f"run_mode must be one of {sorted(valid_modes)}")
    logger.info("run_pipeline_from_sources started mode=%s", run_mode)

    processed_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    project_root = Path(__file__).resolve().parents[2]
    usage_metrics_path = outputs_dir / "usage_metrics.json"
    reset_usage_metrics(
        {
            "run_mode": run_mode,
            "use_llm_narrative": use_llm_narrative,
            "processed_dir": str(processed_dir),
            "outputs_dir": str(outputs_dir),
            "powerbi_dir": str(powerbi_dir),
        }
    )

    master_census, master_claims = transform_sources(sources)  # type: ignore[arg-type]
    logger.info(
        "Transform complete members=%s claims=%s",
        len(master_census),
        len(master_claims),
    )

    master_census_path = processed_dir / "master_census.csv"
    master_claims_path = processed_dir / "master_claims.csv"
    validation_path = outputs_dir / "validation_report.json"

    master_census.to_csv(master_census_path, index=False)
    master_claims.to_csv(master_claims_path, index=False)

    db_row_counts = write_sqlite_database(master_census, master_claims, db_path)
    logger.info("SQLite write complete rows=%s db=%s", db_row_counts, db_path)
    powerbi_tables = build_powerbi_tables(master_census, master_claims)
    powerbi_outputs: Dict[str, str] = {}
    if run_mode in {"full", "powerbi_handoff"}:
        powerbi_dir.mkdir(parents=True, exist_ok=True)
        powerbi_outputs = write_powerbi_tables(powerbi_tables, powerbi_dir)
        logger.info("Power BI exports generated files=%s", len(powerbi_outputs))

    report_pdf_path = generate_claims_pdf_report(
        master_census=master_census,
        master_claims=master_claims,
        powerbi_tables=powerbi_tables,
        output_path=report_path,
        use_llm_narrative=use_llm_narrative,
    )
    logger.info("Report generated path=%s", report_pdf_path)

    pbix_handoff: Dict[str, str] | None = None
    if run_mode == "powerbi_handoff":
        pbix_handoff = create_pbix_handoff_package(
            project_root=project_root,
            powerbi_dir=powerbi_dir,
            outputs_dir=outputs_dir,
            pbix_file_name=pbix_file_name,
        )
        logger.info("PBIX handoff package generated at=%s", pbix_handoff["package_dir"])

    validation_report = validate_transformed_data(master_census, master_claims)
    write_validation_report(validation_report, validation_path)
    usage_report_path = write_usage_metrics(usage_metrics_path)
    logger.info(
        "Pipeline finished status=%s validation_passed=%s",
        "success" if validation_report["passed"] else "failed_validation",
        validation_report["passed"],
    )

    return {
        "status": "success" if validation_report["passed"] else "failed_validation",
        "master_census_path": str(master_census_path),
        "master_claims_path": str(master_claims_path),
        "validation_report_path": str(validation_path),
        "database_path": str(db_path),
        "database_rows": db_row_counts,
        "powerbi_dir": str(powerbi_dir),
        "powerbi_outputs": powerbi_outputs,
        "pbix_handoff": pbix_handoff,
        "run_mode": run_mode,
        "report_pdf_path": report_pdf_path,
        "usage_metrics_path": usage_report_path,
        "validation": validation_report,
    }


def run_pipeline(
    base_dir: Path,
    processed_dir: Path,
    outputs_dir: Path,
    db_path: Path,
    powerbi_dir: Path,
    report_path: Path,
    use_llm_narrative: bool = True,
    run_mode: str = "full",
    pbix_file_name: str = "claims_dashboard.pbix",
) -> Dict[str, object]:
    sources = read_underwriter_sources(base_dir)
    return run_pipeline_from_sources(
        sources=sources,
        processed_dir=processed_dir,
        outputs_dir=outputs_dir,
        db_path=db_path,
        powerbi_dir=powerbi_dir,
        report_path=report_path,
        use_llm_narrative=use_llm_narrative,
        run_mode=run_mode,
        pbix_file_name=pbix_file_name,
    )
