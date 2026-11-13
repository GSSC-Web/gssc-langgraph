"""
Deterministic implementation plan for the software_dev workflow.

Mirrors the gssc5 software agent operation loop (scope → implement →
third-party-first → focused tests → closeout). Specializes steps for
langgraph service code vs gssc5 FE/BE app work.
"""

from __future__ import annotations

import re

from gssc_langgraph.software.types import ChangeSet, PlanStep
from gssc_langgraph.work_surface import WorkSurface, detect_work_surface

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


def _fe_paths(cs: ChangeSet | None) -> list[str]:
    if not cs:
        return []
    out: list[str] = []
    for f in cs["files"]:
        path = f["path"]
        if f["status"] in ("unchanged", "deleted"):
            continue
        if (
            "gssc5-web/" in path
            or "/prompt-overlay/" in path
            or path.endswith(".html")
            or ".component." in path
            or path.endswith(".test.ts")
        ):
            out.append(path)
    return out[:12]


def _build_fe_plan(goal: str, change_set: ChangeSet | None) -> list[PlanStep]:
    trimmed = goal.strip()
    paths = _fe_paths(change_set)
    path_hint = ", ".join(f"`{p}`" for p in paths[:5]) if paths else "touched FE files"
    steps: list[PlanStep] = [
        {
            "id": "scope",
            "title": "Scope the FE work",
            "detail": (
                f'Confirm in-scope gssc5 FE goal: “{trimmed[:200]}'
                f'{"…" if len(trimmed) > 200 else ""}”. '
                "Do not plan LangGraph graph scaffolds for Angular/Tailwind UI."
                if trimmed
                else (
                    "No free-text goal — treat the FE change set as software "
                    "closeout scope (Angular/Tailwind app, not langgraph graphs)."
                )
            ),
        },
        {
            "id": "implement",
            "title": "Implement FE behavior",
            "detail": (
                f"Change the smallest set of Angular/Tailwind surfaces "
                f"({path_hint}). Prefer existing gssc theme tokens "
                "(`border-gssc-*`, `bg-gssc-*`, `text-gssc-*`) over raw "
                "utility reds/blues."
            ),
        },
        {
            "id": "third_party",
            "title": "Stay on the gssc5 FE stack",
            "detail": (
                "Use the gssc5-web Angular + Tailwind toolchain (bun/ng). "
                "Do not invent Python/LangGraph graphs for FE tickets."
            ),
        },
        {
            "id": "tests",
            "title": "Run focused FE tests",
            "detail": (
                "Add/update companion `*.test.ts` next to components. Prefer "
                "`bunx ng test --watch=false --include='**/…/*.test.ts'` on "
                "the focused module; do not weaken Lexical/class asserts."
            ),
        },
        {
            "id": "closeout",
            "title": "Software closeout",
            "detail": (
                "Re-run `software_dev` with a structured change set "
                "(`files` / unified diff). Peer with `test_development` for "
                "FE test closeout — not pytest graph.invoke stubs."
            ),
        },
    ]
    return steps


def _build_be_plan(goal: str, change_set: ChangeSet | None) -> list[PlanStep]:
    trimmed = goal.strip()
    steps: list[PlanStep] = [
        {
            "id": "scope",
            "title": "Scope the BE work",
            "detail": (
                f'Confirm in-scope gssc5 API/backend goal: “{trimmed[:200]}'
                f'{"…" if len(trimmed) > 200 else ""}”. '
                "Do not default to LangGraph graph paths unless the ticket "
                "touches this service."
                if trimmed
                else (
                    "No free-text goal — treat the gssc5 backend change set "
                    "as software closeout scope."
                )
            ),
        },
        {
            "id": "implement",
            "title": "Implement BE behavior",
            "detail": (
                "Change the smallest set of gssc5 API/backend modules for "
                "the ticket. Keep contracts with the public/members apps "
                "stable unless the task explicitly widens them."
            ),
        },
        {
            "id": "third_party",
            "title": "Stay on the gssc5 BE stack",
            "detail": (
                "Prefer the existing gssc5 backend toolchain. Do not scaffold "
                "Python LangGraph assistants for pure gssc5 API work."
            ),
        },
        {
            "id": "tests",
            "title": "Run focused BE tests",
            "detail": (
                "Add/update the project's existing unit/integration tests for "
                "touched handlers; keep asserts tied to the API contract."
            ),
        },
        {
            "id": "closeout",
            "title": "Software closeout",
            "detail": (
                "Re-run `software_dev` with populated `files` or a unified "
                "diff; peer with `test_development` for test closeout."
            ),
        },
    ]
    return steps


def _build_langgraph_plan(goal: str, change_set: ChangeSet | None) -> list[PlanStep]:
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


def build_plan(goal: str, change_set: ChangeSet | None) -> list[PlanStep]:
    """Build ordered plan steps from a goal string and optional change set."""
    surface: WorkSurface = detect_work_surface(goal, change_set)
    if surface == "gssc5_fe":
        return _build_fe_plan(goal, change_set)
    if surface == "gssc5_be":
        return _build_be_plan(goal, change_set)
    # mixed / unknown / langgraph → langgraph service planner (safe default
    # for this repo); mixed still gets langgraph steps plus FE path hints
    # only when pure FE was not detected.
    if surface == "mixed" and _fe_paths(change_set) and not _changed_graph_ids(
        change_set
    ):
        return _build_fe_plan(goal, change_set)
    return _build_langgraph_plan(goal, change_set)
