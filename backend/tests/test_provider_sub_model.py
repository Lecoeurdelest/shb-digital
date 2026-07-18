"""sub_model per-provider (yaml, optional) — provider không map tên claude (local Ollama) khai
sub_model để SUB spawn model tồn tại; provider khác trả None → giữ SUB_MODEL haiku (D-45b)."""

from __future__ import annotations

from app.orch.providers import conv_sub_model


def test_local_has_sub_model():
    assert conv_sub_model("local") == "qwen3:8b"


def test_other_providers_none_keeps_haiku_default():
    assert conv_sub_model("zai") is None
    assert conv_sub_model("claude-cli") is None


def test_unknown_provider_none_not_crash():
    # tên lạ → không raise ở tầng sub_model (resolve_env mới là chỗ fail loud)
    assert conv_sub_model("khong-ton-tai") is None
