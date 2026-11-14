"""Join keys and namespaces for ticket Store handoff."""

from __future__ import annotations

from typing import Any, Mapping

# Namespace prefix: ("gssc", "ticket", <workspace|project>)
NAMESPACE_ROOT = ("gssc", "ticket")
DEFAULT_WORKSPACE = "default"


def ticket_namespace(workspace: str | None = None) -> tuple[str, ...]:
    ws = (workspace or "").strip() or DEFAULT_WORKSPACE
    return (*NAMESPACE_ROOT, ws)


def ticket_key(*, label: str = "", kaneo_task_id: str = "") -> str | None:
    """Prefer kaneoTaskId, then label. None when neither is usable."""
    kid = (kaneo_task_id or "").strip()
    if kid:
        return kid
    lab = (label or "").strip()
    if lab:
        return lab
    return None


def join_key_from_mapping(state: Mapping[str, Any]) -> str | None:
    label = ""
    cs = state.get("changeSet")
    if isinstance(cs, dict):
        label = str(cs.get("label") or "")
    if not label:
        label = str(state.get("label") or "")
    return ticket_key(
        label=label,
        kaneo_task_id=str(state.get("kaneoTaskId") or ""),
    )


def workspace_from_config(configurable: Mapping[str, Any] | None) -> str:
    cfg = configurable or {}
    for key in ("ticketWorkspace", "workspace", "projectId"):
        val = cfg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return DEFAULT_WORKSPACE
