"""Model-free conversational echo graph with MemorySaver persistence.

Demo / integration assistant for multi-turn threads (``thread_id``). Stays
free of LLM clients so local dev and CI work without API keys.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from gssc_langgraph.checkpoint import compile_with_memory


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

graph = compile_with_memory(builder, {"name": "GSSC Conversation"})
