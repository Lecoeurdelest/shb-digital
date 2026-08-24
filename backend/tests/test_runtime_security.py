"""bank_dc chặn startup nếu còn secret demo, auth bypass hay provider có thể egress."""

from __future__ import annotations

import pytest

from app.runtime_security import parse_bank_provider_hosts, runtime_mode, validate_runtime_security

_PASSWORDS = {
    "SEED_USER_PASSWORD": "strong-user-password",
    "SEED_ADMIN_PASSWORD": "strong-admin-password",
    "SEED_C001_PASSWORD": "strong-c001-password",
    "SEED_B001_PASSWORD": "strong-b001-password",
    "SEED_C019_PASSWORD": "strong-c019-password",
}


class _Providers:
    def __init__(self, items: list[dict], selected: str = "bank-llm", resolve_error: bool = False):
        self.items = items
        self.selected = selected
        self.resolve_error = resolve_error

    def reload(self) -> None:
        return None

    def public_view(self) -> list[dict]:
        return self.items

    def effective_default(self) -> str:
        return self.selected

    def resolve_env(self, _name: str):
        if self.resolve_error:
            raise KeyError("missing")
        return self.selected, {"ANTHROPIC_API_KEY": "not-returned-to-client"}


@pytest.fixture
def secure_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "j" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql://bank_app:strong-db-password@postgres.bank.dc/bank")
    monkeypatch.setenv("DEV_SKIP_AUTH", "0")
    monkeypatch.setenv("COOKIE_SECURE", "1")
    monkeypatch.setenv("SHB_BANK_PROVIDER_HOSTS", "llm.bank.dc")
    for name, value in _PASSWORDS.items():
        monkeypatch.setenv(name, value)


def _set_providers(monkeypatch, providers: _Providers) -> None:
    import app.orch.providers as provider_module

    monkeypatch.setattr(provider_module, "providers", providers)


def test_demo_mode_remains_backward_compatible(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    validate_runtime_security("demo")


def test_runtime_mode_rejects_unknown_value():
    with pytest.raises(RuntimeError, match="SHB_RUNTIME_MODE"):
        runtime_mode("production-ish")


@pytest.mark.parametrize(
    "raw",
    ["", "*", "*.bank.dc", "https://llm.bank.dc", "llm.bank.dc:8443", "llm.bank.dc,"],
)
def test_bank_provider_hosts_are_exact_hostnames(raw: str):
    if raw == "":
        assert parse_bank_provider_hosts(raw) == frozenset()
    else:
        with pytest.raises(RuntimeError):
            parse_bank_provider_hosts(raw)


def test_bank_dc_accepts_only_secure_internal_configuration(monkeypatch, secure_env):
    _set_providers(
        monkeypatch,
        _Providers(
            [
                {
                    "name": "bank-llm",
                    "kind": "api",
                    "base_url": "https://llm.bank.dc/anthropic",
                    "models": ["bank-model"],
                }
            ]
        ),
    )

    validate_runtime_security("bank_dc")


def test_bank_dc_aggregates_insecure_defaults(monkeypatch, secure_env):
    monkeypatch.setenv("JWT_SECRET", "shb-digital-dev-secret-change-in-prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://shb:shb@db:5432/shb")
    monkeypatch.setenv("DEV_SKIP_AUTH", "1")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "admin")
    _set_providers(
        monkeypatch,
        _Providers(
            [
                {
                    "name": "bank-llm",
                    "kind": "api",
                    "base_url": "https://llm.bank.dc",
                    "models": ["bank-model"],
                }
            ]
        ),
    )

    with pytest.raises(RuntimeError) as caught:
        validate_runtime_security("bank_dc")

    message = str(caught.value)
    assert "JWT_SECRET" in message
    assert "DATABASE_URL" in message
    assert "DEV_SKIP_AUTH" in message
    assert "COOKIE_SECURE" in message
    assert "SEED_ADMIN_PASSWORD" in message


def test_bank_dc_rejects_subscription_and_non_allowlisted_provider(monkeypatch, secure_env):
    _set_providers(
        monkeypatch,
        _Providers(
            [
                {"name": "cli", "kind": "subscription", "base_url": None, "models": ["x"]},
                {
                    "name": "external",
                    "kind": "api",
                    "base_url": "https://api.external.example/anthropic",
                    "models": ["x"],
                },
            ],
            selected="external",
        ),
    )

    with pytest.raises(RuntimeError) as caught:
        validate_runtime_security("bank_dc")

    assert "subscription provider must be disabled: cli" in str(caught.value)
    assert "provider host is not bank-allowlisted: external" in str(caught.value)


def test_bank_dc_rejects_provider_missing_credentials(monkeypatch, secure_env):
    _set_providers(
        monkeypatch,
        _Providers(
            [
                {
                    "name": "bank-llm",
                    "kind": "api",
                    "base_url": "https://llm.bank.dc",
                    "models": ["bank-model"],
                }
            ],
            resolve_error=True,
        ),
    )

    with pytest.raises(RuntimeError, match="provider credentials/config are incomplete"):
        validate_runtime_security("bank_dc")


def test_bank_dc_old_conversation_cannot_resolve_disabled_provider(monkeypatch, secure_env):
    import app.orch.providers as provider_module

    provider = _Providers(
        [
            {
                "name": "bank-llm",
                "kind": "api",
                "base_url": "https://llm.bank.dc",
                "models": ["bank-model"],
            }
        ]
    )
    _set_providers(monkeypatch, provider)
    monkeypatch.setenv("SHB_RUNTIME_MODE", "bank_dc")

    with pytest.raises(RuntimeError, match="selected provider must be selectable"):
        provider_module.conv_provider_env("retired-external")


def test_bank_dc_rechecks_provider_host_at_conversation_resolve(monkeypatch, secure_env):
    import app.orch.providers as provider_module

    provider = _Providers(
        [
            {
                "name": "bank-llm",
                "kind": "api",
                "base_url": "https://external.example/anthropic",
                "models": ["bank-model"],
            }
        ]
    )
    _set_providers(monkeypatch, provider)
    monkeypatch.setenv("SHB_RUNTIME_MODE", "bank_dc")

    with pytest.raises(RuntimeError, match="provider host is not bank-allowlisted"):
        provider_module.conv_provider_env("bank-llm")


def test_seed_users_validates_before_opening_database(monkeypatch):
    import app.db.seed_users as seed_module

    opened = False

    def reject_runtime() -> None:
        raise RuntimeError("insecure bank_dc")

    def connect(_url: str):
        nonlocal opened
        opened = True

    monkeypatch.setattr(seed_module, "validate_runtime_security", reject_runtime)
    monkeypatch.setattr(seed_module.psycopg2, "connect", connect)

    with pytest.raises(RuntimeError, match="insecure bank_dc"):
        seed_module.seed_users("postgresql://ignored")

    assert opened is False


def test_seed_if_empty_validates_before_database_probe(monkeypatch):
    import app.db.seed_if_empty as seed_module

    probed = False

    def reject_runtime() -> None:
        raise RuntimeError("insecure bank_dc")

    def probe(_url: str) -> bool:
        nonlocal probed
        probed = True
        return False

    monkeypatch.setattr(seed_module, "validate_runtime_security", reject_runtime)
    monkeypatch.setattr(seed_module, "_has_business_data", probe)

    with pytest.raises(RuntimeError, match="insecure bank_dc"):
        seed_module.seed_if_empty("postgresql://ignored")

    assert probed is False
