from __future__ import annotations

from typing import Any, Protocol, TypedDict


class ConnLike(Protocol):
    def cursor(self, *args: Any, **kwargs: Any) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class Receipt(TypedDict, total=False):
    disbursed: bool
    loan_id: str
    amount: float
    asOf: str
    auto_approved: bool
    approved_by: str
    note: str
