"""Model-free conversational echo graph for Agent Server.

Demo / integration assistant for multi-turn threads. Stays free of LLM
clients so local dev and CI work without API keys.

The ``langgraph.json`` export compiles **without** a custom checkpointer —
Agent Server owns persistence (set ``POSTGRES_URI`` for a durable store).
Use ``compile_with_memory(builder, …)`` only in tests / direct invoke helpers.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph


class ConversationState(TypedDict, total=False):
    message: str
    reply: str
    steps: Annotated[list[str], add]


def respond(state: ConversationState, config: RunnableConfig) -> ConversationState:
    configurable = (config or {}).get("configurable") or {}
    prefix = configurable.get("replyPrefix") or "gssc-conversation"
    text = (state.get("message") or "").strip() or "(empty message)"
    return {
        "reply": f"[{prefix}] received: {text}",
        "steps": ["respond"],
    }


builder = StateGraph(ConversationState)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)

# Agent Server injects its own checkpointer; do not attach InMemorySaver here.
graph = builder.compile(name="GSSC Conversation")
