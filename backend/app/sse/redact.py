"""Redact secret trước khi bắn ra FE/trace (khẩu vị bank — streaming-sse §4).

Output agent/tool đi ra FE không được mang secret. Gọi trong emit() — cổng DUY NHẤT.
"""

from __future__ import annotations

import re
from typing import Any

_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED:api-key]"),
    (
        re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]+?-----END[A-Z ]*PRIVATE KEY-----"),
        "[REDACTED:private-key]",
    ),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED:aws-key]"),
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
        "[REDACTED:jwt]",
    ),
    (re.compile(r"[A-Za-z0-9+/=]{400,}"), "[REDACTED:blob]"),
]


def redact_deep(obj: Any) -> Any:
    if isinstance(obj, str):
        for p, r in _PATTERNS:
            obj = p.sub(r, obj)
        return obj
    if isinstance(obj, dict):
        return {k: redact_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_deep(v) for v in obj]
    return obj
