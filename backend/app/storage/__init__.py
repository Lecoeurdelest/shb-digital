"""Public datastore extension surface."""

from app.storage.contracts import KeyValueStore, StoreConfigurationError, StoreDefinition, VectorMatch, VectorStore
from app.storage.registry import (
    DataStoreRegistry,
    connect_capability,
    connect_core,
    connect_store,
    get_registry,
    key_value_capability,
    reset_registry,
    vector_capability,
)

__all__ = [
    "DataStoreRegistry",
    "KeyValueStore",
    "StoreConfigurationError",
    "StoreDefinition",
    "VectorMatch",
    "VectorStore",
    "connect_capability",
    "connect_core",
    "connect_store",
    "get_registry",
    "key_value_capability",
    "reset_registry",
    "vector_capability",
]
