from __future__ import annotations

import pytest

from app.orch.providers import Providers, _load_env_file


def _write(tmp_path, yaml_text: str, env_text: str = "") -> Providers:

    yf = tmp_path / "providers.yaml"
    ef = tmp_path / ".env"
    yf.write_text(yaml_text)
    ef.write_text(env_text)
    import os

    os.environ["PROVIDERS_FILE"] = str(yf)
    os.environ["ENV_FILE"] = str(ef)
    try:
        return Providers(tmp_path)
    finally:
        os.environ.pop("PROVIDERS_FILE", None)
        os.environ.pop("ENV_FILE", None)


_YAML = """
providers:
  - name: claude-cli
    kind: subscription
    default: true
    models: [haiku, sonnet]
  - name: zai
    base_url: https://api.z.ai/api/anthropic
    api_key: ${zai}
    models: [glm-4.6]
"""


def test_default_name_from_flag(tmp_path):
    p = _write(tmp_path, _YAML, "zai=secret123")
    assert p.default_name() == "claude-cli"


def test_subscription_resolves_empty_env(tmp_path):

    p = _write(tmp_path, _YAML, "zai=secret123")
    name, env = p.resolve_env("claude-cli")
    assert name == "claude-cli"
    assert env == {}


def test_keyed_resolves_three_anthropic_vars(tmp_path):

    p = _write(tmp_path, _YAML, "zai=secret123")
    name, env = p.resolve_env("zai")
    assert name == "zai"
    assert env["ANTHROPIC_BASE_URL"] == "https://api.z.ai/api/anthropic"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "secret123"
    assert env["ANTHROPIC_API_KEY"] == "secret123"
    assert set(env) == {"ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"}


def test_none_falls_back_to_default(tmp_path):

    p = _write(tmp_path, _YAML, "zai=secret123")
    name, env = p.resolve_env(None)
    assert name == "claude-cli"
    assert env == {}


def test_missing_key_raises_not_silent(tmp_path):

    p = _write(tmp_path, _YAML, "")
    with pytest.raises(KeyError, match="is missing"):
        p.resolve_env("zai")


def test_unknown_provider_raises(tmp_path):
    p = _write(tmp_path, _YAML, "zai=secret123")
    with pytest.raises(KeyError, match="is not in"):
        p.resolve_env("does-not-exist")


def test_public_view_never_leaks_key(tmp_path):

    p = _write(tmp_path, _YAML, "zai=secret123")
    view = p.public_view()
    blob = repr(view)
    assert "secret123" not in blob, "Expected invariant was not satisfied at source line 88."
    for pv in view:
        assert "api_key" not in pv
        assert isinstance(pv["has_key"], bool)
    by_name = {pv["name"]: pv for pv in view}
    assert by_name["claude-cli"]["has_key"] is True
    assert by_name["claude-cli"]["default"] is True
    assert by_name["zai"]["has_key"] is True


def test_public_view_has_key_false_when_missing(tmp_path):

    p = _write(tmp_path, _YAML, "")
    by_name = {pv["name"]: pv for pv in p.public_view()}
    assert by_name["zai"]["has_key"] is False
    assert by_name["claude-cli"]["has_key"] is True


def test_empty_yaml_falls_back_to_cli(tmp_path):

    p = _write(tmp_path, "providers: []", "")
    assert p.default_name() == "claude-cli"
    name, env = p.resolve_env(None)
    assert name == "claude-cli"
    assert env == {}


def test_env_file_parser_edge(tmp_path):

    ef = tmp_path / ".env"
    ef.write_text('# comment\n\nzai="quoted"\nWRAP=plain\n  spaced = val  \n')
    got = _load_env_file(ef)
    assert got["zai"] == "quoted"
    assert got["WRAP"] == "plain"
    assert got["spaced"] == "val"
    assert "# comment" not in got


def test_reload_picks_up_new_key(tmp_path):

    import os

    yf = tmp_path / "providers.yaml"
    ef = tmp_path / ".env"
    yf.write_text(_YAML)
    ef.write_text("")
    os.environ["PROVIDERS_FILE"] = str(yf)
    os.environ["ENV_FILE"] = str(ef)
    try:
        p = Providers(tmp_path)
        with pytest.raises(KeyError):
            p.resolve_env("zai")
        ef.write_text("zai=nowset")
        p.reload()
        _, env = p.resolve_env("zai")
        assert env["ANTHROPIC_API_KEY"] == "nowset"
    finally:
        os.environ.pop("PROVIDERS_FILE", None)
        os.environ.pop("ENV_FILE", None)
