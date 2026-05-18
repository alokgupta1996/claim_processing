from pathlib import Path

import pandas as pd

from claims_pipeline.ingestion import read_underwriter_sources
from claims_pipeline.transform import transform_sources
from claims_pipeline.validation import validate_transformed_data


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_validation_detects_duplicate_claim_ids() -> None:
    sources = read_underwriter_sources(ROOT_DIR)
    master_census, master_claims = transform_sources(sources)

    corrupted_claims = pd.concat([master_claims, master_claims.iloc[[0]]], ignore_index=True)
    report = validate_transformed_data(master_census, corrupted_claims)

    unique_claim_check = [c for c in report["checks"] if c["name"] == "unique_master_claim_id"][0]
    assert unique_claim_check["passed"] is False
    assert report["passed"] is False

