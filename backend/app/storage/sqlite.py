"""SQLite adapter for local tooling and adapter contract tests, not for the core bank schema."""

from __future__ import annotations

import sqlite3
from urllib.parse import unquote, urlsplit

from app.storage.contracts import StoreConfigurationError, StoreDefinition


def _sqlite_path(dsn: str) -> str:
    parsed = urlsplit(dsn)
    if parsed.scheme != "sqlite":
        raise StoreConfigurationError("SQLite adapter requires a sqlite:// DSN")
    if parsed.path in ("/:memory:", ":memory:"):
        return ":memory:"
    path = unquote(parsed.path)
    if not path:
        raise StoreConfigurationError("SQLite DSN has no database path")
    return path


class SQLiteDataStore:
    """A deliberately small adapter; PostgreSQL-specific migrations are not portable to it."""

    kind = "sqlite"

    def __init__(self, definition: StoreDefinition) -> None:
        if not definition.dsn:
            raise StoreConfigurationError(f"store {definition.name!r} has no configured DSN")
        self.definition = definition
        self._path = _sqlite_path(definition.dsn)

    def acquire(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, check_same_thread=False)

    def release(self, connection: sqlite3.Connection) -> None:
        try:
            connection.rollback()
        finally:
            connection.close()

    def healthcheck(self) -> None:
        connection = self.acquire()
        try:
            if connection.execute("SELECT 1").fetchone() != (1,):
                raise RuntimeError("database probe returned an unexpected value")
        finally:
            self.release(connection)

    def close(self) -> None:
        return None
