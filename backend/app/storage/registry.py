"""Capability-oriented datastore registry with adapter entry points and aliases."""

from __future__ import annotations

import json
import os
import threading
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from app.db.config import DATABASE_URL
from app.storage.contracts import (
    ConnectionStore,
    DataStore,
    KeyValueStore,
    StoreConfigurationError,
    StoreDefinition,
    StoreFactory,
    VectorStore,
)
from app.storage.postgres import ConnectionLease, PostgresDataStore
from app.storage.qdrant import QdrantDataStore
from app.storage.redis import RedisDataStore
from app.storage.sqlite import SQLiteDataStore

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "datastores.json"
ENTRY_POINT_GROUP = "bank_digital.datastores"


def _definition(raw: dict[str, Any]) -> StoreDefinition:
    name = str(raw.get("name", "")).strip()
    driver = str(raw.get("driver", "")).strip().lower()
    if not name or not driver:
        raise StoreConfigurationError("each datastore needs a name and driver")
    capabilities = frozenset(str(item).strip() for item in raw.get("capabilities", []) if str(item).strip())
    target = str(raw.get("target", "")).strip() or None
    dsn: str | None = None
    if driver != "alias":
        env_name = str(raw.get("dsn_env", "")).strip()
        if not env_name:
            raise StoreConfigurationError(f"store {name!r} needs dsn_env")
        dsn = os.environ.get(env_name)
        if dsn is None and env_name == "DATABASE_URL":
            dsn = DATABASE_URL
        if not dsn and bool(raw.get("required", True)):
            raise StoreConfigurationError(f"required store {name!r} is not configured")
    elif not target:
        raise StoreConfigurationError(f"alias store {name!r} needs a target")
    options = raw.get("options") or {}
    if not isinstance(options, dict):
        raise StoreConfigurationError(f"store {name!r} options must be an object")
    options = dict(options)
    options_env = raw.get("options_env") or {}
    if not isinstance(options_env, dict):
        raise StoreConfigurationError(f"store {name!r} options_env must be an object")
    for option_name, env_name in options_env.items():
        if not isinstance(option_name, str) or not isinstance(env_name, str) or not env_name.strip():
            raise StoreConfigurationError(f"store {name!r} options_env entries must be non-empty strings")
        value = os.environ.get(env_name)
        if value is None:
            if bool(raw.get("required", True)):
                raise StoreConfigurationError(f"required option {option_name!r} for store {name!r} is not configured")
            continue
        options[option_name] = value
    return StoreDefinition(
        name=name,
        driver=driver,
        capabilities=capabilities,
        required=bool(raw.get("required", True)),
        dsn=dsn,
        target=target,
        options=options,
    )


def load_definitions(path: Path | None = None) -> list[StoreDefinition]:
    configured = os.environ.get("SHB_DATASTORES_FILE")
    config_path = path or (Path(configured).expanduser() if configured else DEFAULT_CONFIG_PATH)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreConfigurationError(f"cannot read datastore config {config_path.name!r}") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("stores"), list):
        raise StoreConfigurationError("datastore config must use schema version 1")
    definitions = [_definition(item) for item in payload["stores"]]
    names = [item.name for item in definitions]
    if len(names) != len(set(names)):
        raise StoreConfigurationError("datastore names must be unique")
    return definitions


