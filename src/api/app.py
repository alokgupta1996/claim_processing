from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Dict, List, Tuple
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile

from claims_pipeline.config import UnderwriterSpec, get_underwriter_specs
from claims_pipeline.ingestion import read_underwriter_sources_from_bytes
from claims_pipeline.logging_config import setup_logging
from claims_pipeline.mapping import (
    apply_mappings_to_sources,
    mapping_frame_to_dict,
    suggest_column_mappings,
)
from claims_pipeline.pipeline import run_pipeline_from_sources
from claims_pipeline.template_detection import detect_underwriter_template

PROJECT_ROOT = Path(__file__).resolve().parents[2]
setup_logging(service_name="claims-api")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claims Pipeline API",
    description="Upload UW Excel files and run the deterministic pipeline.",
    version="1.0.0",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    req_id = uuid4().hex[:8]
    start = time.perf_counter()
    logger.info(
        "Request started id=%s method=%s path=%s",
        req_id,
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "Request failed id=%s method=%s path=%s latency_ms=%s",
            req_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "Request completed id=%s method=%s path=%s status=%s latency_ms=%s",
        req_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return cleaned.strip("_") or "run"


def _build_expected_columns(specs: Dict[str, UnderwriterSpec]) -> Dict[str, Dict[str, List[str]]]:
    expected: Dict[str, Dict[str, List[str]]] = {}
    for uw_code, spec in specs.items():
        expected[uw_code] = {
            "members": spec.expected_member_columns,
            "claims": spec.expected_claim_columns,
        }
    return expected


def _build_auto_mappings(
    raw_sources: Dict[str, Dict[str, pd.DataFrame]],
    specs: Dict[str, UnderwriterSpec],
    medium_threshold: float,
    high_threshold: float,
    auto_accept_low_confidence: bool,
    ai_engine: str,
) -> Tuple[
    Dict[str, Dict[str, Dict[str, str]]],
    Dict[str, int],
    Dict[str, Dict[str, int | bool]],
]:
    mappings: Dict[str, Dict[str, Dict[str, str]]] = {}
    low_conf_counts: Dict[str, int] = {}
    telemetry: Dict[str, Dict[str, int | bool]] = {}

    for uw_code, tables in raw_sources.items():
        spec = specs[uw_code]
        members = suggest_column_mappings(
            expected_columns=spec.expected_member_columns,
            actual_columns=[str(c) for c in tables["members"].columns],
            medium_threshold=medium_threshold,
            high_threshold=high_threshold,
            ai_engine=ai_engine,
        )
        claims = suggest_column_mappings(
            expected_columns=spec.expected_claim_columns,
            actual_columns=[str(c) for c in tables["claims"].columns],
            medium_threshold=medium_threshold,
            high_threshold=high_threshold,
            ai_engine=ai_engine,
        )

        if auto_accept_low_confidence:
            members["use"] = members["source_column"].fillna("").astype(str).str.strip() != ""
            claims["use"] = claims["source_column"].fillna("").astype(str).str.strip() != ""

        low_count = int(
            (members["use"].astype(bool) & (members["confidence"] == "low")).sum()
            + (claims["use"].astype(bool) & (claims["confidence"] == "low")).sum()
        )
        low_conf_counts[uw_code] = low_count
        member_sentence_total = (
            float(pd.to_numeric(members.get("sentence_score"), errors="coerce").fillna(0).sum())
            if "sentence_score" in members.columns
            else 0.0
        )
        claim_sentence_total = (
            float(pd.to_numeric(claims.get("sentence_score"), errors="coerce").fillna(0).sum())
            if "sentence_score" in claims.columns
            else 0.0
        )
        telemetry[uw_code] = {
            "semantic_stage_used": bool(member_sentence_total > 0 or claim_sentence_total > 0),
            "llm_fallback_used_count": int(
                ("llm_fallback_used" in members.columns and members["llm_fallback_used"].astype(bool).sum())
                + ("llm_fallback_used" in claims.columns and claims["llm_fallback_used"].astype(bool).sum())
            ),
            "member_rows": int(len(members)),
            "claim_rows": int(len(claims)),
        }

        mappings[uw_code] = {
            "members": mapping_frame_to_dict(members),
            "claims": mapping_frame_to_dict(claims),
        }

    return mappings, low_conf_counts, telemetry


@app.get("/api/health")
def api_health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload-and-run")
async def upload_and_run(
    files: List[UploadFile] = File(...),
    run_mode: str = Form("pdf_only"),
    use_llm_narrative: bool = Form(True),
    auto_accept_low_confidence: bool = Form(True),
    ai_engine: str = Form("sentence_transformer"),
    medium_threshold: float = Form(0.65),
    high_threshold: float = Form(0.85),
    min_detection_score: float = Form(0.35),
    run_label: str | None = Form(None),
    pbix_file_name: str = Form("claims_dashboard.pbix"),
) -> Dict[str, object]:
    logger.info(
        "Upload request received files=%s mode=%s ai_engine=%s",
        len(files),
        run_mode,
        ai_engine,
    )
    valid_modes = {"full", "pdf_only", "powerbi_handoff"}
    if run_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"run_mode must be one of {sorted(valid_modes)}")
    if high_threshold <= medium_threshold:
        raise HTTPException(status_code=400, detail="high_threshold must be greater than medium_threshold")
    if not files:
        raise HTTPException(status_code=400, detail="At least one .xlsx file is required")

    specs = get_underwriter_specs(PROJECT_ROOT)
    selected_by_uw: Dict[str, Dict[str, object]] = {}
    detections: List[Dict[str, object]] = []

    for upload in files:
        content = await upload.read()
        if not content:
            continue
        detection = detect_underwriter_template(content, specs)
        detected_uw = str(detection["detected_uw"])
        detected_score = float(detection["detected_score"])
        detections.append(
            {
                "file_name": upload.filename or "unknown.xlsx",
                "detected_uw": detected_uw,
                "score": detected_score,
                "confidence": str(detection["detected_confidence"]),
            }
        )
        if detected_uw == "Unknown" or detected_score < min_detection_score:
            continue
        incumbent = selected_by_uw.get(detected_uw)
        if incumbent is None or detected_score > float(incumbent["score"]):
            selected_by_uw[detected_uw] = {
                "filename": upload.filename or "unknown.xlsx",
                "score": detected_score,
                "bytes": content,
            }

    if not selected_by_uw:
        logger.warning("No files matched templates above threshold=%s", min_detection_score)
        raise HTTPException(
            status_code=400,
            detail="No upload matched known templates above minimum detection score.",
        )

    uploaded_bytes = {
        uw_code: payload["bytes"]  # type: ignore[index]
        for uw_code, payload in selected_by_uw.items()
    }

    try:
        raw_sources = read_underwriter_sources_from_bytes(uploaded_bytes, specs)
        expected_columns = _build_expected_columns(specs)
        mappings, low_conf_counts, mapping_telemetry = _build_auto_mappings(
            raw_sources=raw_sources,
            specs=specs,
            medium_threshold=medium_threshold,
            high_threshold=high_threshold,
            auto_accept_low_confidence=auto_accept_low_confidence,
            ai_engine=ai_engine,
        )
        standardized_sources = apply_mappings_to_sources(raw_sources, mappings, expected_columns)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Auto mapping failed")
        raise HTTPException(status_code=422, detail=f"Unable to map uploaded templates: {exc}") from exc

    tag = _safe_slug(run_label or datetime.now().strftime("api_%Y%m%d_%H%M%S") + f"_{uuid4().hex[:6]}")
    processed_dir = PROJECT_ROOT / "data" / "processed" / tag
    outputs_dir = PROJECT_ROOT / "outputs" / tag
    powerbi_dir = PROJECT_ROOT / "powerbi" / "data" / tag
    db_path = outputs_dir / "claims_analytics.db"
    report_path = outputs_dir / "Claims_Analysis_Report.pdf"

    try:
        result = run_pipeline_from_sources(
            sources=standardized_sources,
            processed_dir=processed_dir,
            outputs_dir=outputs_dir,
            db_path=db_path,
            powerbi_dir=powerbi_dir,
            report_path=report_path,
            use_llm_narrative=use_llm_narrative,
            run_mode=run_mode,
            pbix_file_name=pbix_file_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline execution failed")
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {exc}") from exc

    logger.info(
        "Upload run completed status=%s files_selected=%s run_label=%s",
        result["status"],
        len(selected_by_uw),
        tag,
    )

    return {
        "status": result["status"],
        "run_label": tag,
        "files_received": len(files),
        "files_selected": len(selected_by_uw),
        "selected_templates": {
            uw: {
                "file_name": str(meta["filename"]),
                "score": float(meta["score"]),
            }
            for uw, meta in selected_by_uw.items()
        },
        "detections": detections,
        "low_confidence_mappings": low_conf_counts,
        "mapping_telemetry": mapping_telemetry,
        "result": result,
    }
