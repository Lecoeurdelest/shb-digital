"""Redis adapter: only cache/coordination, never a banking source of truth."""

from __future__ import annotations

from typing import Any

from app.storage.contracts import StoreConfigurationError, StoreDefinition


class RedisDataStore:
    kind = "redis"

    def __init__(self, definition: StoreDefinition) -> None:
        if not definition.dsn:
            raise StoreConfigurationError(f"store {definition.name!r} has no configured DSN")
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - package is a runtime dependency
            raise StoreConfigurationError("Redis adapter dependency is not installed") from exc
        self.definition = definition
        self._prefix = str(definition.options.get("key_prefix", ""))
        timeout = float(definition.options.get("timeout_seconds", 2))
        self._client: Any = redis.Redis.from_url(
            definition.dsn,
            decode_responses=False,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
            health_check_interval=15,
        )

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> bytes | None:
        value = self._client.get(self._key(key))
        return bytes(value) if value is not None else None

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None = None) -> None:
        self._client.set(self._key(key), value, ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(self._key(key))

    def healthcheck(self) -> None:
        if self._client.ping() is not True:
            raise RuntimeError("Redis probe returned an unexpected value")

    def close(self) -> None:
        self._client.close()
