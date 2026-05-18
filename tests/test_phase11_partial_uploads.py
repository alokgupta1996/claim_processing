from pathlib import Path

from claims_pipeline.config import get_underwriter_specs
from claims_pipeline.ingestion import read_underwriter_sources, read_underwriter_sources_from_bytes
from claims_pipeline.transform import transform_sources


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_ingestion_from_bytes_supports_single_uw_upload() -> None:
    specs = get_underwriter_specs()
    uw2_path = ROOT_DIR / specs["UW2"].file_name
    payload = {"UW2": uw2_path.read_bytes()}
    sources = read_underwriter_sources_from_bytes(payload, specs)

    assert set(sources.keys()) == {"UW2"}
    assert len(sources["UW2"]["members"]) == 10
    assert len(sources["UW2"]["claims"]) == 12


def test_transform_sources_supports_single_uw_subset() -> None:
    all_sources = read_underwriter_sources(ROOT_DIR)
    subset_sources = {"UW1": all_sources["UW1"]}

    master_census, master_claims = transform_sources(subset_sources)
    assert len(master_census) == 10
    assert len(master_claims) == 12
    assert master_census["source_uw"].eq("UW1").all()
    assert master_claims["source_uw"].eq("UW1").all()

