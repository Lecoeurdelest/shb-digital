"""sub_model per-provider (yaml, optional) — provider không map tên claude (local Ollama) khai
sub_model để SUB spawn model tồn tại; provider khác trả None → giữ SUB_MODEL haiku (D-45b)."""

from __future__ import annotations

from app.orch.providers import conv_sub_model


def _models_of(name: str) -> list[str]:
    from app.orch.providers import providers

    providers.reload()
    return providers._items.get(name, {}).get("models", [])


def test_local_has_sub_model():
    # local Ollama KHÔNG map alias claude → PHẢI khai sub_model ∈ models (invariant, không lock 'qwen3:8b')
    sm = conv_sub_model("local")
    assert sm is not None and sm in _models_of("local")


def test_wrap_sub_model_declared_and_in_models():
    """PROD FAIL (tester T12-5): wrap = default prod, gateway GPT KHÔNG map alias haiku → sub 502.
    INVARIANT (architect): wrap PHẢI khai sub_model + ∈ models — giá trị cụ thể (gpt-5.4-mini) là
    lựa chọn config, đổi sang gpt-5.4 KHÔNG phải bug; lock 'không None + hợp lệ' mới là hợp đồng."""
    sm = conv_sub_model("wrap")
    assert sm is not None and sm in _models_of("wrap")


def test_anthropic_compat_sub_model_none_or_valid():
    """zai/claude-cli = Anthropic-compatible (map alias haiku native) → sub_model OPTIONAL.
    INVARIANT (architect: đừng assert giá-trị-tình-cờ): None (dùng haiku default) HOẶC ∈ models.
    Sống qua cả hiện tại (claude-cli=sonnet S17 bench tạm) LẪN sau khi GỠ sonnet (→ None)."""
    for name in ("zai", "claude-cli"):
        sm = conv_sub_model(name)
        assert sm is None or sm in _models_of(name)


def test_unknown_provider_none_not_crash():
    # tên lạ → không raise ở tầng sub_model (resolve_env mới là chỗ fail loud)
    assert conv_sub_model("khong-ton-tai") is None


def test_non_anthropic_gateway_providers_declare_sub_model():
    """GUARD (tester T12-5 PROD 502): provider có base_url gateway KHÔNG map alias claude (wrap/local
    — không phải api.z.ai/api.anthropic) PHẢI khai sub_model, else sub spawn 'haiku' → 502.
    Anthropic-compatible (zai z.ai, anthropic) map alias → sub_model optional. Chặn regression class."""
    from app.orch.providers import providers

    providers.reload()
    # gateway map alias haiku native (Anthropic-compatible) — sub_model optional
    _ANTHROPIC_COMPAT_HOSTS = ("api.z.ai", "api.anthropic.com")
    for name, p in providers._items.items():
        base = p.get("base_url") or ""
        if p.get("kind") == "subscription" or not base:
            continue  # claude-cli subscription (CLI auth) — không qua gateway HTTP
        anthropic_compat = any(h in base for h in _ANTHROPIC_COMPAT_HOSTS)
        if not anthropic_compat:
            assert p.get("sub_model"), (
                f"provider '{name}' (base_url={base}) KHÔNG Anthropic-compat → PHẢI khai sub_model "
                "(gateway không map alias haiku → sub 502). Xem wrap/local."
            )
