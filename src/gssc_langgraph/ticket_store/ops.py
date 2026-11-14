"""Read/write lean ticket artifacts via LangGraph Store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from langgraph.store.base import BaseStore

try:
    from langgraph.config import get_store as _lg_get_store
except ImportError:  # pragma: no cover
    _lg_get_store = None  # type: ignore[assignment]

from gssc_langgraph.ticket_store.keys import (
    join_key_from_mapping,
    ticket_namespace,
    workspace_from_config,
)
from gssc_langgraph.ticket_store.types import (
    DEFAULT_TICKET_TTL_HOURS,
    TICKET_ARTIFACT_SCHEMA_VERSION,
    TicketArtifact,
)


def store_handoff_enabled(
    state: Mapping[str, Any],
    configurable: Mapping[str, Any] | None = None,
) -> bool:
    """Opt-out via state.storeHandoff=false or configurable.storeHandoffEnabled=false."""
    cfg = configurable or {}
    if cfg.get("storeHandoffEnabled") is False:
        return False
    if state.get("storeHandoff") is False:
        return False
    return True


def resolve_store(store: BaseStore | None = None) -> BaseStore | None:
    """Prefer an explicit store; else Agent Server / compile(store=…) via get_store()."""
    if store is not None:
        return store
    if _lg_get_store is None:
        return None
    try:
        return _lg_get_store()
    except Exception:
        return None


def lean_plan(plan: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in plan or []:
        if not isinstance(step, dict):
            continue
        item: dict[str, Any] = {
            "id": str(step.get("id") or ""),
            "title": str(step.get("title") or ""),
        }
        for key in ("domain", "kind"):
            if step.get(key):
                item[key] = step[key]
        paths = step.get("paths")
        if isinstance(paths, list) and paths:
            # Paths only — never embedded file content.
            item["paths"] = [str(p) for p in paths[:20]]
        out.append(item)
    return out


def lean_cases(cases: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for case in cases or []:
        if not isinstance(case, dict):
            continue
        item = {
            "id": str(case.get("id") or ""),
            "title": str(case.get("title") or ""),
            "status": str(case.get("status") or ""),
        }
        if case.get("domain"):
            item["domain"] = case["domain"]
        out.append(item)
    return out


def lean_gaps(gaps: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        item = {
            "id": str(gap.get("id") or ""),
            "title": str(gap.get("title") or ""),
            "severity": str(gap.get("severity") or ""),
        }
        if gap.get("domain"):
            item["domain"] = gap["domain"]
        out.append(item)
    return out


def finding_codes(findings: list[Any] | None) -> list[str]:
    codes: list[str] = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        code = str(f.get("code") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def get_ticket_artifact(
    store: BaseStore | None,
    state: Mapping[str, Any],
    *,
    configurable: Mapping[str, Any] | None = None,
) -> TicketArtifact | None:
    store = resolve_store(store)
    if store is None or not store_handoff_enabled(state, configurable):
        return None
    key = join_key_from_mapping(state)
    if not key:
        return None
    ns = ticket_namespace(workspace_from_config(configurable))
    try:
        item = store.get(ns, key)
    except Exception:
        return None
    if item is None or not isinstance(item.value, dict):
        return None
    return item.value  # type: ignore[return-value]


def put_ticket_artifact(
    store: BaseStore | None,
    state: Mapping[str, Any],
    *,
    updated_by: str,
    configurable: Mapping[str, Any] | None = None,
    context_ref: Mapping[str, Any] | None = None,
    ttl_hours: float | None = DEFAULT_TICKET_TTL_HOURS,
) -> TicketArtifact | None:
    """Merge lean fields into the ticket key. No-op when store/key unavailable."""
    store = resolve_store(store)
    if store is None or not store_handoff_enabled(state, configurable):
        return None
    key = join_key_from_mapping(state)
    if not key:
        return None
    ns = ticket_namespace(workspace_from_config(configurable))
    existing: dict[str, Any] = {}
    try:
        prev = store.get(ns, key)
        if prev and isinstance(prev.value, dict):
            existing = dict(prev.value)
    except Exception:
        existing = {}

    label = ""
    cs = state.get("changeSet")
    if isinstance(cs, dict):
        label = str(cs.get("label") or "")
    if not label:
        label = str(state.get("label") or "")

    artifact: TicketArtifact = {
        **existing,  # type: ignore[misc]
        "schemaVersion": TICKET_ARTIFACT_SCHEMA_VERSION,
        "label": label or str(existing.get("label") or key),
        "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updatedBy": updated_by,
    }
    kid = str(state.get("kaneoTaskId") or existing.get("kaneoTaskId") or "").strip()
    if kid:
        artifact["kaneoTaskId"] = kid

    domains = list(state.get("domains") or [])
    if domains:
        artifact["domains"] = [str(d) for d in domains]

    plan = lean_plan(state.get("plan") if isinstance(state.get("plan"), list) else None)
    if plan:
        artifact["plan"] = plan

    verdict = str(state.get("verdict") or "")
    if updated_by == "SoftDev" and verdict:
        artifact["softDevVerdict"] = verdict
    if updated_by == "TestDev" and verdict:
        artifact["testDevVerdict"] = verdict

    cases = lean_cases(
        state.get("testCases") if isinstance(state.get("testCases"), list) else None
    )
    if cases:
        artifact["testCasesSummary"] = cases
    gaps = lean_gaps(state.get("gaps") if isinstance(state.get("gaps"), list) else None)
    if gaps:
        artifact["gapsSummary"] = gaps

    codes = finding_codes(
        state.get("findings") if isinstance(state.get("findings"), list) else None
    )
    if codes:
        artifact["findingCodes"] = codes

    if context_ref:
        artifact["contextRef"] = {
            k: context_ref[k]
            for k in ("root", "cacheKey", "skillIds", "memoryIds")
            if k in context_ref
        }

    payload = dict(artifact)
    try:
        if ttl_hours is None:
            store.put(ns, key, payload)
        else:
            store.put(ns, key, payload, ttl=ttl_hours)
    except (TypeError, NotImplementedError, ValueError):
        # InMemoryStore and some backends reject ttl=; retry without.
        try:
            store.put(ns, key, payload)
        except Exception:
            return None
    except Exception:
        return None
    return artifact
