from __future__ import annotations

import argparse
from pathlib import Path

from claims_pipeline.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run claims transformation pipeline.")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Directory that contains raw assignment files.",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "processed",
        help="Directory for processed CSV outputs.",
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
        help="Directory for reports such as validation JSON.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "claims_analytics.db",
        help="SQLite database output path.",
    )
    parser.add_argument(
        "--powerbi-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "powerbi" / "data",
        help="Directory for Power BI-ready summary tables.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs" / "Claims_Analysis_Report.pdf",
        help="Path to generated analytical PDF report.",
    )
    parser.add_argument(
        "--no-llm-narrative",
        action="store_true",
        help="Disable LLM narrative and use deterministic fallback text.",
    )
    parser.add_argument(
        "--run-mode",
        choices=["full", "pdf_only", "powerbi_handoff"],
        default="full",
        help=(
            "Execution mode: full (Power BI CSV + PDF), "
            "pdf_only (PDF only), powerbi_handoff (CSV + PDF + PBIX build package)."
        ),
    )
    parser.add_argument(
        "--pbix-file-name",
        default="claims_dashboard.pbix",
        help="Expected PBIX file name used in PBIX handoff instructions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_pipeline(
        base_dir=args.base_dir,
        processed_dir=args.processed_dir,
        outputs_dir=args.outputs_dir,
        db_path=args.db_path,
        powerbi_dir=args.powerbi_dir,
        report_path=args.report_path,
        use_llm_narrative=not args.no_llm_narrative,
        run_mode=args.run_mode,
        pbix_file_name=args.pbix_file_name,
    )
    print(f"Pipeline status: {result['status']}")
    print(f"master_census.csv: {result['master_census_path']}")
    print(f"master_claims.csv: {result['master_claims_path']}")
    print(f"validation_report.json: {result['validation_report_path']}")
    print(f"claims_analytics.db: {result['database_path']}")
    print(f"powerbi_data_dir: {result['powerbi_dir']}")
    if result.get("pbix_handoff"):
        print(f"pbix_handoff_package: {result['pbix_handoff']['package_dir']}")
        print(f"pbix_build_guide: {result['pbix_handoff']['build_guide']}")
        print(f"expected_pbix_path: {result['pbix_handoff']['expected_pbix_path']}")
    print(f"report_pdf: {result['report_pdf_path']}")
    print(f"usage_metrics: {result['usage_metrics_path']}")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
