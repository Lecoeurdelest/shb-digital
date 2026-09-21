from __future__ import annotations

import re
import sqlite3
from typing import Any

import psycopg2
import psycopg2.extras

_BLOCKED_CODES = {"disburse_blocked", "invalid_param"}


class OpsDisburseBlocked(Exception):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message") or "ops_disburse was blocked"))


_Q = re.compile(r"\?")


class _OpsCursor:
    def __init__(self, pg_cursor: Any) -> None:
        self._cur = pg_cursor

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list:
        return self._cur.fetchall()


class OpsConnProxy:
    def __init__(self, pg_conn: Any) -> None:
        self._conn = pg_conn

    def execute(self, sql: str, params: tuple = ()) -> _OpsCursor:
        stripped = sql.strip().upper()
        if stripped.startswith("BEGIN"):
            return _OpsCursor(_NullCursor())
        pg_sql = _Q.sub("%s", sql)

        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(pg_sql, params)
        except psycopg2.IntegrityError as e:
            cur.close()
            raise sqlite3.IntegrityError(str(e)) from e
        except psycopg2.Error as e:
            cur.close()
            raise sqlite3.OperationalError(str(e)) from e
        return _OpsCursor(cur)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class _NullCursor:
    def fetchone(self) -> Any:
        return None

    def fetchall(self) -> list:
        return []


def run_ops_disburse(pg_conn: Any, **args: Any) -> dict[str, Any]:

    from roles.operations.functions import ops_disburse

    proxy = OpsConnProxy(pg_conn)
    out = ops_disburse(proxy, **args)

    if out.get("code") in _BLOCKED_CODES:
        raise OpsDisburseBlocked(out)

    if out.get("found") is False:
        raise OpsDisburseBlocked(
            {
                "code": "disburse_blocked",
                "message": "No application was found for disbursement.",
                "hint": out.get("hint") or "Check application_id.",
                "retryable": False,
                "blockers": ["application_not_found"],
            }
        )
    return out
