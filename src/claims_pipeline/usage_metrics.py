from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


_metrics: Dict[str, Any] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_usage_metrics(context: Dict[str, Any] | None = None) -> None:
    global _metrics
    _metrics = {
        "started_at_utc": _utc_now_iso(),
        "finished_at_utc": None,
        "duration_seconds": None,
        "api_calls_total": 0,
        "api_calls_by_kind": {
            "chat_completions": 0,
            "embeddings": 0,
        },
        "api_errors_total": 0,
        "token_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        },
        "models": {},
        "context": context or {},
    }


def _ensure_init() -> None:
    if not _metrics:
        reset_usage_metrics()


def record_api_call(kind: str, model: str = "unknown", success: bool = True) -> None:
    _ensure_init()
    _metrics["api_calls_total"] += 1
    if kind not in _metrics["api_calls_by_kind"]:
        _metrics["api_calls_by_kind"][kind] = 0
    _metrics["api_calls_by_kind"][kind] += 1

    if not success:
        _metrics["api_errors_total"] += 1

    model_key = model or "unknown"
    if model_key not in _metrics["models"]:
        _metrics["models"][model_key] = {
            "api_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    _metrics["models"][model_key]["api_calls"] += 1


def record_token_usage(
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    model: str = "unknown",
) -> None:
    _ensure_init()
    _metrics["token_usage"]["input_tokens"] += int(input_tokens or 0)
    _metrics["token_usage"]["output_tokens"] += int(output_tokens or 0)
    _metrics["token_usage"]["total_tokens"] += int(total_tokens or 0)

    model_key = model or "unknown"
    if model_key not in _metrics["models"]:
        _metrics["models"][model_key] = {
            "api_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    _metrics["models"][model_key]["input_tokens"] += int(input_tokens or 0)
    _metrics["models"][model_key]["output_tokens"] += int(output_tokens or 0)
    _metrics["models"][model_key]["total_tokens"] += int(total_tokens or 0)


def record_openai_usage_from_response(response: Any, model: str = "unknown") -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    # For embeddings responses, completion tokens are usually not provided.
    if total_tokens == 0 and input_tokens > 0:
        total_tokens = input_tokens

    record_token_usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=model,
    )


def get_usage_metrics() -> Dict[str, Any]:
    _ensure_init()
    return json.loads(json.dumps(_metrics))


def finalize_usage_metrics() -> Dict[str, Any]:
    _ensure_init()
    finished = datetime.now(timezone.utc)
    started = datetime.fromisoformat(_metrics["started_at_utc"])
    _metrics["finished_at_utc"] = finished.isoformat()
    _metrics["duration_seconds"] = round((finished - started).total_seconds(), 3)
    return get_usage_metrics()


def write_usage_metrics(path: Path) -> str:
    payload = finalize_usage_metrics()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)
