"""Minimal health graph for service smoke checks.

The LangGraph Agent Server also exposes HTTP ``/ok``; this graph is a
first-class assistant id (``health``) so clients can call the same
threads/runs API used for real workflows.

Emits a thin v2 ``response`` envelope (GLG-45) for the shared coordinator
decoder.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from gssc_langgraph.envelope import build_graph_response


class HealthState(TypedDict, total=False):
    status: str
    service: str
    checkedAt: str
    response: dict[str, Any]
    schemaVersion: str
    verdict: str
    summary: str


def check_health(_state: HealthState) -> HealthState:
    checked = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    status = "ok"
    service = "gssc-langgraph"
    verdict = "PASS" if status == "ok" else "ERROR"
    summary = f"{service} {status} @ {checked}"
    response = build_graph_response(
        tool="GSSC_Health",
        verdict=verdict,  # type: ignore[arg-type]
        summary=summary,
        findings=[],
        domains=[],
        payload={"status": status, "service": service, "checkedAt": checked},
        label="health",
    )
    return {
        "status": status,
        "service": service,
        "checkedAt": checked,
        "verdict": verdict,
        "summary": summary,
        "schemaVersion": "2",
        "response": response,
    }


builder = StateGraph(HealthState)
builder.add_node("checkHealth", check_health)
builder.add_edge(START, "checkHealth")
builder.add_edge("checkHealth", END)

graph = builder.compile(name="GSSC Health")
