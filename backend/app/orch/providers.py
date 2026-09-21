from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("orch.providers")

_VAR = re.compile(r"\$\{(\w+)\}")

# repo_root/backend/app/orch/providers.py → repo_root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> dict[str, str]:

    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class Providers:
    def __init__(self, repo_root: Path | None = None):
        root = repo_root or _REPO_ROOT
        self.file = Path(os.environ.get("PROVIDERS_FILE", root / "configs" / "providers.yaml"))
        self.env_file = Path(os.environ.get("ENV_FILE", root / ".env"))
        self._items: dict[str, dict[str, Any]] = {}
        self._missing_keys: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        env = {**_load_env_file(self.env_file), **os.environ}
        self._items, self._missing_keys = {}, {}
        raw = (yaml.safe_load(self.file.read_text()) or {}) if self.file.exists() else {}
        for p in raw.get("providers") or []:
            name = p["name"]
            key_tpl = p.get("api_key") or ""
            missing = [v for v in _VAR.findall(key_tpl) if not env.get(v)]
            if missing:
                self._missing_keys[name] = ", ".join(missing)
            p = {**p, "api_key": _VAR.sub(lambda m: env.get(m.group(1), ""), key_tpl)}
            self._items[name] = p
        if not self._items:
            self._items = {
                "claude-cli": {
                    "name": "claude-cli",
                    "kind": "subscription",
                    "default": True,
                    "models": ["haiku", "sonnet", "opus"],
                }
            }

    def default_name(self) -> str:
        for name, p in self._items.items():
            if p.get("default"):
                return name
        return next(iter(self._items))

    def effective_default(self) -> str:

        disabled = self._disabled_names()
        alive = [n for n in self._items if n not in disabled]
        env_pref = os.environ.get("SHB_PROVIDER") or None
        if env_pref and env_pref in alive:
            return env_pref
        yaml_default = self.default_name()
        if yaml_default in alive:
            return yaml_default
        return alive[0] if alive else yaml_default

    def resolve_env(self, name: str | None) -> tuple[str, dict[str, str]]:

        name = name or self.default_name()
        p = self._items.get(name)
        if not p:
            raise KeyError(f"provider '{name}' is not in {self.file.name} (available: {', '.join(self._items)})")
        if p.get("kind") == "subscription" or not p.get("base_url"):
            return name, {}
        if name in self._missing_keys:
            raise KeyError(
                f"provider '{name}' is missing {self._missing_keys[name]} in {self.env_file}; "
                "set the key and try again (the server reloads .env for every spawn)"
            )
        key = p["api_key"]
        return name, {
            "ANTHROPIC_BASE_URL": p["base_url"],
            "ANTHROPIC_AUTH_TOKEN": key,
            "ANTHROPIC_API_KEY": key,
        }

    def _disabled_names(self) -> set[str]:

        raw = os.environ.get("SHB_PROVIDERS_DISABLED", "")
        want = {n.strip() for n in raw.split(",") if n.strip()}
        disabled, unknown = set(), set()
        for n in want:
            (disabled if n in self._items else unknown).add(n)
        if unknown:
            log.warning("SHB_PROVIDERS_DISABLED contains unknown names (ignored): %s", sorted(unknown))

        if disabled and disabled >= set(self._items):
            keep = self.default_name()
            log.warning(
                "SHB_PROVIDERS_DISABLED disables every provider; keeping default '%s' so the picker is not empty", keep
            )
            disabled.discard(keep)
        return disabled

    def public_view(self) -> list[dict[str, Any]]:

        disabled = self._disabled_names()
        eff = self.effective_default()
        out = []
        for name, p in self._items.items():
            if name in disabled:
                continue
            out.append(
                {
                    "name": name,
                    "kind": p.get("kind", "api"),
                    "base_url": p.get("base_url"),
                    "models": p.get("models", []),
                    "default": name == eff,
                    "has_key": (
                        p.get("kind") == "subscription" or (bool(p.get("api_key")) and name not in self._missing_keys)
                    ),
                    "note": p.get("note"),
                }
            )
        return out


providers = Providers()


def server_provider_env() -> dict[str, str]:

    providers.reload()
    _, env = providers.resolve_env(providers.effective_default())
    return env


def conv_sub_model(conv_provider: str | None) -> str | None:

    providers.reload()
    name = conv_provider or providers.effective_default()
    return (providers._items.get(name) or {}).get("sub_model")


def conv_provider_env(conv_provider: str | None) -> dict[str, str]:

    providers.reload()
    name = conv_provider or providers.effective_default()

    from app.runtime_security import enforce_bank_provider_selection

    enforce_bank_provider_selection(name, providers)
    _, env = providers.resolve_env(name)
    return env
