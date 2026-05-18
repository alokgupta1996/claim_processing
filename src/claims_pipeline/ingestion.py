from pathlib import Path
from typing import Dict
from io import BytesIO

import pandas as pd

from claims_pipeline.config import UnderwriterSpec, get_underwriter_specs


def _read_sheet(file_obj: object, sheet_name: str, skiprows: int) -> pd.DataFrame:
    return pd.read_excel(file_obj, sheet_name=sheet_name, skiprows=skiprows, dtype=object)


def read_underwriter_sources(
    base_dir: Path, specs: Dict[str, UnderwriterSpec] | None = None
) -> Dict[str, Dict[str, pd.DataFrame]]:
    specs = specs or get_underwriter_specs(base_dir)
    sources: Dict[str, Dict[str, pd.DataFrame]] = {}

    for uw_code, spec in specs.items():
        workbook_path = base_dir / spec.file_name
        members_df = _read_sheet(workbook_path, spec.members_sheet, spec.members_skiprows)
        claims_df = _read_sheet(workbook_path, spec.claims_sheet, spec.claims_skiprows)
        sources[uw_code] = {"members": members_df, "claims": claims_df}

    return sources


def read_underwriter_sources_from_bytes(
    uploaded_bytes: Dict[str, bytes],
    specs: Dict[str, UnderwriterSpec] | None = None,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    specs = specs or get_underwriter_specs()
    sources: Dict[str, Dict[str, pd.DataFrame]] = {}

    for uw_code, file_bytes in uploaded_bytes.items():
        if uw_code not in specs:
            raise ValueError(f"Unknown underwriter code in upload payload: {uw_code}")
        spec = specs[uw_code]
        file_bytes = uploaded_bytes[uw_code]
        members_df = _read_sheet(
            BytesIO(file_bytes), spec.members_sheet, spec.members_skiprows
        )
        claims_df = _read_sheet(BytesIO(file_bytes), spec.claims_sheet, spec.claims_skiprows)
        sources[uw_code] = {"members": members_df, "claims": claims_df}

    if not sources:
        raise ValueError("No uploaded UW files found.")

    return sources


def read_master_schema_template(base_dir: Path) -> Dict[str, pd.DataFrame]:
    template_path = base_dir / "Master_Schema_Template.xlsx"
    xl = pd.ExcelFile(template_path)
    return {
        sheet_name: pd.read_excel(template_path, sheet_name=sheet_name, dtype=object)
        for sheet_name in xl.sheet_names
    }
