from claims_pipeline.config import get_underwriter_specs


def test_underwriter_specs_have_unique_file_names() -> None:
    specs = get_underwriter_specs()
    file_names = [spec.file_name for spec in specs.values()]
    assert len(file_names) == len(set(file_names))


def test_underwriter_specs_have_required_metadata() -> None:
    specs = get_underwriter_specs()
    for uw_code, spec in specs.items():
        assert spec.source_uw == uw_code
        assert spec.members_sheet
        assert spec.claims_sheet
        assert spec.expected_member_rows > 0
        assert spec.expected_claim_rows > 0
        assert len(spec.expected_member_columns) > 0
        assert len(spec.expected_claim_columns) > 0

