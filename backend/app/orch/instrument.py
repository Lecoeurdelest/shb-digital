from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("orch.instrument")
_turn_log = logging.getLogger("orch.turn")  # per-turn structured log (T15-2 evidence)


def extract_metrics(msg: Any) -> dict[str, Any]:

    usage = getattr(msg, "usage", None) or {}
    model_usage = getattr(msg, "model_usage", None) or {}

    model = None
    if isinstance(model_usage, dict) and model_usage:
        keys = list(model_usage.keys())
        model = keys[0] if len(keys) == 1 else ",".join(keys)
    return {
        "input_tokens": _int(usage.get("input_tokens")),
        "output_tokens": _int(usage.get("output_tokens")),
        "cache_read_tokens": _int(usage.get("cache_read_input_tokens")),
        "cache_create_tokens": _int(usage.get("cache_creation_input_tokens")),
        "duration_ms": _int(getattr(msg, "duration_ms", None)),  # MODEL time (field SDK)
        "model": model,
        "cost_usd": _float(getattr(msg, "total_cost_usd", None)),
    }


def _int(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def log_turn(
    *, conv_id: str, actor: str, provider: str | None, model: str | None, base_url: str | None, metrics: dict[str, Any]
) -> None:

    try:
        _turn_log.info(
            "turn conv=%s actor=%s provider=%s model=%s base_url=%s duration_ms=%s "
            "in_tok=%s out_tok=%s cache_read=%s cache_create=%s cost_usd=%s",
            conv_id,
            actor,
            provider,
            metrics.get("model") or model,
            base_url or "(default)",
            metrics.get("duration_ms"),
            metrics.get("input_tokens"),
            metrics.get("output_tokens"),
            metrics.get("cache_read_tokens"),
            metrics.get("cache_create_tokens"),
            metrics.get("cost_usd"),
        )
    except Exception:  # noqa: BLE001
        pass
