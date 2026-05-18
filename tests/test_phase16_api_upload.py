from pathlib import Path

from fastapi.testclient import TestClient

import api.app as api_app_module


def test_api_upload_and_run_endpoint(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    sample_file = root / "UW1_OmanInsurance_RawData.xlsx"
    assert sample_file.exists()

    def _fake_run_pipeline_from_sources(**kwargs):
        outputs_dir = kwargs["outputs_dir"]
        outputs_dir.mkdir(parents=True, exist_ok=True)
        usage_path = outputs_dir / "usage_metrics.json"
        usage_path.write_text("{}", encoding="utf-8")
        return {
            "status": "success",
            "master_census_path": "master_census.csv",
            "master_claims_path": "master_claims.csv",
            "validation_report_path": "validation_report.json",
            "database_path": "claims_analytics.db",
            "database_rows": {"master_census": 1, "master_claims": 1},
            "powerbi_dir": "powerbi/data",
            "powerbi_outputs": {},
            "pbix_handoff": None,
            "run_mode": kwargs["run_mode"],
            "report_pdf_path": "Claims_Analysis_Report.pdf",
            "usage_metrics_path": str(usage_path),
            "validation": {"passed": True, "summary": {"errors": 0}},
        }

    monkeypatch.setattr(api_app_module, "run_pipeline_from_sources", _fake_run_pipeline_from_sources)

    client = TestClient(api_app_module.app)
    with sample_file.open("rb") as fh:
        response = client.post(
            "/api/upload-and-run",
            files=[
                (
                    "files",
                    (
                        sample_file.name,
                        fh.read(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                )
            ],
            data={
                "run_mode": "pdf_only",
                "use_llm_narrative": "false",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["files_selected"] == 1
    assert "UW1" in payload["selected_templates"]
