"""Types cho gated (T11-2 — tách khỏi gated.py giữ ≤400 LOC). Annotation-only, 0 runtime."""

from __future__ import annotations

from typing import Any, Protocol, TypedDict


class ConnLike(Protocol):
    """conn 'quack' — psycopg2 connection dùng trong gated. inner tool (disburse) nhận conn này,
    gọi .cursor() ghi SAME tx."""

    def cursor(self, *args: Any, **kwargs: Any) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class Receipt(TypedDict, total=False):
    """Biên nhận GATED_TOOLS trả (total=False — auto-path enrich thêm auto_approved/approved_by/note,
    stub disburse trả 4 key gốc). Type surface, không ép shape runtime."""

    disbursed: bool
    loan_id: str
    amount: float
    asOf: str
    auto_approved: bool
    approved_by: str
    note: str
