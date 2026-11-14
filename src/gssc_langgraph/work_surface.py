"""Detect whether a goal/change set targets langgraph service vs gssc5 apps."""

from __future__ import annotations

import re
from typing import Any, Literal

WorkSurface = Literal["langgraph", "gssc5_fe", "gssc5_be", "mixed", "unknown"]

_DIFF_GIT_RE = re.compile(r"(?m)^diff --git ")

# Prefer specific app roots. Do NOT match bare ``gssc5-web/`` (that folder
# holds both FE apps and ``apps/backend``).
_BE_PATH_RE = re.compile(
    r"(?i)(^|/)"
    r"(gssc5-web/apps/backend/"
    r"|apps/backend/"
    r"|gssc5-(?:api|backend|server)/"
    r"|apps/api/"
    r"|prisma/"
    r"|nest-cli\.json$)"
)
_FE_PATH_RE = re.compile(
    r"(?i)(^|/)"
    r"(gssc5-web/apps/(?:public|members|admin)/"
    r"|apps/(?:public|members|admin)/"
    r"|prompt-overlay/"
    r"|[^/]+\.(?:component|html|scss|css)\.(?:ts|js)$"
    r"|[^/]+\.html$)"
)
_LANGGRAPH_PATH_RE = re.compile(
    r"(?i)(^|/)"
    r"(src/gssc_langgraph/"
    r"|src/graphs/"
    r"|langgraph\.json$"
    r")"
)

_FE_GOAL_RE = re.compile(
    r"(?i)\b(angular|tailwind|prompt[- ]overlay|css token|"
    r"border-gssc|theme token)\b"
)
_BE_GOAL_RE = re.compile(
    r"(?i)\b(elysia|prisma|prismabox|bun test|apps/backend|"
    r"gssc5[- ]?(api|backend|server)|login[- ]session|nestjs|nest\.js)\b"
)
_LANGGRAPH_GOAL_RE = re.compile(
    r"(?i)\b(langgraph|assistant id|graph\.py|agent server|"
    r"software_dev|test_development|closeout_review)\b"
)


def looks_like_unified_diff(diff: str | None) -> bool:
    """True when ``diff`` contains at least one ``diff --git`` header."""
    if not diff or not diff.strip():
        return False
    return bool(_DIFF_GIT_RE.search(diff))


def _paths_from_change_set(change_set: dict[str, Any] | None) -> list[str]:
    if not change_set:
        return []
    files = change_set.get("files") or []
    return [str(f.get("path") or "") for f in files if f.get("path")]


def classify_path(path: str) -> WorkSurface | None:
    """Classify one filesystem path. Backend wins over FE for shared roots."""
    if not path:
        return None
    # BE before FE: ``gssc5-web/apps/backend`` must not look like FE.
    if _BE_PATH_RE.search(path):
        return "gssc5_be"
    if _FE_PATH_RE.search(path):
        return "gssc5_fe"
    if _LANGGRAPH_PATH_RE.search(path):
        return "langgraph"
    return None


def detect_work_surface(
    goal: str = "",
    change_set: dict[str, Any] | None = None,
    *,
    requirements: str = "",
) -> WorkSurface:
    """Classify work as langgraph service, gssc5 FE/BE, mixed, or unknown."""
    text = f"{goal}\n{requirements}".strip()
    paths = _paths_from_change_set(change_set)

    kinds: set[WorkSurface] = set()
    for path in paths:
        kind = classify_path(path)
        if kind:
            kinds.add(kind)

    if len(kinds) > 1:
        return "mixed"
    if len(kinds) == 1:
        return next(iter(kinds))

    goal_kinds: list[WorkSurface] = []
    if _FE_GOAL_RE.search(text):
        goal_kinds.append("gssc5_fe")
    if _BE_GOAL_RE.search(text):
        goal_kinds.append("gssc5_be")
    if _LANGGRAPH_GOAL_RE.search(text):
        goal_kinds.append("langgraph")
    if len(goal_kinds) > 1:
        # Prefer BE when Elysia/backend cues beat generic Angular noise.
        if "gssc5_be" in goal_kinds and "gssc5_fe" in goal_kinds:
            if _BE_GOAL_RE.search(text) and not re.search(
                r"(?i)\b(angular|tailwind|prompt[- ]overlay)\b", text
            ):
                return "gssc5_be"
        return "mixed"
    if len(goal_kinds) == 1:
        return goal_kinds[0]
    return "unknown"


def is_gssc5_app_surface(surface: WorkSurface) -> bool:
    return surface in ("gssc5_fe", "gssc5_be", "mixed")
