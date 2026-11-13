"""
Deterministic implementation plan for the software_dev workflow.

Mirrors the gssc5 software agent operation loop (scope → implement →
third-party-first → focused tests → closeout) adapted for Python+uv.
"""

from __future__ import annotations

import re

from gssc_langgraph.software.types import ChangeSet, PlanStep

GRAPH_FILE_RE = re.compile(
    r"^(?:src/gssc_langgraph/graphs|src/graphs)/([^/]+)/graph\.py$"
)


def _changed_graph_ids(cs: ChangeSet | None) -> list[str]:
    if not cs:
        return []
    ids: set[str] = set()
    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if m and f["status"] not in ("unchanged", "deleted"):
            ids.add(m.group(1))
    return sorted(ids)


def _goal_mentions(goal: str, *needles: str) -> bool:
    g = goal.lower()
    return any(n in g for n in needles)


def build_plan(goal: str, change_set: ChangeSet | None) -> list[PlanStep]:
    """Build ordered plan steps from a goal string and optional change set."""
    steps: list[PlanStep] = []
    trimmed = goal.strip()
    graphs = _changed_graph_ids(change_set)
    g_lower = trimmed.lower()

    adding_graph = (
        _goal_mentions(
            trimmed,
            "add graph",
            "new graph",
            "domain graph",
            "new assistant",
            "add assistant",
        )
        or (
            bool(re.search(r"\b(add|new|create|scaffold)\b", g_lower))
            and bool(re.search(r"\b(graph|assistant|workflow)\b", g_lower))
        )
        or any(
            change_set
            and any(
                f["path"]
                in (
                    f"src/gssc_langgraph/graphs/{gid}/graph.py",
                    f"src/graphs/{gid}/graph.py",
                )
                and f["status"] == "added"
                for f in change_set["files"]
            )
            for gid in graphs
        )
    )
    fixing = _goal_mentions(trimmed, "fix", "bug", "repair", "regress")

    if trimmed:
        detail = (
            f'Confirm in-scope goal: “{trimmed[:200]}'
            f'{"…" if len(trimmed) > 200 else ""}”. Do not rewrite '
            "requirements/contracts to match buggy code."
        )
    else:
        detail = (
            "No free-text goal — treat the change set as the software "
            "closeout scope (same spirit as gssc5 software-closeout-review)."
        )
    steps.append({"id": "scope", "title": "Scope the work", "detail": detail})

    if adding_graph:
        steps.append(
            {
                "id": "scaffold_graph",
                "title": "Scaffold the LangGraph assistant",
                "detail": (
                    "Add `src/gssc_langgraph/graphs/<id>/graph.py` with "
                    "StateGraph, `graph = builder.compile()` (or "
                    "`compile_with_memory` for conversational graphs), and "
                    "`graph.name`. Keep smoke assistants model-free."
                ),
            }
        )
        steps.append(
            {
                "id": "register",
                "title": "Register the assistant",
                "detail": (
                    'Wire `"<id>": "./src/gssc_langgraph/graphs/<id>/graph.py:graph"` '
                    "in langgraph.json and document the assistant id + input "
                    "shape in README."
                ),
            }
        )
    elif graphs:
        steps.append(
            {
                "id": "implement_graphs",
                "title": "Implement graph changes",
                "detail": (
                    f"Touch only the in-scope assistants ({', '.join(graphs)}); "
                    "preserve baseline gssc5 contract id (health)."
                ),
            }
        )
    elif fixing:
        steps.append(
            {
                "id": "reproduce_fix",
                "title": "Reproduce then fix",
                "detail": (
                    "Add or run a focused pytest that fails for the bug, then "
                    "fix software to satisfy the intended contract — do not "
                    "weaken asserts to match broken SW."
                ),
            }
        )
    else:
        steps.append(
            {
                "id": "implement",
                "title": "Implement behavior",
                "detail": (
                    "Change the smallest set of Python modules under "
                    "src/gssc_langgraph/. Prefer langgraph + langgraph CLI "
                    "over a custom HTTP server."
                ),
            }
        )

    steps.append(
        {
            "id": "third_party",
            "title": "Stay third-party-first",
            "detail": (
                "Use LangGraph, langgraph CLI Agent Server, Python+uv, and "
                "pytest. Flag reinvented FastAPI/Flask/Express/Hono/Elysia "
                "servers or leftover Bun-as-primary packaging."
            ),
        }
    )
    steps.append(
        {
            "id": "tests",
            "title": "Run focused tests",
            "detail": (
                "Add/update pytest coverage for touched graphs. Prefer "
                "`pytest` / `uv run pytest` on the focused files; do not fix "
                "failing tests by watering down asserts when software is wrong."
            ),
        }
    )
    steps.append(
        {
            "id": "closeout",
            "title": "Software closeout",
            "detail": (
                "Run `software` (this workflow) before merge. Peer with the "
                "separate test_dev bot when test closeout is required — do not "
                "own test-bot files."
            ),
        }
    )
    return steps
