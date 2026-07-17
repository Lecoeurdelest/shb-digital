"""PGConnAdapter — bọc psycopg2 conn "quack như sqlite3.Connection" (DECISIONS D-27).

credit.py/customers.py (copy byte-nguyên từ LAB, KHÔNG được sửa — N1) dùng 3 thứ psycopg2
raw KHÔNG có:
  1. `conn.execute(sql, args)` — psycopg2 Connection không có `.execute()`, chỉ `.cursor()`.
  2. Placeholder `?` — psycopg2 chỉ nhận `%s`.
  3. Row access HỖN HỢP trong cùng file: `dict(r)` (mapping theo tên cột) VÀ `r[0]`/`r[1]`
     (index) — không cursor stock nào phủ cả 2 (RealDictCursor phá index, cursor thường phá
     dict(row)). Adapter tự viết Row wrapper phủ cả 2 (task T1-1 Logic mục C).

Đây là lớp CẤP-CONN của vỏ (D-21 cách A2) — KHÔNG đụng logic tool.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import psycopg2
import psycopg2.extensions
import psycopg2.pool

from app.db.config import DATABASE_URL

# match `?` placeholder ngoài chuỗi literal ('...'/"..."). credit.py/customers.py không có
# `?` trong string literal nào (verify: grep "'.*?.*'" rỗng) — nhưng regex vẫn tránh quote-aware
# thay vì .replace('?', '%s') trần, phòng LAB thêm literal có `?` sau này (defensive, N1-an toàn:
# vẫn KHÔNG chạm credit.py, chỉ adapter cẩn thận hơn).
_PLACEHOLDER_RE = re.compile(r"\?|'[^']*'|\"[^\"]*\"")


def _rewrite_placeholders(sql: str) -> str:
    """`?` -> `%s`, bỏ qua `?` nằm trong string literal."""

    def _sub(m: re.Match[str]) -> str:
        tok = m.group(0)
        return "%s" if tok == "?" else tok

    return _PLACEHOLDER_RE.sub(_sub, sql)


class Row:
    """Row wrapper quack-như-sqlite3.Row: hỗ trợ CẢ index (`row[0]`) CẢ mapping
    (`row['col']`, `dict(row)`) — sqlite3.Row hỗ trợ cả 3, không cursor stock nào của
    psycopg2 phủ đủ (task T1-1 Logic mục C)."""

    __slots__ = ("_values", "_cols")

    def __init__(self, values: tuple[Any, ...], cols: list[str]) -> None:
        self._values = values
        self._cols = cols

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, str):
            try:
                idx = self._cols.index(key)
            except ValueError as e:
                raise KeyError(key) from e
            return self._values[idx]
        return self._values[key]

    def keys(self) -> list[str]:
        return list(self._cols)

    def __iter__(self) -> Iterator[Any]:
        # dict(row) gọi keys() rồi __getitem__ nếu có .keys(); nhưng cũng hỗ trợ
        # dict(zip(row.keys(), row)) style — iter trên VALUES khớp sqlite3.Row.__iter__.
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return f"Row({dict(zip(self._cols, self._values, strict=False))!r})"


class _AdapterCursor:
    """Cursor-like trả về từ `PGConnAdapter.execute()` — hỗ trợ `.fetchone()`/`.fetchall()`
    y hệt kết quả `sqlite3.Connection.execute(...)` mà credit.py/customers.py xích thẳng."""

    def __init__(self, pg_cursor: psycopg2.extensions.cursor) -> None:
        self._cur = pg_cursor
        self._cols = [d.name for d in (pg_cursor.description or [])]

    def fetchone(self) -> Row | None:
        row = self._cur.fetchone()
        return Row(tuple(row), self._cols) if row is not None else None

    def fetchall(self) -> list[Row]:
        return [Row(tuple(r), self._cols) for r in self._cur.fetchall()]

    def close(self) -> None:
        self._cur.close()


class PGConnAdapter:
    """Bọc 1 pooled psycopg2 connection, cấp `.execute(sql, params=())` giả lập
    `sqlite3.Connection.execute` — điểm ghép DUY NHẤT giữa fn LAB thuần-sqlite và PG thật.

    credit.py gọi `.execute()` nhiều lần/1 call (mỗi lần 1 cursor). Adapter track các cursor
    đã mở → `close_cursors()` dọn hết trong finally của mount wrapper (tránh cursor mồ côi tích
    lũy khi conn sống dài qua pool). fn LAB KHÔNG gọi close (không biết cursor) — vỏ dọn hộ."""

    def __init__(self, pg_conn: psycopg2.extensions.connection) -> None:
        self._conn = pg_conn
        self._cursors: list[psycopg2.extensions.cursor] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _AdapterCursor:
        pg_sql = _rewrite_placeholders(sql)
        cur = self._conn.cursor()
        try:
            cur.execute(pg_sql, params)
        except Exception:
            cur.close()
            raise
        self._cursors.append(cur)
        return _AdapterCursor(cur)

    def close_cursors(self) -> None:
        """Đóng mọi cursor đã mở trong call này (mount wrapper gọi trong finally)."""
        for c in self._cursors:
            try:
                c.close()
            except psycopg2.Error:
                pass
        self._cursors.clear()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


# ---------------------------------------------------------------------------
# Pool — psycopg2 sync conn (DECISIONS D-22: chạy trong run_in_executor ở T1-2)
# ---------------------------------------------------------------------------

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)
    return _pool


def acquire() -> psycopg2.extensions.connection:
    return get_pool().getconn()


def release(conn: psycopg2.extensions.connection) -> None:
    get_pool().putconn(conn)
