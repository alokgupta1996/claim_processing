from pathlib import Path

from claims_pipeline.ingestion import read_underwriter_sources
from claims_pipeline.mapping import (
    apply_profile_mapping_to_suggestions,
    suggest_column_mappings,
)
from claims_pipeline.mapping_profiles import (
    load_mapping_profile,
    profile_match_score,
    save_mapping_profile,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


def _identity_mappings(raw_sources):
    mappings = {}
    for uw_code, tables in raw_sources.items():
        mappings[uw_code] = {
            "members": {str(c): str(c) for c in tables["members"].columns},
            "claims": {str(c): str(c) for c in tables["claims"].columns},
        }
    return mappings


def test_profile_save_load_roundtrip(tmp_path: Path) -> None:
    raw_sources = read_underwriter_sources(ROOT_DIR)
    mappings = _identity_mappings(raw_sources)

    saved_path = save_mapping_profile(
        profile_dir=tmp_path,
        profile_name="uw_profile_v1",
        raw_sources=raw_sources,
        mappings=mappings,
        ai_engine="hybrid_rules",
        medium_threshold=0.65,
        high_threshold=0.85,
    )
    assert saved_path.exists()

    payload = load_mapping_profile(saved_path)
    assert payload["profile_name"] == "uw_profile_v1"
    assert payload["mappings"]["UW1"]["members"]["Card No"] == "Card No"


def test_profile_match_score_high_for_same_schema(tmp_path: Path) -> None:
    raw_sources = read_underwriter_sources(ROOT_DIR)
    mappings = _identity_mappings(raw_sources)
    saved_path = save_mapping_profile(
        profile_dir=tmp_path,
        profile_name="same_schema",
        raw_sources=raw_sources,
        mappings=mappings,
        ai_engine="hybrid_rules",
        medium_threshold=0.65,
        high_threshold=0.85,
    )
    payload = load_mapping_profile(saved_path)
    score, table_scores = profile_match_score(payload, raw_sources)
    assert score == 1.0
    assert all(v == 1.0 for v in table_scores.values())


def test_apply_profile_mapping_overrides_suggestions() -> None:
    expected = ["Member Name", "Date of Birth"]
    actual = ["name_raw", "dob_raw"]
    suggestions = suggest_column_mappings(expected, actual, min_score=0.99)
    assert suggestions["source_column"].eq("").all()

    profile_mapping = {"Member Name": "name_raw", "Date of Birth": "dob_raw"}
    merged = apply_profile_mapping_to_suggestions(suggestions, profile_mapping, actual)

    assert merged.loc[merged["expected_column"] == "Member Name", "source_column"].iloc[0] == "name_raw"
    assert merged.loc[merged["expected_column"] == "Date of Birth", "source_column"].iloc[0] == "dob_raw"
    assert merged["use"].all()

