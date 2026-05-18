from __future__ import annotations

import json
import logging
import math
import os
import re
import time
import sys
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from claims_pipeline.usage_metrics import (
    record_api_call,
    record_openai_usage_from_response,
)


DOMAIN_ALIASES: Dict[str, List[str]] = {
    "member_name": ["member name", "employee full name", "first name", "last name", "name"],
    "date_of_birth": ["dob", "date of birth", "birth date", "dob yyyymmdd", "excel serial"],
    "gender": ["sex", "gender", "gender cd"],
    "relationship": ["relation", "rel code", "relationship", "principal", "spouse", "child"],
    "benefit_class": ["class", "grade", "benefit category", "cover type"],
    "network_tier": ["network", "network tier", "sub-network", "network_1"],
    "annual_premium": ["annual prem", "annual premium", "annual prem usd", "annual premium qar"],
    "claim_id": ["claim id", "claim ref", "trans id"],
    "service_date": ["service date", "date of service", "svc dt"],
    "claim_date": ["claim dt", "submission date"],
    "icd_code": ["icd code", "icd-10 code", "diagnosis cd"],
    "diagnosis": ["diagnosis", "disease description", "diagnosis text"],
    "illness_type": ["claim category", "illness catg", "disease category"],
    "benefit_type": ["service type", "benefit cd", "service category", "sub-type"],
    "provider_name": ["provider", "prov name", "provider name"],
    "paid_amount": ["paid", "insurer share", "paid usd", "paid fils", "paid qar"],
    "copay": ["copay", "deductible", "member copay"],
}

_SENTENCE_MODEL = None
_SENTENCE_MODEL_NAME = ""
logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", name.lower())
    return normalized


