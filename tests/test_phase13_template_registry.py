import json
from pathlib import Path

from claims_pipeline.config import get_underwriter_specs


def test_template_registry_loads_from_configs_dir(tmp_path: Path) -> None:
    templates_dir = tmp_path / "configs" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "source_uw": "UWX",
        "country": "Testland",
        "file_name": "uwx.xlsx",
        "members_sheet": "Members",
        "claims_sheet": "Claims",
        "members_skiprows": 0,
        "claims_skiprows": 0,
        "expected_member_rows": 1,
        "expected_claim_rows": 1,
        "expected_member_columns": ["A"],
        "expected_claim_columns": ["B"],
    }
    (templates_dir / "UWX.json").write_text(json.dumps(payload), encoding="utf-8")

    specs = get_underwriter_specs(tmp_path)
    assert set(specs.keys()) == {"UWX"}
    assert specs["UWX"].country == "Testland"
