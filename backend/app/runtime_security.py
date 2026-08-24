"""Fail-fast policy cho runtime bank DC; demo mặc định giữ tương thích ngược."""

from __future__ import annotations

import os
import re
from ipaddress import ip_address
from urllib.parse import urlsplit

from app.config import DEFAULT_JWT_SECRET
from app.db.config import DEFAULT_DATABASE_URL

_RUNTIME_MODES = {"demo", "bank_dc"}
_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_SEED_PASSWORDS = {
    "SEED_USER_PASSWORD": "user",
    "SEED_ADMIN_PASSWORD": "admin",
    "SEED_C001_PASSWORD": "c001",
    "SEED_B001_PASSWORD": "b001",
    "SEED_C019_PASSWORD": "c019",
}


def runtime_mode(value: str | None = None) -> str:
    mode = (value if value is not None else os.environ.get("SHB_RUNTIME_MODE", "demo")).strip().lower()
    if mode not in _RUNTIME_MODES:
        raise RuntimeError("SHB_RUNTIME_MODE must be 'demo' or 'bank_dc'")
    return mode


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _valid_host(host: str) -> bool:
    try:
        ip_address(host)
        return True
    except ValueError:
        labels = host.rstrip(".").split(".")
        return bool(labels) and all(_HOST_LABEL.fullmatch(label) for label in labels)


def parse_bank_provider_hosts(raw: str | None) -> frozenset[str]:
    """Hostname exact, không scheme/port/path/wildcard; rỗng bị bank_dc từ chối."""
    if raw is None or not raw.strip():
        return frozenset()
    hosts: set[str] = set()
    for item in raw.split(","):
        host = item.strip().lower().rstrip(".")
        if not host or "*" in host or not _valid_host(host):
            raise RuntimeError("SHB_BANK_PROVIDER_HOSTS contains an invalid hostname")
        hosts.add(host)
    return frozenset(hosts)


def _base_security_violations() -> list[str]:
    failures: list[str] = []
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == DEFAULT_JWT_SECRET or len(jwt_secret) < 32:
        failures.append("JWT_SECRET must be non-default and at least 32 characters")
    database_url = os.environ.get("DATABASE_URL", "")
    try:
        database = urlsplit(database_url)
        if database.port is not None:
            int(database.port)
    except ValueError:
        database = None
    if (
        not database_url
        or database_url == DEFAULT_DATABASE_URL
        or database is None
        or database.scheme not in {"postgres", "postgresql"}
        or not database.hostname
        or not database.username
        or not database.password
        or database.password == "shb"
    ):
        failures.append("DATABASE_URL must be explicit and must not use demo credentials")
    if _env_bool("DEV_SKIP_AUTH"):
        failures.append("DEV_SKIP_AUTH must be disabled")
    if not _env_bool("COOKIE_SECURE"):
        failures.append("COOKIE_SECURE must be enabled")
    for env_name, demo_value in _SEED_PASSWORDS.items():
        value = os.environ.get(env_name, "")
        if not value or value == demo_value or len(value) < 12:
            failures.append(f"{env_name} must be non-demo and at least 12 characters")
    return failures


def _provider_registry_violations(providers, selected: str | None = None) -> list[str]:
    failures: list[str] = []
    try:
        allowlist = parse_bank_provider_hosts(os.environ.get("SHB_BANK_PROVIDER_HOSTS"))
    except RuntimeError as exc:
        return [str(exc)]
    if not allowlist:
        return ["SHB_BANK_PROVIDER_HOSTS must contain at least one internal provider hostname"]
    enabled = providers.public_view()
    if not enabled:
        return ["at least one provider must be selectable"]
    selected = selected or providers.effective_default()
    enabled_names = {item["name"] for item in enabled}
    if selected not in enabled_names:
        failures.append("selected provider must be selectable")
    for item in enabled:
        name = item["name"]
        if item.get("kind") == "subscription":
            failures.append(f"subscription provider must be disabled: {name}")
            continue
        try:
            parsed = urlsplit(item.get("base_url") or "")
            if parsed.port is not None:
                int(parsed.port)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError:
            failures.append(f"provider URL is malformed: {name}")
            continue
        if parsed.scheme not in {"http", "https"} or not host or host not in allowlist:
            failures.append(f"provider host is not bank-allowlisted: {name}")
            continue
        try:
            providers.resolve_env(name)
        except (KeyError, ValueError):
            failures.append(f"provider credentials/config are incomplete: {name}")
    return failures


def _provider_security_violations() -> list[str]:
    from app.orch.providers import providers

    providers.reload()
    return _provider_registry_violations(providers)


def enforce_bank_provider_selection(name: str, providers) -> None:
    """Re-check registry đã reload tại điểm dùng để config đổi nóng không mở egress ngoài DC."""
    if runtime_mode() == "demo":
        return
    failures = _provider_registry_violations(providers, selected=name)
    if failures:
        raise RuntimeError("bank_dc provider validation failed: " + "; ".join(failures))


def validate_runtime_security(mode: str | None = None) -> None:
    """Demo no-op; bank_dc gom mọi vi phạm rồi chặn startup trước khi app nhận request."""
    if runtime_mode(mode) == "demo":
        return
    failures = [*_base_security_violations(), *_provider_security_violations()]
    if failures:
        raise RuntimeError("bank_dc runtime validation failed: " + "; ".join(failures))
