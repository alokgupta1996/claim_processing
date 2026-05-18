from __future__ import annotations

from io import BytesIO
from typing import Dict, List

import pandas as pd

from claims_pipeline.config import UnderwriterSpec


def _safe_read_columns(file_bytes: bytes, sheet_name: str, skiprows: int) -> List[str]:
    try:
        df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name, skiprows=skiprows, dtype=object)
        return [str(c) for c in df.columns]
    except Exception:
        return []


def _overlap_ratio(expected: List[str], actual: List[str]) -> float:
    exp = {x.strip().lower() for x in expected}
    act = {x.strip().lower() for x in actual}
    if not exp:
        return 0.0
    return len(exp & act) / len(exp)


def detect_underwriter_template(
    file_bytes: bytes,
    specs: Dict[str, UnderwriterSpec],
) -> Dict[str, object]:
    xl = pd.ExcelFile(BytesIO(file_bytes))
    sheet_names = {str(s) for s in xl.sheet_names}

    candidates: List[Dict[str, object]] = []
    for uw_code, spec in specs.items():
        members_sheet_present = spec.members_sheet in sheet_names
        claims_sheet_present = spec.claims_sheet in sheet_names
        sheet_score = (int(members_sheet_present) + int(claims_sheet_present)) / 2

        members_cols = _safe_read_columns(file_bytes, spec.members_sheet, spec.members_skiprows)
        claims_cols = _safe_read_columns(file_bytes, spec.claims_sheet, spec.claims_skiprows)
        members_overlap = _overlap_ratio(spec.expected_member_columns, members_cols)
        claims_overlap = _overlap_ratio(spec.expected_claim_columns, claims_cols)
        column_score = (members_overlap + claims_overlap) / 2

        total_score = 0.45 * sheet_score + 0.55 * column_score
        if total_score >= 0.85:
            confidence = "high"
        elif total_score >= 0.65:
            confidence = "medium"
        else:
            confidence = "low"

        candidates.append(
            {
                "uw_code": uw_code,
                "country": spec.country,
                "score": round(total_score, 3),
                "confidence": confidence,
                "sheet_score": round(sheet_score, 3),
                "column_score": round(column_score, 3),
            }
        )

    ranked = sorted(candidates, key=lambda x: float(x["score"]), reverse=True)
    best = ranked[0]
    detected_uw = str(best["uw_code"]) if float(best["score"]) >= 0.35 else "Unknown"
    return {
        "detected_uw": detected_uw,
        "detected_score": float(best["score"]),
        "detected_confidence": str(best["confidence"]),
        "candidates": ranked,
    }