def _tokenize(name: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def _token_jaccard(a: str, b: str) -> float:
    ta, tb = set(_tokenize(a)), set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _alias_semantic_score(a: str, b: str) -> float:
    a_l, b_l = a.lower(), b.lower()
    best = 0.0
    for alias_group in DOMAIN_ALIASES.values():
        in_a = any(alias in a_l for alias in alias_group)
        in_b = any(alias in b_l for alias in alias_group)
        if in_a and in_b:
            best = max(best, 1.0)
        elif in_a or in_b:
            best = max(best, 0.4)
    return best


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _embedding_scores(
    expected_columns: List[str],
    actual_columns: List[str],
    engine: str,
) -> Dict[Tuple[str, str], float]:
    if engine not in {"openai_embeddings", "sentence_transformer_openai"}:
        return {}
    if not os.getenv("OPENAI_API_KEY"):
        return {}

    try:
        from openai import OpenAI
    except Exception:
        return {}

    client = OpenAI()
    all_texts = expected_columns + actual_columns
    try:
        started = time.perf_counter()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=all_texts,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        record_api_call(kind="embeddings", model="text-embedding-3-small", success=True)
        record_openai_usage_from_response(response, model="text-embedding-3-small")
        logger.info(
            "Embedding call success model=%s texts=%s latency_ms=%s",
            "text-embedding-3-small",
            len(all_texts),
            elapsed_ms,
        )
    except Exception:
        record_api_call(kind="embeddings", model="text-embedding-3-small", success=False)
        logger.warning("Embedding call failed model=%s", "text-embedding-3-small")
        return {}

    vectors = [item.embedding for item in response.data]
    expected_vecs = vectors[: len(expected_columns)]
    actual_vecs = vectors[len(expected_columns) :]

    scores: Dict[Tuple[str, str], float] = {}
    for i, expected in enumerate(expected_columns):
        for j, actual in enumerate(actual_columns):
            sim = _cosine_similarity(expected_vecs[i], actual_vecs[j])
            # Convert cosine [-1, 1] to [0, 1] for easier blending.
            scores[(expected, actual)] = round((sim + 1.0) / 2.0, 6)
    return scores


def _sentence_transformer_model():
    global _SENTENCE_MODEL, _SENTENCE_MODEL_NAME
    model_name = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    if _SENTENCE_MODEL is not None and _SENTENCE_MODEL_NAME == model_name:
        return _SENTENCE_MODEL

    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None

    try:
        _SENTENCE_MODEL = SentenceTransformer(model_name)
        _SENTENCE_MODEL_NAME = model_name
        return _SENTENCE_MODEL
    except Exception:
        return None


def _sentence_transformer_scores(
    expected_columns: List[str],
    actual_columns: List[str],
    engine: str,
) -> Dict[Tuple[str, str], float]:
    if engine not in {"sentence_transformer", "sentence_transformer_openai"}:
        return {}
    # Guard for unstable runtime combinations (observed crashes in Python 3.14).
    if sys.version_info >= (3, 13):
        return {}
    model = _sentence_transformer_model()
    if model is None:
        return {}

    all_texts = expected_columns + actual_columns
    try:
        vectors = model.encode(all_texts, normalize_embeddings=True)
    except Exception:
        return {}

    expected_vecs = vectors[: len(expected_columns)]
    actual_vecs = vectors[len(expected_columns) :]

    scores: Dict[Tuple[str, str], float] = {}
    for i, expected in enumerate(expected_columns):
        for j, actual in enumerate(actual_columns):
            # Normalized embeddings -> dot product in [-1, 1]
            sim = float((expected_vecs[i] * actual_vecs[j]).sum())
            scores[(expected, actual)] = round((sim + 1.0) / 2.0, 6)
    return scores


def _extract_json_object(text: str) -> Dict[str, str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return {}
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    snippet = cleaned[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) if v is not None else "" for k, v in parsed.items()}


def _llm_fallback_mapping(
    expected_columns: List[str],
    actual_columns: List[str],
) -> Dict[str, str]:
    if not expected_columns or not actual_columns:
        return {}
    if not os.getenv("AZURE_OPENAI_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        return {}

    try:
        from openai import AzureOpenAI, OpenAI
    except Exception:
        return {}

    prompt = (
        "Map expected column names to actual source column names.\n"
        "Rules:\n"
        "1) Return JSON object only.\n"
        "2) Keys must exactly be expected columns.\n"
        "3) Values must be one of provided actual columns, or empty string if no good match.\n"
        "4) No commentary.\n\n"
        f"expected_columns={json.dumps(expected_columns)}\n"
        f"actual_columns={json.dumps(actual_columns)}"
    )

    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    model_name = "unknown"
    client = None
    if azure_key and azure_endpoint and azure_deployment:
        try:
            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version=azure_api_version,
            )
            model_name = azure_deployment
        except Exception:
            client = None
    elif os.getenv("OPENAI_API_KEY"):
        try:
            client = OpenAI()
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        except Exception:
            client = None

    if client is None:
        return {}

    try:
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a precise schema mapping assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        record_api_call(kind="chat_completions", model=model_name, success=True)
        record_openai_usage_from_response(response, model=model_name)
        logger.info(
            "LLM mapping fallback success model=%s expected_cols=%s actual_cols=%s latency_ms=%s",
            model_name,
            len(expected_columns),
            len(actual_columns),
            elapsed_ms,
        )
    except Exception:
        record_api_call(kind="chat_completions", model=model_name, success=False)
        logger.warning(
            "LLM mapping fallback failed model=%s expected_cols=%s actual_cols=%s",
            model_name,
            len(expected_columns),
            len(actual_columns),
        )
        return {}

    content = response.choices[0].message.content if response.choices else ""
    parsed = _extract_json_object(content or "")
    valid = {str(c) for c in actual_columns}
    return {
        expected: suggestion
        for expected, suggestion in parsed.items()
        if expected in expected_columns and suggestion in valid
    }


def _confidence_bucket(score: float, high_threshold: float, medium_threshold: float) -> str:
    if score >= high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"


def suggest_column_mappings(
    expected_columns: Iterable[str],
    actual_columns: Iterable[str],
    min_score: float = 0.35,
    high_threshold: float = 0.85,
    medium_threshold: float = 0.65,
    ai_engine: str = "hybrid_rules",
    llm_fallback: bool = True,
) -> pd.DataFrame:
    actual_list = [str(col) for col in actual_columns]
    expected_list = [str(col) for col in expected_columns]
    embedding_lookup = _embedding_scores(expected_list, actual_list, ai_engine)
    sentence_lookup = _sentence_transformer_scores(expected_list, actual_list, ai_engine)
    rows = []
    unresolved_expected: List[str] = []
    for expected in expected_list:
        best_source = ""
        best_score = 0.0
        best_name_score = 0.0
        best_token_score = 0.0
        best_semantic_score = 0.0
        best_embedding_score = 0.0
        best_sentence_score = 0.0

        for actual in actual_list:
            name_score = _similarity(str(expected), actual)
            token_score = _token_jaccard(str(expected), actual)
            semantic_score = _alias_semantic_score(str(expected), actual)
            embedding_score = embedding_lookup.get((expected, actual), 0.0)
            sentence_score = sentence_lookup.get((expected, actual), 0.0)

            if embedding_lookup:
                score = (
                    0.30 * name_score
                    + 0.15 * token_score
                    + 0.10 * semantic_score
                    + 0.25 * embedding_score
                    + 0.20 * sentence_score
                )
            elif sentence_lookup:
                score = (
                    0.30 * name_score
                    + 0.20 * token_score
                    + 0.15 * semantic_score
                    + 0.35 * sentence_score
                )
            else:
                score = 0.55 * name_score + 0.25 * token_score + 0.20 * semantic_score

            if score > best_score:
                best_score = round(score, 6)
                best_source = actual
                best_name_score = round(name_score, 6)
                best_token_score = round(token_score, 6)
                best_semantic_score = round(semantic_score, 6)
                best_embedding_score = round(embedding_score, 6)
                best_sentence_score = round(sentence_score, 6)

        if best_score < min_score:
            best_source = ""
            confidence = "low"
            recommended = False
            unresolved_expected.append(expected)
        else:
            confidence = _confidence_bucket(best_score, high_threshold, medium_threshold)
            recommended = confidence in {"high", "medium"}
        rows.append(
            {
                "expected_column": expected,
                "source_column": best_source,
                "score": round(best_score, 3),
                "confidence": confidence,
                "name_score": round(best_name_score, 3),
                "token_score": round(best_token_score, 3),
                "semantic_score": round(best_semantic_score, 3),
                "embedding_score": round(best_embedding_score, 3),
                "sentence_score": round(best_sentence_score, 3),
                "llm_fallback_used": False,
                "recommended": recommended,
                "use": bool(best_source) and recommended,
            }
        )
    suggestions = pd.DataFrame(rows)

    llm_fallback_applied = 0
    if llm_fallback and unresolved_expected:
        llm_map = _llm_fallback_mapping(unresolved_expected, actual_list)
        if llm_map:
            already_used = {
                str(v).strip()
                for v in suggestions["source_column"].fillna("").astype(str).tolist()
                if str(v).strip()
            }
            for idx, row in suggestions.iterrows():
                expected = str(row["expected_column"])
                if expected not in llm_map:
                    continue
                suggestion = str(llm_map[expected]).strip()
                if not suggestion or suggestion not in actual_list:
                    continue
                if suggestion in already_used:
                    continue
                suggestions.at[idx, "source_column"] = suggestion
                suggestions.at[idx, "score"] = max(float(suggestions.at[idx, "score"]), round(min_score + 0.01, 3))
                suggestions.at[idx, "confidence"] = "medium"
                suggestions.at[idx, "recommended"] = True
                suggestions.at[idx, "use"] = True
                suggestions.at[idx, "llm_fallback_used"] = True
                already_used.add(suggestion)
                llm_fallback_applied += 1

    if sentence_lookup:
        logger.info(
            "Column mapping semantic stage active: engine=%s expected=%s actual=%s",
            ai_engine,
            len(expected_list),
            len(actual_list),
        )
    if llm_fallback_applied > 0:
        logger.info(
            "Column mapping llm fallback applied: mappings=%s unresolved=%s",
            llm_fallback_applied,
            len(unresolved_expected),
        )

    return suggestions


def mapping_frame_to_dict(mapping_frame: pd.DataFrame) -> Dict[str, str]:
    required_cols = {"expected_column", "source_column", "use"}
    if not required_cols.issubset(mapping_frame.columns):
        raise ValueError("Mapping frame must include expected_column, source_column, and use")

    mapping: Dict[str, str] = {}
    used_sources: set[str] = set()
    for _, row in mapping_frame.iterrows():
        if not bool(row["use"]):
            continue
        expected = str(row["expected_column"])
        source_value = row["source_column"]
        if pd.isna(source_value):
            continue
        source = str(source_value).strip()
        if not source:
            continue
        if source in used_sources:
            raise ValueError(f"Source column '{source}' is assigned multiple times")
        mapping[expected] = source
        used_sources.add(source)
    return mapping


def apply_column_mapping(
    df: pd.DataFrame,
    expected_columns: Iterable[str],
    mapping: Dict[str, str],
) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    missing = []
    for expected in expected_columns:
        if expected not in mapping:
            missing.append(expected)
            continue
        source = mapping[expected]
        if source not in df.columns:
            missing.append(expected)
            continue
        out[expected] = df[source]

    if missing:
        raise ValueError(f"Missing mapped columns: {missing}")
    return out


def apply_mappings_to_sources(
    raw_sources: Dict[str, Dict[str, pd.DataFrame]],
    mappings: Dict[str, Dict[str, Dict[str, str]]],
    expected_columns: Dict[str, Dict[str, Iterable[str]]],
) -> Dict[str, Dict[str, pd.DataFrame]]:
    standardized: Dict[str, Dict[str, pd.DataFrame]] = {}
    for uw_code, source_tables in raw_sources.items():
        standardized[uw_code] = {}
        for table_key in ("members", "claims"):
            table_mapping = mappings[uw_code][table_key]
            table_expected_cols = expected_columns[uw_code][table_key]
            standardized[uw_code][table_key] = apply_column_mapping(
                source_tables[table_key], table_expected_cols, table_mapping
            )
    return standardized


def apply_profile_mapping_to_suggestions(
    suggestions: pd.DataFrame,
    profile_mapping: Dict[str, str] | None,
    actual_columns: Iterable[str],
) -> pd.DataFrame:
    if not profile_mapping:
        return suggestions

    out = suggestions.copy()
    valid_actual = {str(c) for c in actual_columns}
    for idx, row in out.iterrows():
        expected = str(row["expected_column"])
        if expected not in profile_mapping:
            continue
        source = str(profile_mapping[expected]).strip()
        if source not in valid_actual:
            continue
        out.at[idx, "source_column"] = source
        out.at[idx, "use"] = True
    return out
