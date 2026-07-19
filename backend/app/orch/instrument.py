"""instrument (T16-1) — bóc chỉ số THẬT từ ResultMessage (SDK) + log có cấu trúc per-turn.

ResultMessage.usage/model_usage/total_cost_usd/duration_ms hiện bị vứt (main_session/sub_runner
`elif ResultMessage: pass`). Bóc → lưu tasks (sub) / message metadata (main) → nguồn stats T16-2.

MAPPING KEY THẬT (capture live zai/glm-4.6, 19/7 — advisor: tránh silent-null vì cột ≠ key SDK):
- usage top-level SNAKE_CASE: input_tokens · output_tokens · cache_read_input_tokens ·
  cache_creation_input_tokens (KHÁC tên cột cache_read_tokens/cache_create_tokens → map TAY).
- model = KEY của model_usage dict (KHÔNG có scalar msg.model). Nhiều model → lấy key đầu (thường 1).
- total_cost_usd + duration_ms = field scalar (duration_ms = MODEL time, không phải ended-started DB).
Defensive: usage/model_usage vắng (provider lạ / lỗi) → field None SẠCH, KHÔNG vỡ turn.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("orch.instrument")
_turn_log = logging.getLogger("orch.turn")  # per-turn structured log (T15-2 evidence)


def extract_metrics(msg: Any) -> dict[str, Any]:
    """ResultMessage → {input_tokens, output_tokens, cache_read_tokens, cache_create_tokens,
    duration_ms, model, cost_usd}. Field vắng → None (không vỡ). KHÔNG raise."""
    usage = getattr(msg, "usage", None) or {}
    model_usage = getattr(msg, "model_usage", None) or {}
    # model THẬT = key model_usage (không scalar field). Nhiều key → nối (hiếm; thường 1 model/turn).
    model = None
    if isinstance(model_usage, dict) and model_usage:
        keys = list(model_usage.keys())
        model = keys[0] if len(keys) == 1 else ",".join(keys)
    return {
        "input_tokens": _int(usage.get("input_tokens")),
        "output_tokens": _int(usage.get("output_tokens")),
        "cache_read_tokens": _int(usage.get("cache_read_input_tokens")),  # cột ≠ key SDK — map TAY
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
    """1 dòng log có cấu trúc/turn (T15-2 evidence — bằng chứng MÁY 'model/base_url đổi per-turn').

    base_url = từ env RESOLVED thực sự đẩy vào SDK (KHÔNG conv.provider — có thể null→effective).
    provider lạ / cost ngoài Anthropic → vẫn ghi (FE label 'ước tính'). KHÔNG raise (best-effort)."""
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
    except Exception:  # noqa: BLE001 — log không bao giờ vỡ turn
        pass