class DataStoreRegistry:
    def __init__(self, definitions: list[StoreDefinition]) -> None:
        self._definitions = {item.name: item for item in definitions}
        self._order = [item.name for item in definitions]
        self._factories: dict[str, StoreFactory] = {
            "postgres": PostgresDataStore,
            "postgresql": PostgresDataStore,
            "sqlite": SQLiteDataStore,
            "redis": RedisDataStore,
            "qdrant": QdrantDataStore,
        }
        self._entry_points: dict[str, Any] = {}
        self._instances: dict[str, DataStore] = {}
        self._lock = threading.RLock()
        self._discover_entry_points()
        self._validate_aliases()

    def _discover_entry_points(self) -> None:
        for point in entry_points(group=ENTRY_POINT_GROUP):
            if point.name not in self._factories and point.name not in self._entry_points:
                self._entry_points[point.name] = point

    def _factory(self, driver: str) -> StoreFactory:
        factory = self._factories.get(driver)
        if factory is not None:
            return factory
        point = self._entry_points.get(driver)
        if point is None:
            raise StoreConfigurationError(f"no adapter registered for datastore driver {driver!r}")
        try:
            factory = point.load()
        except Exception as exc:  # noqa: BLE001 - plugin import failure becomes a safe config error
            raise StoreConfigurationError(f"cannot load datastore driver {driver!r}") from exc
        self._factories[driver] = factory
        return factory

    def register_driver(self, name: str, factory: StoreFactory, *, replace: bool = False) -> None:
        driver = name.strip().lower()
        if not driver:
            raise StoreConfigurationError("driver name cannot be empty")
        if (driver in self._factories or driver in self._entry_points) and not replace:
            raise StoreConfigurationError(f"datastore driver {driver!r} is already registered")
        if replace:
            self._entry_points.pop(driver, None)
        self._factories[driver] = factory

    def _validate_aliases(self) -> None:
        for name in self._order:
            seen: set[str] = set()
            current = name
            while self._definitions[current].driver == "alias":
                if current in seen:
                    raise StoreConfigurationError(f"datastore alias cycle contains {current!r}")
                seen.add(current)
                target = self._definitions[current].target
                if target not in self._definitions:
                    raise StoreConfigurationError(f"datastore alias {current!r} has an unknown target")
                current = target

    def definition(self, name: str) -> StoreDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise StoreConfigurationError(f"unknown datastore {name!r}") from exc

    def get(self, name: str) -> DataStore:
        definition = self.definition(name)
        if definition.driver == "alias":
            return self.get(definition.target or "")
        with self._lock:
            existing = self._instances.get(name)
            if existing is not None:
                return existing
            factory = self._factory(definition.driver)
            instance = factory(definition)
            self._instances[name] = instance
            return instance

    def for_capability(self, capability: str) -> DataStore:
        for name in self._order:
            if capability in self._definitions[name].capabilities:
                return self.get(name)
        raise StoreConfigurationError(f"no datastore provides capability {capability!r}")

    def connection_store(self, name: str = "core") -> ConnectionStore:
        store = self.get(name)
        if not isinstance(store, ConnectionStore):
            raise StoreConfigurationError(f"datastore {name!r} does not provide DB connections")
        return store

    def key_value_store(self, capability: str = "cache") -> KeyValueStore:
        store = self.for_capability(capability)
        if not isinstance(store, KeyValueStore):
            raise StoreConfigurationError(f"datastore capability {capability!r} does not provide key-value storage")
        return store

    def vector_store(self, capability: str = "vector") -> VectorStore:
        store = self.for_capability(capability)
        if not isinstance(store, VectorStore):
            raise StoreConfigurationError(f"datastore capability {capability!r} does not provide vector storage")
        return store

    def healthcheck_required(self) -> None:
        checked: set[int] = set()
        for name in self._order:
            if not self._definitions[name].required:
                continue
            store = self.get(name)
            marker = id(store)
            if marker not in checked:
                store.healthcheck()
                checked.add(marker)

    def close(self) -> None:
        with self._lock:
            for store in self._instances.values():
                store.close()
            self._instances.clear()


_registry: DataStoreRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> DataStoreRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = DataStoreRegistry(load_definitions())
    return _registry


def reset_registry() -> None:
    global _registry
    with _registry_lock:
        if _registry is not None:
            _registry.close()
        _registry = None


def connect_core() -> ConnectionLease:
    return connect_store("core")


def connect_store(name: str) -> ConnectionLease:
    return ConnectionLease(get_registry().connection_store(name))


def connect_capability(capability: str) -> ConnectionLease:
    registry = get_registry()
    store = registry.for_capability(capability)
    if not isinstance(store, ConnectionStore):
        raise StoreConfigurationError(f"datastore capability {capability!r} does not provide DB connections")
    return ConnectionLease(store)


def key_value_capability(capability: str = "cache") -> KeyValueStore:
    return get_registry().key_value_store(capability)


def vector_capability(capability: str = "vector") -> VectorStore:
    return get_registry().vector_store(capability)
