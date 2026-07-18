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

    def effective_default(self) -> str:
        """Default THỰC DÙNG (1 NGUỒN SỰ THẬT — cả /api/models field 'default' LẪN đường tạo conv
        không truyền provider). Tránh preselect provider ĐÃ BỊ ẨN (SHB_PROVIDERS_DISABLED):
        (1) SHB_PROVIDER env nếu set VÀ còn sống · (2) else yaml default: true nếu còn sống ·
        (3) else provider ĐẦU TIÊN còn sống trong public_view. Không còn sống nào → default_name (fallback
        cực hiếm — _disabled_names đã giữ ≥1 sống)."""
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

    def _disabled_names(self) -> set[str]:
        """Provider bị tắt qua env SHB_PROVIDERS_DISABLED (comma list) — FIX C: VM ẩn claude-cli
        (container không CLI auth → nút chết). Tên lạ → ignore + log. Default không set → rỗng."""
        raw = os.environ.get("SHB_PROVIDERS_DISABLED", "")
        want = {n.strip() for n in raw.split(",") if n.strip()}
        disabled, unknown = set(), set()
        for n in want:
            (disabled if n in self._items else unknown).add(n)
        if unknown:
            log.warning("SHB_PROVIDERS_DISABLED có tên lạ (ignore): %s", sorted(unknown))
        # KHÔNG để list rỗng chết picker: nếu disable HẾT → giữ lại default (log warning).
        if disabled and disabled >= set(self._items):
            keep = self.default_name()
            log.warning("SHB_PROVIDERS_DISABLED tắt HẾT provider — giữ default '%s' để picker không rỗng", keep)
            disabled.discard(keep)
        return disabled

    def public_view(self) -> list[dict[str, Any]]:
        """Cho API /models — KHÔNG kèm key (chỉ has_key true/false). FIX C: loại provider disabled.
        'default' = EFFECTIVE default (FE preselect) — CHỈ 1 provider còn sống, KHÔNG trỏ provider ẩn."""
        disabled = self._disabled_names()
        eff = self.effective_default()
        out = []
        for name, p in self._items.items():
            if name in disabled:
                continue  # ẩn khỏi picker FE + validation create_conversation (đọc public_view)
            out.append(
                {
                    "name": name,
                    "kind": p.get("kind", "api"),
                    "base_url": p.get("base_url"),
                    "models": p.get("models", []),
                    "default": name == eff,  # effective (không phải yaml flag — tránh trỏ provider ẩn)
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
    """Env provider mức SERVER (a): EFFECTIVE default (1 nguồn sự thật với /api/models — KHÔNG rơi
    provider ẩn dù SHB_PROVIDER trỏ vào nó). reload .env mỗi lần (bắt key mới).

    (a) resolve ở mức server — KHÔNG đọc conv.provider (đó là (c) model/provider per-conversation).
    """
    providers.reload()
    _, env = providers.resolve_env(providers.effective_default())
    return env


def conv_sub_model(conv_provider: str | None) -> str | None:
    """Model cho SUB theo provider của conv — yaml field `sub_model` (OPTIONAL, D-45b mở rộng).

    Mặc định sub luôn 'haiku' (rẻ, cố ý — D-45b); provider KHÔNG map tên claude (vd `local`
    Ollama on-prem: model phải tồn tại đúng tên) khai `sub_model:` trong providers.yaml →
    sub spawn model đó. Trả None → caller giữ SUB_MODEL."""
    providers.reload()
    name = conv_provider or providers.effective_default()
    return (providers._items.get(name) or {}).get("sub_model")


def conv_provider_env(conv_provider: str | None) -> dict[str, str]:
    """D-45b (c) per-conv: env từ provider CỦA CONV (resume-consistency — conv tạo trên X chạy X).

    conv_provider None → EFFECTIVE default (CÙNG nguồn với /api/models 'default' — ca không truyền
    provider KHÔNG rơi provider ẩn). Có tên → resolve_env raise KeyError nếu thiếu key/không tồn →
    caller (turn) fail LOUD (không hang câm). reload .env mỗi lần (bắt key điền runtime).
    """
    providers.reload()
    name = conv_provider or providers.effective_default()
    _, env = providers.resolve_env(name)
    return env
