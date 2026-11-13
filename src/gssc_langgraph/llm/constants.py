"""Default LLM provider / model for GSSC LangGraph graphs that call a chat model.

Prefer xAI (Grok) for this service; override with env when needed.
"""

from __future__ import annotations

# LangChain / LangSmith provider id for xAI.
DEFAULT_LLM_PROVIDER = "xai"

# Default Grok chat model id. Override with GSSC_XAI_MODEL (preferred) or XAI_MODEL.
DEFAULT_XAI_MODEL = "grok-4.7"

# Env var holding the xAI API key (ChatXAI reads this by default).
XAI_API_KEY_ENV = "XAI_API_KEY"

# Preferred env override for the Grok model id used by this service.
GSSC_XAI_MODEL_ENV = "GSSC_XAI_MODEL"

# Alternate env override (matches common LangChain / gateway naming).
XAI_MODEL_ENV = "XAI_MODEL"
