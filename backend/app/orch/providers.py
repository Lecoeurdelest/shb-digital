"""Provider registry cho SDK runtime — PORT pattern battle/core/runtime/providers.py (D-45).

Một provider = một gateway nói giọng Anthropic API: SDK chỉ cần env {ANTHROPIC_BASE_URL,
ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY} per-session (ClaudeAgentOptions.env — KHÔNG đụng
process env, nên các session khác provider chạy song song được).
Provider kind=subscription (claude-cli) = KHÔNG set env → SDK dùng auth Claude CLI bundle như cũ.

⚠️ Standalone (demo Đà Nẵng): kind=subscription chỉ chạy nếu MÁY có Claude CLI login (~/.claude).
Máy KHÔNG có CLI login → PHẢI chọn provider có key (zai) qua env SHB_PROVIDER. Đó là lý do
registry này tồn tại — không phụ thuộc CLI auth thừa hưởng.

Luật bí mật (port battle): key CHỈ sống trong module này + options.env. public_view() cho API/FE
trả has_key true/false — KHÔNG BAO GIỜ trả key.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_VAR = re.compile(r"\$\{(\w+)\}")

# repo_root/backend/app/orch/providers.py → repo_root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_env_file(path: Path) -> dict[str, str]:
    """Parser .env tối giản (KEY=VALUE, # comment) — không cần dependency dotenv."""
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
    """Registry đọc providers.yaml + ${VAR} từ .env. reload() mỗi lần spawn để bắt .env mới."""

    def __init__(self, repo_root: Path | None = None):
        root = repo_root or _REPO_ROOT
        self.file = Path(os.environ.get("PROVIDERS_FILE", root / "configs" / "providers.yaml"))
        self.env_file = Path(os.environ.get("ENV_FILE", root / ".env"))
        self._items: dict[str, dict[str, Any]] = {}
        self._missing_keys: dict[str, str] = {}  # provider → tên biến thiếu
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
        if not self._items:  # không có file → tối thiểu vẫn chạy được đường CLI
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

    def resolve_env(self, name: str | None) -> tuple[str, dict[str, str]]:
        """(tên provider resolved, env cho ClaudeAgentOptions).

        subscription/không base_url → env RỖNG (SDK dùng CLI auth). provider có tên nhưng thiếu
        key trong .env → raise để caller trả lỗi giọng-agent (không hang câm).
        """
        name = name or self.default_name()
        p = self._items.get(name)
        if not p:
            raise KeyError(f"provider '{name}' không có trong {self.file.name} (hiện có: {', '.join(self._items)})")
        if p.get("kind") == "subscription" or not p.get("base_url"):
            return name, {}
        if name in self._missing_keys:
            raise KeyError(
                f"provider '{name}' thiếu biến {self._missing_keys[name]} trong {self.env_file} "
                "— điền key rồi gọi lại (server reload .env mỗi lần spawn)"
            )
        key = p["api_key"]
        return name, {
            "ANTHROPIC_BASE_URL": p["base_url"],
            "ANTHROPIC_AUTH_TOKEN": key,
            "ANTHROPIC_API_KEY": key,
        }

    def public_view(self) -> list[dict[str, Any]]:
        """Cho API /models — KHÔNG kèm key (chỉ has_key true/false)."""
        out = []
        for name, p in self._items.items():
            out.append(
                {
                    "name": name,
                    "kind": p.get("kind", "api"),
                    "base_url": p.get("base_url"),
                    "models": p.get("models", []),
                    "default": bool(p.get("default")),
                    "has_key": (
                        p.get("kind") == "subscription" or (bool(p.get("api_key")) and name not in self._missing_keys)
                    ),
                    "note": p.get("note"),
                }
            )
        return out


# Singleton mức module — server-default provider từ env SHB_PROVIDER (bỏ trống = default yaml).
providers = Providers()


def server_provider_env() -> dict[str, str]:
    """Env provider mức SERVER (a): SHB_PROVIDER hoặc default yaml. reload .env mỗi lần (bắt key mới).

    (a) resolve ở mức server — KHÔNG đọc conv.provider (đó là (c) model/provider per-conversation).
    """
    providers.reload()
    _, env = providers.resolve_env(os.environ.get("SHB_PROVIDER") or None)
    return env


def conv_provider_env(conv_provider: str | None) -> dict[str, str]:
    """D-45b (c) per-conv: env từ provider CỦA CONV (resume-consistency — conv tạo trên X chạy X).

    conv_provider None → server-default (SHB_PROVIDER) — conv cũ + không chọn = hành vi (a). Có tên
    → resolve_env raise KeyError nếu thiếu key/không tồn → caller (turn) fail LOUD (không hang câm).
    reload .env mỗi lần (bắt key điền runtime).
    """
    providers.reload()
    name = conv_provider or os.environ.get("SHB_PROVIDER") or None
    _, env = providers.resolve_env(name)
    return env
