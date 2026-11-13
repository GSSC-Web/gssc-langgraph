"""GSSC LangGraph Agent Server (Python)."""

from __future__ import annotations


def main() -> None:
    """CLI entry for ``gssc-langgraph`` — prints package help."""
    print(
        "gssc-langgraph — Python LangGraph Agent Server\n"
        "\n"
        "Assistants: health, conversation, closeout_review, software_dev, test_development\n"
        "CLIs: closeout | software | test-dev\n"
        "Env: XAI_API_KEY, GSSC_XAI_MODEL, GSSC_CHECKPOINT_BACKEND, GSSC_LANGGRAPH_API_KEY\n"
        "See README.md for Agent Server / langgraph.json wiring."
    )


# Key helpers re-exported for convenience (import-heavy graph modules stay lazy).
from gssc_langgraph.checkpoint import (  # noqa: E402
    compile_graph,
    compile_with_memory,
    create_checkpointer,
    create_checkpointer_from_env,
    resolve_checkpoint_config,
    thread_config,
)
from gssc_langgraph.llm import (  # noqa: E402
    DEFAULT_XAI_MODEL,
    create_chat_model,
    resolve_llm_config,
)

__all__ = [
    "DEFAULT_XAI_MODEL",
    "compile_graph",
    "compile_with_memory",
    "create_chat_model",
    "create_checkpointer",
    "create_checkpointer_from_env",
    "main",
    "resolve_checkpoint_config",
    "resolve_llm_config",
    "thread_config",
]
