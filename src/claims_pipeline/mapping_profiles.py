from __future__ import annotations

from datetime import datetime, UTC
import json
from pathlib import Path
import re
from typing import Dict, Iterable, Tuple

import pandas as pd


def _sanitize_profile_name(profile_name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", profile_name.strip())
    return cleaned.strip("_") or "default_profile"


def _column_set(columns: Iterable[object]) -> set[str]:
    return {str(c).strip() for c in columns}


def _source_signature(
    raw_sources: Dict[str, Dict[str, pd.DataFrame]],
) -> Dict[str, Dict[str, list[str]]]:
    signature: Dict[str, Dict[str, list[str]]] = {}
    for uw_code, tables in raw_sources.items():
        signature[uw_code] = {
            "members": [str(c) for c in tables["members"].columns],
            "claims": [str(c) for c in tables["claims"].columns],
        }
    return signature


def save_mapping_profile(
    profile_dir: Path,
    profile_name: str,
    raw_sources: Dict[str, Dict[str, pd.DataFrame]],
    mappings: Dict[str, Dict[str, Dict[str, str]]],
    ai_engine: str,
    medium_threshold: float,
    high_threshold: float,
) -> Path:
    profile_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_profile_name(profile_name)
    profile_path = profile_dir / f"{safe_name}.json"

    payload = {
        "version": 1,
        "profile_name": safe_name,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "ai_engine": ai_engine,
        "medium_threshold": medium_threshold,
        "high_threshold": high_threshold,
        "signature": _source_signature(raw_sources),
        "mappings": mappings,
    }
    profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return profile_path


def load_mapping_profile(profile_path: Path) -> Dict[str, object]:
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if "mappings" not in payload or "signature" not in payload:
        raise ValueError("Invalid profile format: missing mappings/signature.")
    return payload


def profile_match_score(
    profile_payload: Dict[str, object],
    raw_sources: Dict[str, Dict[str, pd.DataFrame]],
) -> Tuple[float, Dict[str, float]]:
    signature = profile_payload["signature"]
    if not isinstance(signature, dict):
        return 0.0, {}

    per_table_scores: Dict[str, float] = {}
    score_sum = 0.0
    score_count = 0

    for uw_code, tables in raw_sources.items():
        if uw_code not in signature:
            continue
        sig_uw = signature[uw_code]
        if not isinstance(sig_uw, dict):
            continue
        for table_key in ("members", "claims"):
            if table_key not in sig_uw:
                continue
            expected_cols = _column_set(sig_uw[table_key])
            actual_cols = _column_set(tables[table_key].columns)
            if not expected_cols and not actual_cols:
                score = 1.0
            elif not expected_cols or not actual_cols:
                score = 0.0
            else:
                score = len(expected_cols & actual_cols) / len(expected_cols | actual_cols)
            k = f"{uw_code}.{table_key}"
            per_table_scores[k] = round(score, 4)
            score_sum += score
            score_count += 1

    if score_count == 0:
        return 0.0, per_table_scores
    overall = score_sum / score_count
    return round(overall, 4), per_table_scores

