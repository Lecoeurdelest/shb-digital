from __future__ import annotations

from app.orch.providers import conv_sub_model


def _models_of(name: str) -> list[str]:
    from app.orch.providers import providers

    providers.reload()
    return providers._items.get(name, {}).get("models", [])


def test_local_has_sub_model():

    sm = conv_sub_model("local")
    assert sm is not None and sm in _models_of("local")


def test_wrap_sub_model_declared_and_in_models():

    sm = conv_sub_model("wrap")
    assert sm is not None and sm in _models_of("wrap")


def test_anthropic_compat_sub_model_none_or_valid():

    for name in ("zai", "claude-cli"):
        sm = conv_sub_model(name)
        assert sm is None or sm in _models_of(name)


def test_unknown_provider_none_not_crash():

    assert conv_sub_model("does-not-exist") is None


def test_non_anthropic_gateway_providers_declare_sub_model():

    from app.orch.providers import providers

    providers.reload()
    # gateway map alias haiku native (Anthropic-compatible) — sub_model optional
    _ANTHROPIC_COMPAT_HOSTS = ("api.z.ai", "api.anthropic.com")
    for _name, p in providers._items.items():
        base = p.get("base_url") or ""
        if p.get("kind") == "subscription" or not base:
            continue
        anthropic_compat = any(h in base for h in _ANTHROPIC_COMPAT_HOSTS)
        if not anthropic_compat:
            assert p.get("sub_model"), "Expected invariant was not satisfied at source line 50."
