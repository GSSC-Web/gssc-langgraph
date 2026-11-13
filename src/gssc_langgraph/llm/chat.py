"""Create the default chat model: xAI ChatXAI (Grok)."""

from __future__ import annotations

import os
from typing import Any

from gssc_langgraph.llm.config import resolve_llm_config
from gssc_langgraph.llm.constants import XAI_API_KEY_ENV


def create_chat_model(**options: Any) -> Any:
    """Create the default chat model for domain graphs: xAI ``ChatXAI`` (Grok).

    Requires ``XAI_API_KEY`` in the environment (or ``api_key`` / ``apiKey`` in
    options). Model id defaults to ``grok-4.7``, overridable via
    ``GSSC_XAI_MODEL`` / ``XAI_MODEL`` or the ``model`` option.

    Deterministic smoke paths (``health``, ``conversation``) and specialist
    checks stay model-free. Specialist bots may call this only from optional
    synthesis nodes when a key is present; those graphs must still complete
    without a key.
    """
    model_override = options.pop("model", None)
    api_key = options.pop("api_key", None)
    if api_key is None:
        api_key = options.pop("apiKey", None)

    resolved = resolve_llm_config(
        {"model": model_override} if model_override is not None else None
    )

    key = api_key if api_key is not None else os.environ.get(XAI_API_KEY_ENV)
    if not key or not str(key).strip():
        raise RuntimeError(
            f"Missing {XAI_API_KEY_ENV}. Set it in .env (see .env.example) "
            "before calling create_chat_model()."
        )

    from langchain_xai import ChatXAI

    return ChatXAI(
        **options,
        api_key=str(key).strip(),
        model=resolved.model,
    )
