from __future__ import annotations

from datetime import datetime
import io
import logging
from pathlib import Path
from typing import Dict
import sys
import zipfile

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from claims_pipeline.config import UnderwriterSpec, get_underwriter_specs
from claims_pipeline.ingestion import read_underwriter_sources_from_bytes
from claims_pipeline.logging_config import setup_logging
from claims_pipeline.mapping import (
    apply_mappings_to_sources,
    apply_profile_mapping_to_suggestions,
    mapping_frame_to_dict,
    suggest_column_mappings,
)
from claims_pipeline.mapping_profiles import (
    load_mapping_profile,
    profile_match_score,
    save_mapping_profile,
)
from claims_pipeline.pipeline import run_pipeline_from_sources
from claims_pipeline.template_detection import detect_underwriter_template

setup_logging(service_name="claims-ui")
logger = logging.getLogger(__name__)


def _build_expected_columns(specs: Dict[str, UnderwriterSpec]) -> Dict[str, Dict[str, list[str]]]:
    expected: Dict[str, Dict[str, list[str]]] = {}
    for uw_code, spec in specs.items():
        expected[uw_code] = {
            "members": spec.expected_member_columns,
            "claims": spec.expected_claim_columns,
        }
    return expected


def _editor_for_mapping(
    title: str,
    expected_columns: list[str],
    actual_columns: list[str],
    key: str,
    high_threshold: float,
    medium_threshold: float,
    ai_engine: str,
    profile_mapping: Dict[str, str] | None = None,
) -> pd.DataFrame:
    suggestions = suggest_column_mappings(
        expected_columns,
        actual_columns,
        high_threshold=high_threshold,
        medium_threshold=medium_threshold,
        ai_engine=ai_engine,
    )
    suggestions = apply_profile_mapping_to_suggestions(
        suggestions, profile_mapping=profile_mapping, actual_columns=actual_columns
    )
    options = [""] + actual_columns
    st.markdown(f"**{title}**")
    edited = st.data_editor(
        suggestions,
        key=key,
        hide_index=True,
        use_container_width=True,
        column_config={
            "expected_column": st.column_config.TextColumn(
                "Expected Column", disabled=True
            ),
            "source_column": st.column_config.SelectboxColumn(
                "Mapped Source Column", options=options
            ),
            "score": st.column_config.NumberColumn("Auto Match Score", disabled=True),
            "confidence": st.column_config.TextColumn("Confidence", disabled=True),
            "recommended": st.column_config.CheckboxColumn(
                "Recommended", disabled=True
            ),
            "name_score": st.column_config.NumberColumn("Name Score", disabled=True),
            "token_score": st.column_config.NumberColumn("Token Score", disabled=True),
            "semantic_score": st.column_config.NumberColumn("Semantic Score", disabled=True),
            "embedding_score": st.column_config.NumberColumn(
                "Embedding Score", disabled=True
            ),
            "sentence_score": st.column_config.NumberColumn(
                "Sentence Score", disabled=True
            ),
            "llm_fallback_used": st.column_config.CheckboxColumn(
                "LLM Fallback", disabled=True
            ),
            "use": st.column_config.CheckboxColumn("Use This Mapping"),
        },
    )
    return edited


def _read_sources_from_uploaded_files(
    uploaded_files: Dict[str, object],
    specs: Dict[str, UnderwriterSpec],
) -> Dict[str, Dict[str, pd.DataFrame]]:
    uploaded_bytes = {
        uw_code: uploaded_files[uw_code].getvalue()
        for uw_code in uploaded_files
        if uploaded_files[uw_code] is not None
    }
    return read_underwriter_sources_from_bytes(uploaded_bytes, specs)


