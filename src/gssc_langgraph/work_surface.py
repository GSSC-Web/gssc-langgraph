"""Detect whether a goal/change set targets langgraph service vs gssc5 apps."""

from __future__ import annotations

import re
from typing import Any, Literal

WorkSurface = Literal["langgraph", "gssc5_fe", "gssc5_be", "mixed", "unknown"]

_DIFF_GIT_RE = re.compile(r"(?m)^diff --git ")

_FE_PATH_RE = re.compile(
    r"(?i)(^|/)"
    r"(gssc5-web/"
    r"|apps/(?:public|members|admin)/"
    r"|prompt-overlay/"
    r"|[^/]+\.(?:component|html|scss|css)\.(?:ts|js)$"
    r"|[^/]+\.html$)"
)
_BE_PATH_RE = re.compile(
    r"(?i)(^|/)"
    r"(gssc5-(?:api|backend|server)/"
    r"|apps/api/"
    r"|nest-cli\.json$)"
)
_LANGGRAPH_PATH_RE = re.compile(
    r"(?i)(^|/)"
    r"(src/gssc_langgraph/"
    r"|src/graphs/"
    r"|langgraph\.json$"
    r")"
)

_FE_GOAL_RE = re.compile(
    r"(?i)\b(angular|tailwind|prompt[- ]overlay|gssc5-web|css token|"
    r"border-gssc|theme token)\b"
)
_BE_GOAL_RE = re.compile(
    r"(?i)\b(gssc5[- ]?(api|backend|server)|nestjs|nest\.js)\b"
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


def detect_work_surface(
    goal: str = "",
    change_set: dict[str, Any] | None = None,
    *,
    requirements: str = "",
) -> WorkSurface:
    """Classify work as langgraph service, gssc5 FE/BE, mixed, or unknown."""
    text = f"{goal}\n{requirements}".strip()
    paths = _paths_from_change_set(change_set)

    fe_paths = any(_FE_PATH_RE.search(p) for p in paths)
    be_paths = any(_BE_PATH_RE.search(p) for p in paths)
    lg_paths = any(_LANGGRAPH_PATH_RE.search(p) for p in paths)

    if sum(bool(x) for x in (fe_paths, be_paths, lg_paths)) > 1:
        return "mixed"
    if fe_paths:
        return "gssc5_fe"
    if be_paths:
        return "gssc5_be"
    if lg_paths:
        return "langgraph"

    kinds: list[WorkSurface] = []
    if _FE_GOAL_RE.search(text):
        kinds.append("gssc5_fe")
    if _BE_GOAL_RE.search(text):
        kinds.append("gssc5_be")
    if _LANGGRAPH_GOAL_RE.search(text):
        kinds.append("langgraph")
    if len(kinds) > 1:
        return "mixed"
    if len(kinds) == 1:
        return kinds[0]
    return "unknown"


def is_gssc5_app_surface(surface: WorkSurface) -> bool:
    return surface in ("gssc5_fe", "gssc5_be", "mixed")
