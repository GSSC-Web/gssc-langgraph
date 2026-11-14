"""
Deterministic implementation plan for the software_dev workflow.

Mirrors the gssc5 software agent operation loop (scope → implement →
third-party-first → focused tests → closeout). Specializes steps for
langgraph service code vs gssc5 FE/BE app work.
"""

from __future__ import annotations

import re

from gssc_langgraph.envelope.domains import pin_domains
from gssc_langgraph.envelope.types import DomainId
from gssc_langgraph.software.types import ChangeSet, PlanStep, PlanStepKind
from gssc_langgraph.work_surface import (
    WorkSurface,
    classify_path,
    detect_work_surface,
)

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
        if classify_path(path) == "gssc5_fe":
            out.append(path)
    return out[:12]


def _be_paths(cs: ChangeSet | None) -> list[str]:
    if not cs:
        return []
    out: list[str] = []
    for f in cs["files"]:
        path = f["path"]
        if f["status"] in ("unchanged", "deleted"):
            continue
        if classify_path(path) == "gssc5_be":
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
    paths = _be_paths(change_set)
    path_hint = (
        ", ".join(f"`{p}`" for p in paths[:5]) if paths else "touched backend modules"
    )
    steps: list[PlanStep] = [
        {
            "id": "scope",
            "title": "Scope the BE work",
            "detail": (
                f'Confirm in-scope gssc5 Elysia/Bun backend goal: “{trimmed[:200]}'
                f'{"…" if len(trimmed) > 200 else ""}”. '
                "Do not plan Angular/Tailwind FE scaffolds or LangGraph graphs "
                "for backend-only tickets."
                if trimmed
                else (
                    "No free-text goal — treat the gssc5 backend "
                    "(`apps/backend`) change set as software closeout scope."
                )
            ),
        },
        {
            "id": "implement",
            "title": "Implement BE behavior",
            "detail": (
                f"Change the smallest set of Elysia/Prisma backend modules "
                f"({path_hint}). Keep public/members app contracts stable "
                "unless the task explicitly widens them."
            ),
        },
        {
            "id": "third_party",
            "title": "Stay on the gssc5 BE stack",
            "detail": (
                "Use the gssc5-web backend toolchain (Bun, Elysia, Prisma/"
                "Prismabox, mise). Do not invent Angular component harnesses "
                "or Python LangGraph assistants for pure backend work."
            ),
        },
        {
            "id": "tests",
            "title": "Run focused BE tests",
            "detail": (
                "Add/update companion Bun `*.test.ts` beside sources. Prefer "
                "`bun test <path>` or `mise run //backend:test` on focused "
                "suites — not the Angular FE harness."
            ),
        },
        {
            "id": "closeout",
            "title": "Software closeout",
            "detail": (
                "Re-run `software_dev` with a structured change set "
                "(`files` / unified diff). Peer with `test_development` for "
                "backend Bun test closeout — not FE Lexical stubs."
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


def _existing_test_paths(cs: ChangeSet | None, *, surface: WorkSurface) -> list[str]:
    """Return ``*.test.ts`` paths already present in the change set."""
    if not cs:
        return []
    out: list[str] = []
    for f in cs["files"]:
        path = f["path"]
        if f["status"] == "deleted":
            continue
        if not path.endswith(".test.ts") and not path.endswith(".test.js"):
            continue
        if classify_path(path) == surface:
            out.append(path)
    return out


def _build_mixed_fe_be_plan(
    goal: str, change_set: ChangeSet | None
) -> list[PlanStep]:
    """Dual-domain plan: BE Bun + FE ng — no winner-take-all."""
    trimmed = goal.strip()
    be = _be_paths(change_set)
    fe = _fe_paths(change_set)
    be_hint = ", ".join(f"`{p}`" for p in be[:4]) if be else "backend modules"
    fe_hint = ", ".join(f"`{p}`" for p in fe[:4]) if fe else "FE modules"
    be_tests = _existing_test_paths(change_set, surface="gssc5_be")
    fe_tests = _existing_test_paths(change_set, surface="gssc5_fe")
    be_test_hint = (
        ", ".join(f"`{p}`" for p in be_tests[:3])
        if be_tests
        else "existing backend Bun tests in/near the change set"
    )
    fe_test_hint = (
        ", ".join(f"`{p}`" for p in fe_tests[:3])
        if fe_tests
        else "existing FE `*.test.ts` in/near the change set"
    )
    return [
        {
            "id": "scope",
            "title": "Scope mixed BE + FE work",
            "detail": (
                f'Confirm dual-domain goal: “{trimmed[:200]}'
                f'{"…" if len(trimmed) > 200 else ""}”. '
                f"Backend surfaces ({be_hint}) and FE surfaces ({fe_hint}) "
                "both stay in scope — do not collapse to FE-only or BE-only."
                if trimmed
                else (
                    "Mixed change set — keep both gssc5 backend (`apps/backend`) "
                    "and FE (`apps/public|members|admin`) in scope."
                )
            ),
        },
        {
            "id": "implement_be",
            "title": "Implement BE behavior",
            "detail": (
                f"Change the smallest Elysia/Bun/Prisma set ({be_hint}). "
                "Do not invent markers/tests absent from the change set."
            ),
        },
        {
            "id": "implement_fe",
            "title": "Implement FE behavior",
            "detail": (
                f"Change the smallest Angular/Tailwind set ({fe_hint}). "
                "Do not invent markers/tests absent from the change set."
            ),
        },
        {
            "id": "third_party",
            "title": "Stay on each domain's stack",
            "detail": (
                "Backend: Bun/Elysia/Prisma/mise. FE: Angular/Tailwind/ng. "
                "Do not apply FE harness advice to backend paths or vice versa."
            ),
        },
        {
            "id": "tests",
            "title": "Run focused BE + FE tests",
            "detail": (
                f"BE: `bun test` / `mise run //backend:test` on existing loci "
                f"({be_test_hint}). FE: `bunx ng test --watch=false` on "
                f"existing loci ({fe_test_hint}). Prefer update of tests "
                "already in the change set over inventing new paths."
            ),
        },
        {
            "id": "closeout",
            "title": "Software closeout",
            "detail": (
                "Re-run `software_dev` with the mixed change set. Peer with "
                "`test_development` for dual-domain Bun + ng closeout."
            ),
        },
    ]


_KIND_BY_ID: dict[str, PlanStepKind] = {
    "scope": "other",
    "implement": "implement",
    "implement_be": "implement",
    "implement_fe": "implement",
    "implement_graphs": "implement",
    "scaffold_graph": "implement",
    "register": "alm",
    "reproduce_fix": "test",
    "third_party": "other",
    "tests": "test",
    "closeout": "alm",
}


def _default_domain_for_surface(surface: WorkSurface) -> DomainId:
    if surface == "gssc5_be":
        return "backend"
    if surface == "gssc5_fe":
        return "public-fe"
    if surface == "langgraph":
        return "langgraph"
    if surface == "mixed":
        return "backend"
    return "unknown"


def _commands_for_step(step_id: str, domain: DomainId) -> list[str]:
    if step_id != "tests" and not step_id.startswith("implement"):
        if step_id == "closeout":
            return ["software_dev", "test_development"]
        return []
    if domain == "backend":
        return ["bun test", "mise run //backend:test"]
    if domain in ("public-fe", "members-fe", "admin-fe"):
        return ["bunx ng test --watch=false"]
    if domain == "langgraph":
        return ["uv run pytest"]
    return []


def _annotate_plan(
    steps: list[PlanStep],
    *,
    surface: WorkSurface,
    change_set: ChangeSet | None,
    domains: list[DomainId],
) -> list[PlanStep]:
    """Attach domain / kind / paths / commands for v2 payload.plan[] (GLG-42)."""
    primary = domains[0] if domains else _default_domain_for_surface(surface)
    be_paths = _be_paths(change_set)
    fe_paths = _fe_paths(change_set)
    be_tests = _existing_test_paths(change_set, surface="gssc5_be")
    fe_tests = _existing_test_paths(change_set, surface="gssc5_fe")
    out: list[PlanStep] = []
    for step in steps:
        sid = step["id"]
        domain: DomainId = primary
        paths: list[str] = []
        if sid in ("implement_be",) or (
            sid == "tests" and "backend" in domains and "public-fe" not in domains
        ):
            domain = "backend"
            paths = be_paths if sid.startswith("implement") else be_tests
        elif sid in ("implement_fe",):
            domain = next(
                (d for d in domains if d.endswith("-fe")),
                "public-fe",
            )
            paths = fe_paths
        elif sid == "tests" and surface == "mixed":
            # Dual-domain test step: tag backend primary; FE commands still listed.
            domain = "backend"
            paths = be_tests + fe_tests
        elif sid == "tests" and surface == "gssc5_fe":
            domain = next((d for d in domains if d.endswith("-fe")), "public-fe")
            paths = fe_tests
        elif sid == "tests" and surface == "gssc5_be":
            domain = "backend"
            paths = be_tests
        elif surface == "gssc5_fe":
            domain = next((d for d in domains if d.endswith("-fe")), "public-fe")
            paths = fe_paths if sid.startswith("implement") else []
        elif surface == "gssc5_be":
            domain = "backend"
            paths = be_paths if sid.startswith("implement") else []
        elif surface == "langgraph":
            domain = "langgraph"

        kind = _KIND_BY_ID.get(sid, "other")
        commands = _commands_for_step(sid, domain)
        if sid == "tests" and surface == "mixed":
            commands = [
                "bun test",
                "mise run //backend:test",
                "bunx ng test --watch=false",
            ]
        annotated: PlanStep = {
            **step,
            "domain": domain,
            "kind": kind,
            "paths": paths[:12],
            "commands": commands,
        }
        out.append(annotated)
    return out


def build_plan(
    goal: str,
    change_set: ChangeSet | None,
    *,
    requirements: str = "",
    domain_hint: str | list[str] | None = None,
) -> list[PlanStep]:
    """Build ordered plan steps from a goal string and optional change set."""
    surface: WorkSurface = detect_work_surface(
        goal, change_set, requirements=requirements
    )
    domains = pin_domains(
        goal=goal,
        requirements=requirements,
        change_set=change_set,
        domain_hint=domain_hint,
    )
    if domain_hint and "backend" in domains and not any(
        d.endswith("-fe") for d in domains
    ):
        steps = _build_be_plan(goal, change_set)
        return _annotate_plan(steps, surface="gssc5_be", change_set=change_set, domains=domains)
    if domain_hint and any(d.endswith("-fe") for d in domains) and "backend" not in domains:
        steps = _build_fe_plan(goal, change_set)
        return _annotate_plan(steps, surface="gssc5_fe", change_set=change_set, domains=domains)

    if surface == "gssc5_fe":
        steps = _build_fe_plan(goal, change_set)
        return _annotate_plan(steps, surface=surface, change_set=change_set, domains=domains)
    if surface == "gssc5_be":
        steps = _build_be_plan(goal, change_set)
        return _annotate_plan(steps, surface=surface, change_set=change_set, domains=domains)
    if surface == "mixed":
        has_fe = bool(_fe_paths(change_set))
        has_be = bool(_be_paths(change_set))
        if has_fe and has_be and not _changed_graph_ids(change_set):
            steps = _build_mixed_fe_be_plan(goal, change_set)
            return _annotate_plan(
                steps, surface="mixed", change_set=change_set, domains=domains
            )
        if has_fe and not _changed_graph_ids(change_set):
            steps = _build_fe_plan(goal, change_set)
            return _annotate_plan(
                steps, surface="gssc5_fe", change_set=change_set, domains=domains
            )
        if has_be and not _changed_graph_ids(change_set):
            steps = _build_be_plan(goal, change_set)
            return _annotate_plan(
                steps, surface="gssc5_be", change_set=change_set, domains=domains
            )
    steps = _build_langgraph_plan(goal, change_set)
    return _annotate_plan(
        steps, surface="langgraph", change_set=change_set, domains=domains or ["langgraph"]
    )
