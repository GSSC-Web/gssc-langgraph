"""Resolve service-wide LLM defaults from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from gssc_langgraph.llm.constants import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_XAI_MODEL,
    GSSC_XAI_MODEL_ENV,
    XAI_API_KEY_ENV,
    XAI_MODEL_ENV,
)

LlmProvider = str  # currently always "xai"


@dataclass(frozen=True)
class ResolvedLlmConfig:
    """Resolved LLM defaults (does not construct a client)."""

    provider: LlmProvider
    """Chat model id passed to ChatXAI (e.g. grok-4.7)."""
    model: str
    """True when XAI_API_KEY is present (non-empty)."""
    has_api_key: bool


def _env(name: str, env: Mapping[str, str] | None = None) -> str | None:
    source = env if env is not None else os.environ
    value = source.get(name)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def resolve_llm_config(
    overrides: Mapping[str, str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> ResolvedLlmConfig:
    """Resolve provider/model/key presence from env.

    Does not construct a client or require a key — safe for tests and smoke graphs.
    Model order: overrides['model'] → GSSC_XAI_MODEL → XAI_MODEL → grok-4.7.
    """
    model_override = None
    if overrides:
        raw = overrides.get("model")
        if raw is not None:
            model_override = str(raw).strip() or None

    model = (
        model_override
        or _env(GSSC_XAI_MODEL_ENV, env)
        or _env(XAI_MODEL_ENV, env)
        or DEFAULT_XAI_MODEL
    )

    return ResolvedLlmConfig(
        provider=DEFAULT_LLM_PROVIDER,
        model=model,
        has_api_key=bool(_env(XAI_API_KEY_ENV, env)),
    )
