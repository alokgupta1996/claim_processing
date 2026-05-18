from pathlib import Path

from claims_pipeline.config import get_underwriter_specs
from claims_pipeline.ingestion import read_master_schema_template, read_underwriter_sources


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_assignment_artifacts_exist() -> None:
    required = [
        "Assignment_Brief.docx",
        "Master_Schema_Template.xlsx",
        "Sample_Claims_Analysis_Report.pdf",
        "UW1_OmanInsurance_RawData.xlsx",
        "UW2_NationalLife_RawData.xlsx",
        "UW3_QatarGeneral_RawData.xlsx",
    ]
    for file_name in required:
        assert (ROOT_DIR / file_name).exists(), f"Missing required file: {file_name}"


def test_source_files_load_with_expected_shapes_and_columns() -> None:
    specs = get_underwriter_specs()
    sources = read_underwriter_sources(ROOT_DIR, specs)

    for uw_code, spec in specs.items():
        members = sources[uw_code]["members"]
        claims = sources[uw_code]["claims"]

        assert len(members) == spec.expected_member_rows
        assert len(claims) == spec.expected_claim_rows
        assert members.columns.tolist() == spec.expected_member_columns
        assert claims.columns.tolist() == spec.expected_claim_columns


def test_master_schema_contains_expected_core_sheets() -> None:
    template = read_master_schema_template(ROOT_DIR)
    expected_sheets = {"Master_Census", "Master_Claims", "Transformation_Rules", "DB_Schema"}
    assert expected_sheets.issubset(set(template.keys()))

