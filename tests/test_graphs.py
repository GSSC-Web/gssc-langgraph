"""Health + conversation graphs and compile_with_memory helper."""

from __future__ import annotations

import uuid
from operator import add
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from gssc_langgraph.checkpoint import compile_with_memory, thread_config
from gssc_langgraph.graphs.closeout_review.graph import graph as closeout_graph
from gssc_langgraph.graphs.conversation.graph import builder as conversation_builder
from gssc_langgraph.graphs.conversation.graph import graph as conversation_graph
from gssc_langgraph.graphs.health.graph import graph as health_graph
from gssc_langgraph.graphs.software_dev.graph import graph as software_graph
from gssc_langgraph.graphs.test_development.graph import graph as test_dev_graph

# langgraph.json entrypoints — Agent Server rejects custom checkpointers.
_API_EXPORTED_GRAPHS = (
    ("health", health_graph),
    ("conversation", conversation_graph),
    ("closeout_review", closeout_graph),
    ("software_dev", software_graph),
    ("test_development", test_dev_graph),
)


def test_health_graph_is_compiled() -> None:
    assert health_graph is not None
    assert health_graph.name == "GSSC Health"


def test_health_graph_returns_ok() -> None:
    result = health_graph.invoke({})
    assert result["status"] == "ok"
    assert result["service"] == "gssc-langgraph"
    assert result["checkedAt"]


def test_api_exported_graphs_have_no_custom_checkpointer() -> None:
    for assistant_id, compiled in _API_EXPORTED_GRAPHS:
        assert compiled.checkpointer is None, (
            f"{assistant_id} must export without a custom checkpointer "
            "(Agent Server supplies persistence)"
        )


def test_conversation_graph_is_compiled() -> None:
    assert conversation_graph is not None
    assert conversation_graph.name == "GSSC Conversation"


def test_conversation_echoes_message() -> None:
    result = conversation_graph.invoke({"message": "hello from gssc5"})
    assert "hello from gssc5" in result["reply"]
    assert result["steps"] == ["respond"]


def test_conversation_persists_reducer_state_across_turns_with_memory() -> None:
    # Persistence for multi-turn unit tests uses compile_with_memory on the
    # builder — not the Agent Server export (which has no checkpointer).
    graph = compile_with_memory(
        conversation_builder, {"name": "GSSC Conversation (test memory)"}
    )
    config = thread_config(f"conversation-multi-{uuid.uuid4()}")

    first = graph.invoke({"message": "turn-one"}, config)
    assert "turn-one" in first["reply"]
    assert first["steps"] == ["respond"]

    second = graph.invoke({"message": "turn-two"}, config)
    assert "turn-two" in second["reply"]
    # steps uses an append reducer — MemorySaver keeps prior turn values.
    assert second["steps"] == ["respond", "respond"]

    snapshot = graph.get_state(config)
    assert snapshot.values["steps"] == ["respond", "respond"]
    assert "turn-two" in snapshot.values["reply"]


def test_conversation_isolates_state_across_thread_ids() -> None:
    graph = compile_with_memory(
        conversation_builder, {"name": "GSSC Conversation (test isolate)"}
    )
    a = thread_config(f"conversation-a-{uuid.uuid4()}")
    b = thread_config(f"conversation-b-{uuid.uuid4()}")

    graph.invoke({"message": "only-a"}, a)
    result_b = graph.invoke({"message": "only-b"}, b)

    assert result_b["steps"] == ["respond"]
    assert "only-b" in result_b["reply"]
    assert "only-a" not in result_b["reply"]


def test_compile_with_memory_enables_multi_turn_persistence() -> None:
    class State(TypedDict):
        n: Annotated[int, add]

    builder = StateGraph(State)
    builder.add_node("inc", lambda _state: {"n": 1})
    builder.add_edge(START, "inc")
    builder.add_edge("inc", END)
    graph = compile_with_memory(builder, {"name": "checkpoint-smoke"})
    assert graph.name == "checkpoint-smoke"
    assert graph.checkpointer is not None

    config = thread_config(f"helper-{uuid.uuid4()}")
    graph.invoke({}, config)
    second = graph.invoke({}, config)
    assert second["n"] == 2
