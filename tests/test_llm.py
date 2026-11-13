"""LLM config + ChatXAI construction."""

from __future__ import annotations

import os

import pytest

from gssc_langgraph.llm import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_XAI_MODEL,
    create_chat_model,
    resolve_llm_config,
)

TRACKED = ("XAI_API_KEY", "GSSC_XAI_MODEL", "XAI_MODEL")


@pytest.fixture(autouse=True)
def _restore_llm_env() -> None:
    saved = {key: os.environ.get(key) for key in TRACKED}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_resolve_llm_config_defaults_without_keys() -> None:
    for key in TRACKED:
        os.environ.pop(key, None)

    cfg = resolve_llm_config()
    assert cfg.provider == DEFAULT_LLM_PROVIDER
    assert cfg.provider == "xai"
    assert cfg.model == DEFAULT_XAI_MODEL
    assert cfg.model == "grok-4.7"
    assert cfg.has_api_key is False


def test_gssc_xai_model_wins_over_xai_model() -> None:
    os.environ["XAI_MODEL"] = "grok-4.3"
    os.environ["GSSC_XAI_MODEL"] = "grok-4.6"
    assert resolve_llm_config().model == "grok-4.6"


def test_explicit_override_wins_over_env() -> None:
    os.environ["GSSC_XAI_MODEL"] = "grok-4.6"
    assert resolve_llm_config({"model": "grok-4.5"}).model == "grok-4.5"


def test_has_api_key_reflects_xai_api_key() -> None:
    # Avoid `xai-…` shaped literals so secrets review does not false-positive.
    os.environ["XAI_API_KEY"] = "test-key-not-for-production"
    assert resolve_llm_config().has_api_key is True


def test_create_chat_model_throws_when_key_missing() -> None:
    os.environ.pop("XAI_API_KEY", None)
    with pytest.raises(RuntimeError, match="XAI_API_KEY"):
        create_chat_model()


def test_create_chat_model_constructs_with_resolved_model() -> None:
    os.environ["XAI_API_KEY"] = "test-key-not-for-production"
    os.environ["GSSC_XAI_MODEL"] = "grok-4.7"

    model = create_chat_model(temperature=0)
    assert model is not None
    model_name = getattr(model, "model", None) or getattr(model, "model_name", None)
    assert model_name == "grok-4.7"
