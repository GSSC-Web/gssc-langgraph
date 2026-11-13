"""
Documented contracts for gssc-langgraph assistants.

These stand in for StrictDoc LLRs in gssc5: each entry is a permanent
behavior a pytest should lock.
"""

from __future__ import annotations

import json
import re

from gssc_langgraph.test_dev.types import ChangeSet, Contract

BASELINE_CONTRACTS: list[Contract] = [
    {
        "id": "health.status_ok",
        "graphId": "health",
        "title": "Health returns ok",
        "requirement": (
            'The health assistant SHALL return status "ok" and identify '
            'service "gssc-langgraph".'
        ),
        "assertHints": ["status", "ok", "gssc-langgraph"],
        "source": "baseline",
    },
    {
        "id": "health.checked_at",
        "graphId": "health",
        "title": "Health timestamps check",
        "requirement": (
            "The health assistant SHALL include a non-empty checkedAt timestamp."
        ),
        "assertHints": ["checkedAt"],
        "source": "baseline",
    },
]

GRAPH_FILE_RE = re.compile(
    r"^(?:src/gssc_langgraph/graphs|src/graphs)/([^/]+)/graph\.py$"
)

TOOLING_GRAPH_IDS: frozenset[str] = frozenset(
    {
        "closeout_review",
        "test_development",
        "software_dev",
    }
)

CHAT_MODEL_RE = re.compile(
    r"ChatOpenAI|ChatAnthropic|ChatXAI|init_chat_model|initChatModel|"
    r"create_chat_model|createChatModel|"
    r"langchain_openai|langchain_anthropic|langchain_xai|"
    r"""from\s+["']@langchain/(?:openai|anthropic|xai)["']"""
)


def _text_of(cs: ChangeSet, path: str) -> str:
    for f in cs["files"]:
        if f["path"] == path:
            return f.get("content") or ""
    return ""


def _graph_body(cs: ChangeSet, graph_id: str) -> str:
    for path in (
        f"src/gssc_langgraph/graphs/{graph_id}/graph.py",
        f"src/graphs/{graph_id}/graph.py",
    ):
        body = _text_of(cs, path)
        if body:
            return body
    return ""


def infer_structural_contracts(
    cs: ChangeSet, graph_ids: list[str]
) -> list[Contract]:
    """Infer minimal compiled/export + invoke-smoke contracts for non-baseline graphs."""
    out: list[Contract] = []
    for gid in graph_ids:
        if any(c["graphId"] == gid for c in BASELINE_CONTRACTS):
            continue
        body = _graph_body(cs, gid)
        if not body:
            continue

        out.append(
            {
                "id": f"{gid}.compiled_export",
                "graphId": gid,
                "title": f"{gid} exports compiled graph",
                "requirement": (
                    f'Graph "{gid}" SHALL export a compiled `graph` with a '
                    "stable graph.name."
                ),
                "assertHints": ["graph", "name", gid.replace("_", " ")],
                "source": "inferred",
            }
        )

        if not CHAT_MODEL_RE.search(body):
            out.append(
                {
                    "id": f"{gid}.invoke_smoke",
                    "graphId": gid,
                    "title": f"{gid} invoke smoke",
                    "requirement": (
                        f'Graph "{gid}" SHALL be invokable in pytest without '
                        "external API keys (model-free smoke)."
                    ),
                    "assertHints": ["invoke"],
                    "source": "inferred",
                }
            )
    return out


def graph_ids_from_change_set(cs: ChangeSet) -> list[str]:
    ids: set[str] = set()
    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if m and f["status"] != "deleted":
            ids.add(m.group(1))
    lg = _text_of(cs, "langgraph.json")
    if lg:
        try:
            parsed = json.loads(lg)
            graphs = parsed.get("graphs") if isinstance(parsed, dict) else None
            if isinstance(graphs, dict):
                ids.update(str(k) for k in graphs)
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(ids)


def changed_graph_ids(cs: ChangeSet) -> list[str]:
    ids: set[str] = set()
    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if m and f["status"] not in ("unchanged", "deleted"):
            ids.add(m.group(1))
    return sorted(ids)


def resolve_contracts(cs: ChangeSet, scope_graph_ids: list[str]) -> list[Contract]:
    baseline = [c for c in BASELINE_CONTRACTS if c["graphId"] in scope_graph_ids]
    inferred = infer_structural_contracts(cs, scope_graph_ids)
    return [*baseline, *inferred]
