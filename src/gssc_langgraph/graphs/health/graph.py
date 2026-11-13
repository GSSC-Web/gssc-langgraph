"""Minimal health graph for service smoke checks.

The LangGraph Agent Server also exposes HTTP ``/ok``; this graph is a
first-class assistant id (``health``) so clients can call the same
threads/runs API used for real workflows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class HealthState(TypedDict, total=False):
    status: str
    service: str
    checkedAt: str


def check_health(_state: HealthState) -> HealthState:
    return {
        "status": "ok",
        "service": "gssc-langgraph",
        "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


builder = StateGraph(HealthState)
builder.add_node("checkHealth", check_health)
builder.add_edge(START, "checkHealth")
builder.add_edge("checkHealth", END)

graph = builder.compile(name="GSSC Health")
