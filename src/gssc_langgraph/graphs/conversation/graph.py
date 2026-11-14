"""Model-free conversational echo graph for Agent Server.

Demo / integration assistant for multi-turn threads. Stays free of LLM
clients so local dev and CI work without API keys.

Optionally wraps results in a thin v2 ``response`` envelope (GLG-46) so
coordinators can use one decoder for all namespace tools.

The ``langgraph.json`` export compiles **without** a custom checkpointer —
Agent Server owns persistence (set ``POSTGRES_URI`` for a durable store).
Use ``compile_with_memory(builder, …)`` only in tests / direct invoke helpers.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from gssc_langgraph.envelope import build_graph_response


class ConversationState(TypedDict, total=False):
    message: str
    reply: str
    steps: Annotated[list[str], add]
    response: dict[str, Any]
    schemaVersion: str
    verdict: str
    summary: str


def respond(state: ConversationState, config: RunnableConfig) -> ConversationState:
    configurable = (config or {}).get("configurable") or {}
    prefix = configurable.get("replyPrefix") or "gssc-conversation"
    text = (state.get("message") or "").strip() or "(empty message)"
    reply = f"[{prefix}] received: {text}"
    summary = reply[:240]
    response = build_graph_response(
        tool="GSSC_Conversation",
        verdict="PASS",
        summary=summary,
        findings=[],
        domains=[],
        payload={"message": state.get("message") or "", "reply": reply, "steps": ["respond"]},
        label="conversation",
    )
    return {
        "reply": reply,
        "steps": ["respond"],
        "verdict": "PASS",
        "summary": summary,
        "schemaVersion": "2",
        "response": response,
    }


builder = StateGraph(ConversationState)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)

# Agent Server injects its own checkpointer; do not attach InMemorySaver here.
graph = builder.compile(name="GSSC Conversation")
