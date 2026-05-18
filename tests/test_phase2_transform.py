from pathlib import Path

import pandas as pd

from claims_pipeline.ingestion import read_underwriter_sources
from claims_pipeline.transform import (
    MASTER_CENSUS_COLUMNS,
    MASTER_CLAIMS_COLUMNS,
    transform_sources,
)
from claims_pipeline.validation import validate_transformed_data


ROOT_DIR = Path(__file__).resolve().parents[1]


def _build_master_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    sources = read_underwriter_sources(ROOT_DIR)
    return transform_sources(sources)


def test_transform_outputs_match_master_schema_shape() -> None:
    master_census, master_claims = _build_master_frames()

    assert master_census.columns.tolist() == MASTER_CENSUS_COLUMNS
    assert master_claims.columns.tolist() == MASTER_CLAIMS_COLUMNS
    assert len(master_census) == 32
    assert len(master_claims) == 36


def test_ids_are_unique_and_linked() -> None:
    master_census, master_claims = _build_master_frames()

    assert master_census["master_member_id"].is_unique
    assert master_claims["master_claim_id"].is_unique
    assert master_claims["master_member_id"].isin(master_census["master_member_id"]).all()


def test_date_normalization_and_time_fields() -> None:
    _, master_claims = _build_master_frames()

    parsed_claim = pd.to_datetime(master_claims["claim_date"], errors="raise")
    parsed_service = pd.to_datetime(master_claims["service_date"], errors="raise")
    assert parsed_claim.notna().all()
    assert parsed_service.notna().all()
    assert master_claims["month"].between(1, 12).all()
    assert master_claims["quarter"].isin({"Q1", "Q2", "Q3", "Q4"}).all()


def test_currency_conversion_examples_are_correct() -> None:
    master_census, master_claims = _build_master_frames()

    uw1_member = master_census.loc[
        master_census["master_member_id"] == "UW1_OIC-001", "annual_premium_usd"
    ].iloc[0]
    uw3_member = master_census.loc[
        master_census["master_member_id"] == "UW3_QGI-C001", "annual_premium_usd"
    ].iloc[0]
    uw1_claim_paid = master_claims.loc[
        master_claims["master_claim_id"] == "UW1_OIC-CLM-001", "paid_amount_usd"
    ].iloc[0]
    uw3_claim_paid = master_claims.loc[
        master_claims["master_claim_id"] == "UW3_QGI-CLM-001", "paid_amount_usd"
    ].iloc[0]

    assert uw1_member == 220.15
    assert uw3_member == 1153.85
    assert uw1_claim_paid == 2072.00
    assert uw3_claim_paid == 256.04


def test_category_standardization_and_flags() -> None:
    _, master_claims = _build_master_frames()

    assert "PEC/Chronic" in set(master_claims["illness_type"])
    assert "Maternity" in set(master_claims["illness_type"])
    assert "Mental Health" in set(master_claims["illness_type"])
    assert "Emergency" in set(master_claims["benefit_type"])

    pec_check = master_claims["illness_type"].eq("PEC/Chronic")
    onco_check = master_claims["illness_type"].eq("Oncology")
    mat_check = master_claims["illness_type"].eq("Maternity")
    mh_check = master_claims["illness_type"].eq("Mental Health")

    assert (master_claims["pec_flag"] == pec_check.astype(int)).all()
    assert (master_claims["oncology_flag"] == onco_check.astype(int)).all()
    assert (master_claims["maternity_flag"] == mat_check.astype(int)).all()
    assert (master_claims["mental_health_flag"] == mh_check.astype(int)).all()


def test_validation_report_passes_on_transformed_data() -> None:
    master_census, master_claims = _build_master_frames()
    report = validate_transformed_data(master_census, master_claims)

    assert report["passed"] is True
    assert report["summary"]["passed_checks"] == report["summary"]["total_checks"]

