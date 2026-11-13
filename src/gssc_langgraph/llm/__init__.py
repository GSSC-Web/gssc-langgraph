"""LLM helpers (xAI / Grok defaults). Minimal surface for domain synthesis."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedLlmConfig:
    has_api_key: bool
    model: str = "grok-2-latest"
    api_key: str = ""


def resolve_llm_config(overrides: dict[str, Any] | None = None) -> ResolvedLlmConfig:
    """Resolve LLM config from env (XAI_API_KEY) and optional overrides."""
    overrides = overrides or {}
    api_key = str(overrides.get("api_key") or os.environ.get("XAI_API_KEY") or "")
    model = str(
        overrides.get("model")
        or os.environ.get("XAI_MODEL")
        or os.environ.get("GSSC_LLM_MODEL")
        or "grok-2-latest"
    )
    return ResolvedLlmConfig(
        has_api_key=bool(api_key.strip()),
        model=model,
        api_key=api_key,
    )


def create_chat_model(*, temperature: float = 0, **kwargs: Any) -> Any:
    """Create a chat model. Raises if XAI_API_KEY is missing."""
    cfg = resolve_llm_config(kwargs if "api_key" in kwargs or "model" in kwargs else None)
    if kwargs.get("api_key"):
        cfg = ResolvedLlmConfig(
            has_api_key=True,
            model=str(kwargs.get("model") or cfg.model),
            api_key=str(kwargs["api_key"]),
        )
    if not cfg.has_api_key:
        raise RuntimeError("XAI_API_KEY is required to create a chat model")

    try:
        from langchain_xai import ChatXAI
    except ImportError:
        from langchain_openai import ChatOpenAI as ChatXAI  # type: ignore[assignment]

    return ChatXAI(
        model=cfg.model,
        api_key=cfg.api_key,
        temperature=temperature,
        **{k: v for k, v in kwargs.items() if k not in ("api_key", "model", "temperature")},
    )


__all__ = ["ResolvedLlmConfig", "create_chat_model", "resolve_llm_config"]
