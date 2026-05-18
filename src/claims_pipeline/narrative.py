from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Dict, List

from claims_pipeline.usage_metrics import (
    record_api_call,
    record_openai_usage_from_response,
)

logger = logging.getLogger(__name__)


def _fallback_narrative(context: Dict[str, object]) -> Dict[str, object]:
    total_claims = context.get("total_claims", 0)
    total_paid = context.get("total_paid_usd", 0.0)
    loss_ratio = context.get("loss_ratio_pct", 0.0)
    top_provider = context.get("top_provider_name", "N/A")
    top_provider_share = context.get("top_provider_share_pct", 0.0)
    top_diag = context.get("top_diagnosis", "N/A")

    return {
        "executive_summary": (
            f"Portfolio includes {total_claims} claims with total paid amount USD {total_paid:,.2f}. "
            f"Current modeled loss ratio is {loss_ratio:.1f}% based on available premium fields."
        ),
        "key_findings": [
            f"Top provider concentration is {top_provider_share:.1f}% at {top_provider}.",
            f"Most frequent chronic diagnosis observed: {top_diag}.",
            "Inpatient and chronic segments should be monitored as cost drivers.",
        ],
        "recommendations": [
            "Introduce provider concentration review for top-spend facilities.",
            "Launch chronic disease management interventions for top diagnosis groups.",
            "Tighten pre-authorization rules for high-value inpatient episodes.",
        ],
        "clinical_insights": [
            f"{top_diag} appears as a recurrent diagnosis in this dataset.",
            "Chronic and maternity categories require preventive care tracking.",
            "Mental health episodes are low frequency but should be monitored.",
        ],
        "methodology_notes": [
            "Currency normalization follows assignment conversion rules per UW template.",
            "KPI metrics are computed from transformed master_claims and master_census outputs.",
        ],
    }


def _llm_narrative(context: Dict[str, object]) -> Dict[str, object] | None:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    if not api_key or not endpoint or not deployment:
        logger.info("LLM narrative disabled: Azure OpenAI environment not configured")
        return None

    try:
        from openai import AzureOpenAI
    except Exception as exc:
        logger.warning("LLM narrative disabled: openai package import failed: %s", exc.__class__.__name__)
        return None

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    prompt = (
        "You are preparing a client-facing health claims executive brief.\n"
        "Generate high-quality, business-ready narrative in STRICT JSON only (no markdown, no prose outside JSON).\n\n"
        "Required JSON schema:\n"
        "{\n"
        '  "executive_summary": "string",\n'
        '  "key_findings": ["string", "string", "string"],\n'
        '  "recommendations": ["string", "string", "string"],\n'
        '  "clinical_insights": ["string", "string", "string"],\n'
        '  "methodology_notes": ["string", "string"]\n'
        "}\n\n"
        "Content rules:\n"
        "1) Use only provided metrics. Do not fabricate values, entities, diagnoses, or trends.\n"
        "2) Executive summary must be 4-6 sentences with clear business meaning, risk signal, and portfolio context.\n"
        "3) Key findings must be insight-led (what it means), not just metric restatement.\n"
        "4) Recommendations must be practical and action-oriented for insurer/employer decision-making.\n"
        "5) Clinical insights should highlight utilization pattern implications and monitoring priorities.\n"
        "6) Methodology notes should be concise and audit-friendly.\n"
        "7) Keep tone professional, precise, and suitable for leadership review.\n\n"
        f"METRICS_JSON={json.dumps(context)}"
    )

    try:
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior insurance analytics consultant writing executive-level "
                        "health claims insights with high clarity and strong business framing."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        record_api_call(kind="chat_completions", model=deployment, success=True)
        record_openai_usage_from_response(response, model=deployment)
        logger.info(
            "LLM narrative call success model=%s latency_ms=%s",
            deployment,
            elapsed_ms,
        )
        text = response.choices[0].message.content or ""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
        try:
            parsed = json.loads(cleaned)
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            parsed = json.loads(cleaned[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        record_api_call(kind="chat_completions", model=deployment, success=False)
        logger.warning(
            "LLM narrative call failed model=%s error=%s",
            deployment,
            exc.__class__.__name__,
        )
        return None


def generate_report_narrative(context: Dict[str, object], use_llm: bool = True) -> Dict[str, object]:
    if use_llm:
        narrative = _llm_narrative(context)
        if narrative:
            return narrative
    return _fallback_narrative(context)
