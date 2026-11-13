"""Shared LLM defaults for GSSC LangGraph domain workflows.

Provider of choice: xAI (Grok) via ``langchain_xai.ChatXAI``.
"""

from gssc_langgraph.llm.chat import create_chat_model
from gssc_langgraph.llm.config import ResolvedLlmConfig, resolve_llm_config
from gssc_langgraph.llm.constants import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_XAI_MODEL,
    GSSC_XAI_MODEL_ENV,
    XAI_API_KEY_ENV,
    XAI_MODEL_ENV,
)

__all__ = [
    "DEFAULT_LLM_PROVIDER",
    "DEFAULT_XAI_MODEL",
    "GSSC_XAI_MODEL_ENV",
    "XAI_API_KEY_ENV",
    "XAI_MODEL_ENV",
    "ResolvedLlmConfig",
    "create_chat_model",
    "resolve_llm_config",
]
