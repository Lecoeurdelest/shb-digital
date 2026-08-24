"""Datastore registry: aliases, capabilities, adapters, and secret-safe failures."""

from __future__ import annotations

import json

import psycopg2
import pytest

import app.storage.postgres as postgres_module
import app.storage.registry as registry_module
from app.storage import DataStoreRegistry, StoreConfigurationError, StoreDefinition
from app.storage.postgres import PostgresDataStore
from app.storage.registry import get_registry, load_definitions

from .conftest import requires_db


class _FakeStore:
    kind = "fake"

    def __init__(self, definition: StoreDefinition) -> None:
        self.definition = definition
        self.probes = 0
        self.closed = False

    def healthcheck(self) -> None:
        self.probes += 1

    def close(self) -> None:
        self.closed = True


def _definition(name: str, driver: str, *capabilities: str, target: str | None = None) -> StoreDefinition:
    return StoreDefinition(
        name=name,
        driver=driver,
        dsn="fake://configured" if driver != "alias" else None,
        target=target,
        capabilities=frozenset(capabilities),
    )


def test_custom_driver_alias_and_capability_share_one_instance():
    registry = DataStoreRegistry(
        [
            _definition("core", "fake", "transactions"),
            _definition("prompts", "alias", "prompt_catalog", target="core"),
        ]
    )
    registry.register_driver("fake", _FakeStore)

    core = registry.get("core")
    assert registry.get("prompts") is core
    assert registry.for_capability("prompt_catalog") is core

    registry.healthcheck_required()
    assert core.probes == 1
    registry.close()
    assert core.closed is True


def test_alias_cycle_and_missing_adapter_fail_without_dsn():
    with pytest.raises(StoreConfigurationError, match="alias cycle"):
        DataStoreRegistry(
            [
                _definition("one", "alias", target="two"),
                _definition("two", "alias", target="one"),
            ]
        )

    registry = DataStoreRegistry([_definition("special", "secret-driver", "vector")])
    with pytest.raises(StoreConfigurationError) as error:
        registry.get("special")
    assert "fake://configured" not in str(error.value)


def test_optional_entry_point_is_loaded_only_when_requested(monkeypatch):
    class BrokenPoint:
        name = "broken-store"
        loads = 0

        def load(self):
            self.loads += 1
            raise RuntimeError("secret plugin detail")

    point = BrokenPoint()
    monkeypatch.setattr(registry_module, "entry_points", lambda **_kwargs: [point])
    registry = DataStoreRegistry(
        [
            _definition("core", "fake", "transactions"),
            StoreDefinition(
                name="optional",
                driver="broken-store",
                dsn="broken://configured",
                required=False,
                capabilities=frozenset({"vector"}),
            ),
        ]
    )
    registry.register_driver("fake", _FakeStore)

    assert registry.get("core").kind == "fake"
    assert point.loads == 0
    with pytest.raises(StoreConfigurationError, match="cannot load datastore driver") as error:
        registry.get("optional")
    assert point.loads == 1
    assert "secret plugin detail" not in str(error.value)


def test_load_definitions_uses_env_indirection(tmp_path, monkeypatch):
    config = tmp_path / "stores.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "stores": [
                    {
                        "name": "local",
                        "driver": "sqlite",
                        "dsn_env": "TEST_STORE_DSN",
                        "capabilities": ["prompt_catalog"],
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("TEST_STORE_DSN", "sqlite:///:memory:")
    definitions = load_definitions(config)
    assert definitions[0].name == "local"
    assert definitions[0].dsn == "sqlite:///:memory:"

    registry = DataStoreRegistry(definitions)
    registry.get("local").healthcheck()
    registry.close()


def test_load_definitions_resolves_secret_options_from_env(tmp_path, monkeypatch):
    config = tmp_path / "stores.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "stores": [
                    {
                        "name": "vectors",
                        "driver": "external-vector",
                        "dsn_env": "VECTOR_URL",
                        "options_env": {"api_key": "VECTOR_API_KEY"},
                        "capabilities": ["vector"],
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("VECTOR_URL", "https://vectors.internal")
    monkeypatch.setenv("VECTOR_API_KEY", "do-not-print-this")

    definition = load_definitions(config)[0]

    assert definition.options["api_key"] == "do-not-print-this"
    assert "do-not-print-this" not in repr(definition)


def test_postgres_pool_bounds_connection_and_acquire_wait(monkeypatch):
    class FakeConnection:
        closed = 0
        status = psycopg2.extensions.STATUS_READY

    class FakePool:
        created: tuple[tuple, dict] | None = None

        def __init__(self, *args, **kwargs):
            FakePool.created = (args, kwargs)
            self.connection = FakeConnection()
            self.puts = 0

        def getconn(self):
            return self.connection

        def putconn(self, _connection, close=False):
            self.puts += 1

        def closeall(self):
            return None

    monkeypatch.setattr(postgres_module.psycopg2.pool, "ThreadedConnectionPool", FakePool)
    monkeypatch.setenv("SHB_DB_POOL_MIN", "1")
    monkeypatch.setenv("SHB_DB_POOL_MAX", "1")
    monkeypatch.setenv("SHB_DB_CONNECT_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("SHB_DB_POOL_ACQUIRE_TIMEOUT_SECONDS", "0.001")
    store = PostgresDataStore(_definition("core", "postgresql", "transactions"))

    first = store.acquire()
    with pytest.raises(psycopg2.pool.PoolError, match="acquire timed out"):
        store.acquire()
    store.release(first)
    second = store.acquire()
    store.release(second)

    assert FakePool.created is not None
    args, kwargs = FakePool.created
    assert args == (1, 1)
    assert kwargs["connect_timeout"] == 3
    assert kwargs["application_name"] == "bank-digital"


def test_postgres_pool_rejects_invalid_timeouts(monkeypatch):
    monkeypatch.setenv("SHB_DB_CONNECT_TIMEOUT_SECONDS", "0")
    store = PostgresDataStore(_definition("core", "postgresql", "transactions"))
    with pytest.raises(StoreConfigurationError, match="SHB_DB_CONNECT_TIMEOUT_SECONDS must be positive"):
        store.acquire()


@requires_db
def test_default_registry_probes_core_and_resolves_declared_capabilities():
    registry = get_registry()
    registry.healthcheck_required()
    assert registry.for_capability("transactions") is registry.get("core")
    assert registry.for_capability("prompt_catalog") is registry.get("core")
