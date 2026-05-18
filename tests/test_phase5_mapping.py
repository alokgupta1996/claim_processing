from pathlib import Path

import pandas as pd

from claims_pipeline.config import get_underwriter_specs
from claims_pipeline.ingestion import read_underwriter_sources
from claims_pipeline.mapping import (
    apply_column_mapping,
    apply_mappings_to_sources,
    mapping_frame_to_dict,
    suggest_column_mappings,
)
from claims_pipeline.pipeline import run_pipeline_from_sources


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_suggest_column_mappings_finds_obvious_matches() -> None:
    expected = ["Member Name", "Date of Birth", "Annual Prem (Fils)"]
    actual = ["member_name", "date of birth", "annual premium"]
    suggestions = suggest_column_mappings(expected, actual)
    mapping = dict(zip(suggestions["expected_column"], suggestions["source_column"]))
    assert mapping["Member Name"] == "member_name"
    assert mapping["Date of Birth"] == "date of birth"
    assert "confidence" in suggestions.columns
    assert set(suggestions["confidence"]).issubset({"high", "medium", "low"})


def test_mapping_frame_to_dict_respects_use_flag() -> None:
    frame = pd.DataFrame(
        [
            {"expected_column": "A", "source_column": "x", "score": 0.9, "use": True},
            {"expected_column": "B", "source_column": "y", "score": 0.8, "use": False},
        ]
    )
    mapped = mapping_frame_to_dict(frame)
    assert mapped == {"A": "x"}


def test_apply_column_mapping_raises_on_missing_mapping() -> None:
    df = pd.DataFrame({"x": [1], "y": [2]})
    try:
        apply_column_mapping(df, ["A", "B"], {"A": "x"})
        assert False, "Expected ValueError for missing mapped columns"
    except ValueError as exc:
        assert "Missing mapped columns" in str(exc)


def test_run_pipeline_from_mapped_sources(tmp_path: Path) -> None:
    raw_sources = read_underwriter_sources(ROOT_DIR)
    specs = get_underwriter_specs()

    mappings = {}
    expected = {}
    for uw_code, spec in specs.items():
        mappings[uw_code] = {
            "members": {col: col for col in spec.expected_member_columns},
            "claims": {col: col for col in spec.expected_claim_columns},
        }
        expected[uw_code] = {
            "members": spec.expected_member_columns,
            "claims": spec.expected_claim_columns,
        }

    standardized = apply_mappings_to_sources(raw_sources, mappings, expected)
    processed_dir = tmp_path / "data" / "processed"
    outputs_dir = tmp_path / "outputs"
    db_path = outputs_dir / "claims_analytics.db"
    powerbi_dir = tmp_path / "powerbi" / "data"
    report_path = outputs_dir / "Claims_Analysis_Report.pdf"

    result = run_pipeline_from_sources(
        sources=standardized,
        processed_dir=processed_dir,
        outputs_dir=outputs_dir,
        db_path=db_path,
        powerbi_dir=powerbi_dir,
        report_path=report_path,
        use_llm_narrative=False,
    )
    assert result["status"] == "success"
    assert db_path.exists()


def test_openai_engine_falls_back_safely_without_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    expected = ["member_name", "service_date"]
    actual = ["Member Name", "Date of Service"]
    suggestions = suggest_column_mappings(expected, actual, ai_engine="openai_embeddings")
    assert len(suggestions) == 2
    assert suggestions["source_column"].str.len().gt(0).all()


def test_sentence_transformer_engine_falls_back_safely_if_model_unavailable(monkeypatch) -> None:
    from claims_pipeline import mapping as mapping_module

    monkeypatch.setattr(mapping_module, "_sentence_transformer_model", lambda: None)
    expected = ["employee_name", "dob_field"]
    actual = ["Employee Name", "Date of Birth"]
    suggestions = suggest_column_mappings(expected, actual, ai_engine="sentence_transformer")
    assert len(suggestions) == 2
    assert suggestions["source_column"].str.len().gt(0).all()


def test_llm_fallback_populates_unresolved_mapping(monkeypatch) -> None:
    from claims_pipeline import mapping as mapping_module

    # Force lexical matching to fail so LLM fallback path is used.
    monkeypatch.setattr(mapping_module, "_similarity", lambda _a, _b: 0.0)
    monkeypatch.setattr(mapping_module, "_token_jaccard", lambda _a, _b: 0.0)
    monkeypatch.setattr(mapping_module, "_alias_semantic_score", lambda _a, _b: 0.0)
    monkeypatch.setattr(
        mapping_module,
        "_llm_fallback_mapping",
        lambda expected_cols, _actual_cols: {str(expected_cols[0]): "MEMBER_REF"},
    )

    suggestions = suggest_column_mappings(
        expected_columns=["member_id"],
        actual_columns=["MEMBER_REF"],
        min_score=0.4,
        ai_engine="hybrid_rules",
        llm_fallback=True,
    )
    assert suggestions.loc[0, "source_column"] == "MEMBER_REF"
    assert bool(suggestions.loc[0, "llm_fallback_used"])
