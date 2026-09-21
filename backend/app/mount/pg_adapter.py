from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import psycopg2
import psycopg2.extensions

from app.storage.registry import get_registry

_PLACEHOLDER_RE = re.compile(r"\?|'[^']*'|\"[^\"]*\"")


def _rewrite_placeholders(sql: str) -> str:

    def _sub(m: re.Match[str]) -> str:
        tok = m.group(0)
        return "%s" if tok == "?" else tok

    return _PLACEHOLDER_RE.sub(_sub, sql)


_WRITE_HEAD_RE = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|REPLACE|MERGE|GRANT)\b", re.IGNORECASE
)
_ALLOWED_WRITE_RE = re.compile(r"^\s*INSERT\s+INTO\s+assessments\b", re.IGNORECASE)


def _is_write(sql: str) -> bool:

    return _WRITE_HEAD_RE.match(sql) is not None


def _is_allowed_write(sql: str) -> bool:

    return _ALLOWED_WRITE_RE.match(sql) is not None


class Row:
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

        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:  # pragma: no cover — debug aid
        return f"Row({dict(zip(self._cols, self._values, strict=False))!r})"


def _coerce_row(row: tuple[Any, ...]) -> tuple[Any, ...]:

    return tuple(bytes(v) if isinstance(v, memoryview) else v for v in row)


class _AdapterCursor:
    def __init__(self, pg_cursor: psycopg2.extensions.cursor, lastrowid: int | None = None) -> None:
        self._cur = pg_cursor
        self._cols = [d.name for d in (pg_cursor.description or [])]
        self.lastrowid = lastrowid

    def fetchone(self) -> Row | None:
        row = self._cur.fetchone()
        return Row(_coerce_row(row), self._cols) if row is not None else None

    def fetchall(self) -> list[Row]:
        return [Row(_coerce_row(r), self._cols) for r in self._cur.fetchall()]

    def close(self) -> None:
        self._cur.close()


class PGConnAdapter:
    def __init__(self, pg_conn: psycopg2.extensions.connection) -> None:
        self._conn = pg_conn
        self._cursors: list[psycopg2.extensions.cursor] = []

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> _AdapterCursor:

        if _is_write(sql) and not _is_allowed_write(sql):
            raise PermissionError(
                "adapter writes are restricted to 'INSERT INTO assessments' (D-55b); this statement was blocked: "
                f"{sql.strip()[:80]!r}. Reads (SELECT) and assessment inserts are allowed; other writes indicate "
                "a configuration error."
            )
        pg_sql = _rewrite_placeholders(sql)

        allowed_write = _is_allowed_write(sql)
        if allowed_write and "returning" not in pg_sql.lower():
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
        cur = self._conn.cursor()
        try:
            cur.execute(pg_sql, params)
        except Exception:
            cur.close()
            raise
        lastrowid: int | None = None
        if allowed_write:
            row = cur.fetchone()  # RETURNING id → (id,)
            lastrowid = row[0] if row else None
        self._cursors.append(cur)
        return _AdapterCursor(cur, lastrowid=lastrowid)

    def close_cursors(self) -> None:

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

# ---------------------------------------------------------------------------


def get_pool():

    return get_registry().connection_store("core")


def acquire() -> psycopg2.extensions.connection:
    return get_pool().acquire()


def release(conn: psycopg2.extensions.connection) -> None:
    get_pool().release(conn)