def _build_assignment_editor(
    uploaded_files: list[object],
    specs: Dict[str, UnderwriterSpec],
) -> pd.DataFrame:
    rows = []
    for file_obj in uploaded_files:
        detection = detect_underwriter_template(file_obj.getvalue(), specs)
        detected = str(detection["detected_uw"])
        rows.append(
            {
                "file_name": str(file_obj.name),
                "file_size_kb": round(len(file_obj.getvalue()) / 1024, 1),
                "detected_uw": detected,
                "score": float(detection["detected_score"]),
                "confidence": str(detection["detected_confidence"]),
                "assigned_uw": detected if detected in specs else "Ignore",
            }
        )

    assign_df = pd.DataFrame(rows)
    uw_options = ["Ignore"] + list(specs.keys())
    edited = st.data_editor(
        assign_df,
        key="assignment_editor",
        hide_index=True,
        use_container_width=True,
        column_config={
            "file_name": st.column_config.TextColumn("File Name", disabled=True),
            "file_size_kb": st.column_config.NumberColumn("Size (KB)", disabled=True),
            "detected_uw": st.column_config.TextColumn("Detected Template", disabled=True),
            "score": st.column_config.NumberColumn("Detection Score", disabled=True),
            "confidence": st.column_config.TextColumn("Confidence", disabled=True),
            "assigned_uw": st.column_config.SelectboxColumn(
                "Assigned Underwriter", options=uw_options
            ),
        },
    )
    return edited


def _build_mappings_ui(
    raw_sources: Dict[str, Dict[str, pd.DataFrame]],
    specs: Dict[str, UnderwriterSpec],
    high_threshold: float,
    medium_threshold: float,
    ai_engine: str,
    loaded_profile_mappings: Dict[str, Dict[str, Dict[str, str]]] | None = None,
) -> Dict[str, Dict[str, Dict[str, str]]]:
    mappings: Dict[str, Dict[str, Dict[str, str]]] = {}

    for uw_code in raw_sources:
        spec = specs[uw_code]
        st.subheader(f"{uw_code} - {spec.country}")
        mappings[uw_code] = {}

        members_mapping_frame = _editor_for_mapping(
            title=f"{uw_code} Members Mapping",
            expected_columns=spec.expected_member_columns,
            actual_columns=[str(c) for c in raw_sources[uw_code]["members"].columns],
            key=f"{uw_code}_members_mapping",
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            ai_engine=ai_engine,
            profile_mapping=(
                loaded_profile_mappings.get(uw_code, {}).get("members", {})
                if loaded_profile_mappings
                else None
            ),
        )
        claims_mapping_frame = _editor_for_mapping(
            title=f"{uw_code} Claims Mapping",
            expected_columns=spec.expected_claim_columns,
            actual_columns=[str(c) for c in raw_sources[uw_code]["claims"].columns],
            key=f"{uw_code}_claims_mapping",
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            ai_engine=ai_engine,
            profile_mapping=(
                loaded_profile_mappings.get(uw_code, {}).get("claims", {})
                if loaded_profile_mappings
                else None
            ),
        )

        low_members = int(
            (members_mapping_frame["use"].astype(bool) & (members_mapping_frame["confidence"] == "low")).sum()
        )
        low_claims = int(
            (claims_mapping_frame["use"].astype(bool) & (claims_mapping_frame["confidence"] == "low")).sum()
        )
        total_low = low_members + low_claims
        if total_low > 0:
            st.warning(
                f"{uw_code} has {total_low} selected low-confidence mappings. Review before run."
            )
        else:
            st.success(f"{uw_code} mappings are medium/high confidence.")

        mappings[uw_code]["members"] = mapping_frame_to_dict(members_mapping_frame)
        mappings[uw_code]["claims"] = mapping_frame_to_dict(claims_mapping_frame)
    return mappings


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return cleaned.strip("_") or "run"


def _zip_dir_to_bytes(directory: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=str(file_path.relative_to(directory)))
    return buffer.getvalue()


def _download_file_button(label: str, path: Path, mime: str) -> None:
    if not path.exists() or not path.is_file():
        return
    st.download_button(
        label=label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime,
    )


