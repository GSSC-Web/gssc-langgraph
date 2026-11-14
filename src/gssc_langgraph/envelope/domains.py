"""DomainPin helpers — map work surfaces / paths to envelope domain ids."""

from __future__ import annotations

from typing import Any

from gssc_langgraph.envelope.types import DomainId
from gssc_langgraph.work_surface import (
    WorkSurface,
    classify_path,
    detect_work_surface,
)

_FE_APP_DOMAIN: dict[str, DomainId] = {
    "public": "public-fe",
    "members": "members-fe",
    "admin": "admin-fe",
}

_HINT_ALIASES: dict[str, DomainId] = {
    "backend": "backend",
    "be": "backend",
    "gssc5_be": "backend",
    "api": "backend",
    "public-fe": "public-fe",
    "public": "public-fe",
    "members-fe": "members-fe",
    "members": "members-fe",
    "admin-fe": "admin-fe",
    "admin": "admin-fe",
    "fe": "public-fe",
    "gssc5_fe": "public-fe",
    "langgraph": "langgraph",
    "python": "langgraph",
}


def _fe_domain_for_path(path: str) -> DomainId:
    lower = path.lower().replace("\\", "/")
    for app, domain in _FE_APP_DOMAIN.items():
        if f"apps/{app}/" in lower or f"gssc5-web/apps/{app}/" in lower:
            return domain
    return "public-fe"


def domains_from_paths(paths: list[str]) -> list[DomainId]:
    found: set[DomainId] = set()
    for path in paths:
        kind = classify_path(path)
        if kind == "gssc5_be":
            found.add("backend")
        elif kind == "gssc5_fe":
            found.add(_fe_domain_for_path(path))
        elif kind == "langgraph":
            found.add("langgraph")
    return _ordered(found)


def domains_from_surface(surface: WorkSurface) -> list[DomainId]:
    if surface == "gssc5_be":
        return ["backend"]
    if surface == "gssc5_fe":
        return ["public-fe"]
    if surface == "langgraph":
        return ["langgraph"]
    if surface == "mixed":
        return ["backend", "public-fe"]
    return ["unknown"]


def pin_domains(
    *,
    goal: str = "",
    requirements: str = "",
    change_set: dict[str, Any] | None = None,
    domain_hint: str | list[str] | None = None,
) -> list[DomainId]:
    """Resolve DomainPin for SoftDev/TestDev/Closeout responses.

    Honors optional ``domainHint`` when set. Never defaults gssc5 app
    tickets to ``langgraph`` / ``src/gssc_langgraph``.
    """
    if domain_hint:
        hints = domain_hint if isinstance(domain_hint, list) else [domain_hint]
        resolved: list[DomainId] = []
        for h in hints:
            key = str(h).strip().lower()
            if key in _HINT_ALIASES:
                d = _HINT_ALIASES[key]
                if d not in resolved:
                    resolved.append(d)
        if resolved:
            return resolved

    paths: list[str] = []
    if change_set:
        for f in change_set.get("files") or []:
            p = f.get("path") if isinstance(f, dict) else None
            if p:
                paths.append(str(p))
    from_paths = domains_from_paths(paths)
    if from_paths:
        return from_paths

    surface = detect_work_surface(goal, change_set, requirements=requirements)
    return domains_from_surface(surface)


def _ordered(found: set[DomainId]) -> list[DomainId]:
    order: list[DomainId] = [
        "backend",
        "public-fe",
        "members-fe",
        "admin-fe",
        "langgraph",
        "unknown",
    ]
    return [d for d in order if d in found]
