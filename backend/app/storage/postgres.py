"""Thread-safe PostgreSQL datastore adapter used by the transactional core."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extensions
import psycopg2.pool

from app.storage.contracts import StoreConfigurationError, StoreDefinition


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise StoreConfigurationError(f"{name} must be an integer") from exc
    if value < 1:
        raise StoreConfigurationError(f"{name} must be positive")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise StoreConfigurationError(f"{name} must be a number") from exc
    if value <= 0:
        raise StoreConfigurationError(f"{name} must be positive")
    return value


class PostgresDataStore:
    kind = "postgresql"

    def __init__(self, definition: StoreDefinition) -> None:
        if not definition.dsn:
            raise StoreConfigurationError(f"store {definition.name!r} has no configured DSN")
        self.definition = definition
        self._dsn = definition.dsn
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None
        self._slots: threading.BoundedSemaphore | None = None
        self._lock = threading.Lock()

    def _get_pool(self) -> psycopg2.pool.ThreadedConnectionPool:
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    minimum = _positive_int("SHB_DB_POOL_MIN", 1)
                    maximum = _positive_int("SHB_DB_POOL_MAX", 10)
                    if minimum > maximum:
                        raise StoreConfigurationError("SHB_DB_POOL_MIN cannot exceed SHB_DB_POOL_MAX")
                    connect_timeout = _positive_int("SHB_DB_CONNECT_TIMEOUT_SECONDS", 5)
                    pool = psycopg2.pool.ThreadedConnectionPool(
                        minimum,
                        maximum,
                        dsn=self._dsn,
                        connect_timeout=connect_timeout,
                        application_name="bank-digital",
                    )
                    self._slots = threading.BoundedSemaphore(maximum)
                    # Gán pool sau cùng để thread khác không bao giờ thấy pool thiếu cổng giới hạn.
                    self._pool = pool
        return self._pool

    def acquire(self) -> psycopg2.extensions.connection:
        pool = self._get_pool()
        slots = self._slots
        if slots is None:  # pragma: no cover - initialized atomically with the pool
            raise psycopg2.pool.PoolError("database pool is not initialized")
        wait_seconds = _positive_float("SHB_DB_POOL_ACQUIRE_TIMEOUT_SECONDS", 5.0)
        if not slots.acquire(timeout=wait_seconds):
            raise psycopg2.pool.PoolError(f"database pool acquire timed out after {wait_seconds:g}s")
        try:
            return pool.getconn()
        except Exception:
            slots.release()
            raise

    def release(self, connection: psycopg2.extensions.connection) -> None:
        pool = self._get_pool()
        slots = self._slots
        try:
            if connection.closed:
                pool.putconn(connection, close=True)
                return
            try:
                if connection.status != psycopg2.extensions.STATUS_READY:
                    connection.rollback()
            except psycopg2.Error:
                pool.putconn(connection, close=True)
                return
            pool.putconn(connection)
        finally:
            if slots is not None:
                slots.release()

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        connection = self.acquire()
        try:
            yield connection
        finally:
            self.release(connection)

    def healthcheck(self) -> None:
        connection = self.acquire()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise RuntimeError("database probe returned an unexpected value")
            connection.rollback()
        finally:
            self.release(connection)

    def close(self) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.closeall()
                self._pool = None
                self._slots = None


class ConnectionLease:
    """Connection-shaped lease whose close returns the connection to its adapter pool."""

    def __init__(self, store: Any) -> None:
        self._store = store
        self._connection = store.acquire()
        self._released = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def close(self) -> None:
        if not self._released:
            self._released = True
            self._store.release(self._connection)

    def __enter__(self) -> ConnectionLease:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self.close()
        return False