def main() -> None:
    st.set_page_config(page_title="Claims Pipeline UI", layout="wide")
    st.title("Health Claims Pipeline - Upload and Mapping")
    st.caption(
        "Upload UW files, confirm column mappings, then run the same deterministic backend pipeline."
    )

    specs = get_underwriter_specs(PROJECT_ROOT)
    expected_columns = _build_expected_columns(specs)
    logger.info("UI loaded with template_count=%s", len(specs))

    st.sidebar.header("Output Settings")
    run_mode_label = st.sidebar.selectbox(
        "Pipeline Mode",
        options=[
            "Full (PDF + Power BI CSV)",
            "PDF Only (no Power BI export)",
            "Power BI Handoff (PDF + CSV + PBIX build package)",
        ],
        index=0,
    )
    run_mode = {
        "Full (PDF + Power BI CSV)": "full",
        "PDF Only (no Power BI export)": "pdf_only",
        "Power BI Handoff (PDF + CSV + PBIX build package)": "powerbi_handoff",
    }[run_mode_label]
    pbix_file_name = st.sidebar.text_input(
        "Expected PBIX file name",
        "claims_dashboard.pbix",
        help="Used for the PBIX handoff guide in Power BI Handoff mode.",
    )
    ai_engine_label = st.sidebar.selectbox(
        "AI Mapping Engine",
        options=[
            "SentenceTransformer + Rules (recommended)",
            "Hybrid Rules (fast)",
            "SentenceTransformer + OpenAI Embeddings + Rules",
        ],
        index=0,
    )
    ai_engine = {
        "SentenceTransformer + Rules (recommended)": "sentence_transformer",
        "Hybrid Rules (fast)": "hybrid_rules",
        "SentenceTransformer + OpenAI Embeddings + Rules": "sentence_transformer_openai",
    }[ai_engine_label]
    medium_threshold = st.sidebar.slider(
        "Medium confidence threshold", min_value=0.40, max_value=0.90, value=0.65, step=0.05
    )
    high_threshold = st.sidebar.slider(
        "High confidence threshold", min_value=0.60, max_value=0.98, value=0.85, step=0.05
    )
    if high_threshold <= medium_threshold:
        st.sidebar.error("High threshold must be greater than medium threshold.")
        return

    if ai_engine == "sentence_transformer_openai":
        st.sidebar.caption(
            "Requires OPENAI_API_KEY for embedding stage. If unavailable, mapping falls back to sentence-transformer rules."
        )
    if run_mode == "pdf_only":
        st.sidebar.caption("PDF Only mode skips writing Power BI CSV exports.")
    if run_mode == "powerbi_handoff":
        st.sidebar.caption(
            "Power BI Handoff mode creates a PBIX build package with data, theme, and guides."
        )

    processed_dir = Path(
        st.sidebar.text_input(
            "Processed CSV directory",
            str(PROJECT_ROOT / "data" / "processed"),
        )
    )
    outputs_dir = Path(
        st.sidebar.text_input(
            "Reports/output directory",
            str(PROJECT_ROOT / "outputs"),
        )
    )
    db_path = Path(
        st.sidebar.text_input(
            "SQLite DB path",
            str(PROJECT_ROOT / "outputs" / "claims_analytics.db"),
        )
    )
    powerbi_dir = Path(
        st.sidebar.text_input(
            "Power BI data directory",
            str(PROJECT_ROOT / "powerbi" / "data"),
        )
    )
    report_path = Path(
        st.sidebar.text_input(
            "PDF report path",
            str(PROJECT_ROOT / "outputs" / "Claims_Analysis_Report.pdf"),
        )
    )
    use_llm_narrative = st.sidebar.checkbox(
        "Use LLM narrative for report text",
        value=True,
    )
    profiles_dir = Path(
        st.sidebar.text_input(
            "Mapping profiles directory",
            str(PROJECT_ROOT / "configs" / "mappings"),
        )
    )
    profile_name = st.sidebar.text_input("Mapping profile name", "default_uw_profile")
    auto_run_folder = st.sidebar.checkbox(
        "Auto-create unique run folder (recommended)",
        value=True,
        help="Prevents output files from being overwritten between runs.",
    )
    default_run_label = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_label_input = st.sidebar.text_input(
        "Run label",
        default_run_label,
        help="Used only when auto run folder is enabled.",
    )

    st.subheader("1. Upload Underwriter Files")
    uploaded_files = st.file_uploader(
        "Upload one or more UW templates",
        type=["xlsx"],
        accept_multiple_files=True,
        key="general_uploader",
    )
    if not uploaded_files:
        st.info("Upload at least one UW file to continue.")
        return
    uploaded_count = len(uploaded_files)
    st.caption(
        f"{uploaded_count} UW file(s) uploaded. You can process a single UW or multiple UWs together."
    )

    st.subheader("2. Auto Template Detection and Assignment")
    assignment_frame = _build_assignment_editor(uploaded_files, specs)
    selected_rows = assignment_frame[assignment_frame["assigned_uw"] != "Ignore"]
    if selected_rows.empty:
        st.warning("No files selected for processing. Assign at least one file.")
        return

    duplicated_assignments = selected_rows["assigned_uw"].duplicated(keep=False)
    if duplicated_assignments.any():
        conflict = selected_rows.loc[duplicated_assignments, "assigned_uw"].tolist()
        st.error(f"Multiple files assigned to same UW template: {conflict}. Keep only one per UW.")
        return

    file_lookup = {str(f.name): f for f in uploaded_files}
    selected_uploaded: Dict[str, object] = {}
    for _, row in selected_rows.iterrows():
        selected_uploaded[str(row["assigned_uw"])] = file_lookup[str(row["file_name"])]

    try:
        raw_sources = _read_sources_from_uploaded_files(selected_uploaded, specs)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to read assigned files: {exc}")
        return

    loaded_profile_mappings = None
    st.subheader("3. Mapping Profile (Optional)")
    profile_cols = st.columns(2)
    with profile_cols[0]:
        if st.button("Load Profile", key="load_profile_btn"):
            try:
                profile_path = profiles_dir / f"{profile_name}.json"
                payload = load_mapping_profile(profile_path)
                overall_score, per_table = profile_match_score(payload, raw_sources)
                loaded_profile_mappings = payload["mappings"]  # type: ignore[index]
                st.session_state["loaded_profile_mappings"] = loaded_profile_mappings
                st.session_state["loaded_profile_score"] = overall_score
                st.session_state["loaded_profile_table_scores"] = per_table
                st.success(f"Loaded profile: {profile_path}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Unable to load profile: {exc}")

    if "loaded_profile_mappings" in st.session_state:
        loaded_profile_mappings = st.session_state["loaded_profile_mappings"]
        score = st.session_state.get("loaded_profile_score", 0.0)
        table_scores = st.session_state.get("loaded_profile_table_scores", {})
        if score < 0.75:
            st.warning(f"Loaded profile schema match score is {score:.2f}. Review carefully.")
        else:
            st.success(f"Loaded profile schema match score: {score:.2f}")
        st.json({"schema_match_score": score, "per_table": table_scores})

    st.subheader("4. Confirm Column Mapping")
    st.write(
        "AI suggestions are prefilled with confidence levels. Confirm or edit before pipeline run."
    )
    try:
        mappings = _build_mappings_ui(
            raw_sources,
            specs,
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            ai_engine=ai_engine,
            loaded_profile_mappings=loaded_profile_mappings,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed while preparing mapping editors: {exc}")
        return

    if st.button("Save Current Mapping As Profile", key="save_profile_btn"):
        try:
            saved_path = save_mapping_profile(
                profile_dir=profiles_dir,
                profile_name=profile_name,
                raw_sources=raw_sources,
                mappings=mappings,
                ai_engine=ai_engine,
                medium_threshold=medium_threshold,
                high_threshold=high_threshold,
            )
            st.success(f"Profile saved: {saved_path}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Unable to save profile: {exc}")

    acknowledge_low_conf = st.checkbox(
        "I confirm any low-confidence mappings are reviewed and acceptable.",
        value=False,
    )

    if st.button("Run Pipeline With Confirmed Mappings", type="primary"):
        if not acknowledge_low_conf:
            st.error(
                "Please confirm low-confidence mapping review before running the pipeline."
            )
            return
        try:
            if auto_run_folder:
                run_label = _safe_slug(run_label_input)
                processed_dir_effective = processed_dir / run_label
                outputs_dir_effective = outputs_dir / run_label
                powerbi_dir_effective = powerbi_dir / run_label
                db_path_effective = outputs_dir_effective / db_path.name
                report_path_effective = outputs_dir_effective / report_path.name
                st.info(f"Using run folder: {run_label}")
            else:
                processed_dir_effective = processed_dir
                outputs_dir_effective = outputs_dir
                powerbi_dir_effective = powerbi_dir
                db_path_effective = db_path
                report_path_effective = report_path

            standardized_sources = apply_mappings_to_sources(
                raw_sources, mappings, expected_columns
            )
            result = run_pipeline_from_sources(
                sources=standardized_sources,
                processed_dir=processed_dir_effective,
                outputs_dir=outputs_dir_effective,
                db_path=db_path_effective,
                powerbi_dir=powerbi_dir_effective,
                report_path=report_path_effective,
                use_llm_narrative=use_llm_narrative,
                run_mode=run_mode,
                pbix_file_name=pbix_file_name,
            )
            logger.info(
                "UI pipeline run completed status=%s mode=%s",
                result["status"],
                run_mode,
            )
            if result["status"] == "success":
                st.success("Pipeline executed successfully.")
            else:
                st.warning("Pipeline finished with validation issues.")
            st.json(result["validation"]["summary"])
            st.write(f"master_census.csv: {result['master_census_path']}")
            st.write(f"master_claims.csv: {result['master_claims_path']}")
            st.write(f"validation_report.json: {result['validation_report_path']}")
            st.write(f"claims_analytics.db: {result['database_path']}")
            st.write(f"powerbi_data_dir: {result['powerbi_dir']}")
            if result.get("powerbi_outputs"):
                st.write("Power BI CSV exports generated.")
            else:
                st.write("Power BI CSV exports skipped in selected mode.")
            if result.get("pbix_handoff"):
                handoff = result["pbix_handoff"]
                st.success("PBIX handoff package generated.")
                st.write(f"pbix_handoff_package: {handoff['package_dir']}")
                st.write(f"pbix_build_guide: {handoff['build_guide']}")
                st.write(f"expected_pbix_path: {handoff['expected_pbix_path']}")
            st.write(f"report_pdf: {result['report_pdf_path']}")

            st.subheader("Downloads")
            report_pdf_path = Path(result["report_pdf_path"])
            _download_file_button("Download PDF Report", report_pdf_path, "application/pdf")

            validation_path = Path(result["validation_report_path"])
            _download_file_button("Download Validation Report (JSON)", validation_path, "application/json")

            if result.get("pbix_handoff"):
                handoff_dir = Path(result["pbix_handoff"]["package_dir"])
                guide_path = Path(result["pbix_handoff"]["build_guide"])
                _download_file_button("Download PBIX Build Guide", guide_path, "text/markdown")
                handoff_zip = _zip_dir_to_bytes(handoff_dir)
                st.download_button(
                    label="Download Power BI Handoff Package (ZIP)",
                    data=handoff_zip,
                    file_name=f"{handoff_dir.name}.zip",
                    mime="application/zip",
                )
            elif result.get("powerbi_outputs"):
                powerbi_export_dir = Path(result["powerbi_dir"])
                if powerbi_export_dir.exists():
                    powerbi_zip = _zip_dir_to_bytes(powerbi_export_dir)
                    st.download_button(
                        label="Download Power BI CSV Exports (ZIP)",
                        data=powerbi_zip,
                        file_name=f"{powerbi_export_dir.name}.zip",
                        mime="application/zip",
                    )
        except Exception as exc:  # noqa: BLE001
            logger.exception("UI pipeline run failed")
            st.error(f"Pipeline run failed: {exc}")


if __name__ == "__main__":
    main()
