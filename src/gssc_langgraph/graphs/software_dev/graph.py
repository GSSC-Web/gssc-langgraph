"""Agentic software development workflow (model-free plan/checks + optional LLM
synthesis).

Invoke via Agent Server assistant id ``software_dev``, or ``software`` CLI.

Emits a v2 ``response`` GraphResponse envelope (GLG-35…46) so coordinators
can branch on ``response.verdict`` without parsing narrative.

The ``langgraph.json`` export compiles **without** a custom checkpointer —
Agent Server owns thread persistence (``POSTGRES_URI`` for durable store).
``specialistNotes`` accumulate across Agent Server / SDK threads. For unit
tests that need an in-process saver, use ``compile_with_memory(builder, …)``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from operator import add
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from gssc_langgraph.envelope import (
    build_graph_response,
    coerce_text,
    context_ref_from_bundle,
    normalize_findings,
    pin_domains,
    strip_oversized_content,
)
from gssc_langgraph.gssc5 import format_gssc5_context, load_gssc5_context_for_role
from gssc_langgraph.gssc5.types import Gssc5ContextBundle
from gssc_langgraph.software.checks import CHECK_RUNNERS, summarize, verdict_from
from gssc_langgraph.software.plan import build_plan
from gssc_langgraph.software.synthesize import synthesize_software
from gssc_langgraph.software.types import (
    ChangeSet,
    ChangedFile,
    FileStatus,
    PlanStep,
    ProposedMemoryUpdate,
    SoftwareCheckId,
    SoftwareFinding,
    SoftwareVerdict,
    SpecialistNote,
)


def replace_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return right if right is not None else []


def replace_nullable(left: Any, right: Any) -> Any:
    return right if right is not None else None


class SoftwareState(TypedDict, total=False):
    goal: str
    requirements: str
    diff: str
    files: dict[str, str]
    label: str
    fileStatuses: dict[str, FileStatus]
    changeSet: ChangeSet | None
    domainHint: str | list[str]
    includeContextBodies: bool
    plan: Annotated[list[PlanStep], replace_list]
    findings: Annotated[list[SoftwareFinding], add]
    checksRun: Annotated[list[SoftwareCheckId], add]
    verdict: SoftwareVerdict | str
    summary: str
    gssc5Context: Annotated[Gssc5ContextBundle | None, replace_nullable]
    gssc5ContextText: str
    gssc5Root: str
    narrativeSummary: str
    proposedMemoryUpdates: Annotated[list[ProposedMemoryUpdate], replace_list]
    synthesisNote: str
    specialistNotes: Annotated[list[SpecialistNote], add]
    steps: Annotated[list[str], add]
    response: dict[str, Any]
    schemaVersion: str
    domains: list[str]


_DIFF_PATH_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)


def build_change_set(state: SoftwareState) -> ChangeSet | None:
    if state.get("changeSet"):
        return state["changeSet"]

    files: list[ChangedFile] = []
    file_map = state.get("files") or {}
    statuses = state.get("fileStatuses") or {}
    for path, content in file_map.items():
        files.append(
            {
                "path": path,
                "content": content,
                "status": statuses.get(path, "modified"),
            }
        )

    diff = state.get("diff") or ""
    if diff.strip():
        for match in _DIFF_PATH_RE.finditer(diff):
            path = match.group(2)
            if not any(f["path"] == path for f in files):
                files.append({"path": path, "status": "modified"})

    if not files and not diff.strip():
        return None

    label = (state.get("label") or "").strip() or ("diff" if diff else "files")
    result: ChangeSet = {"label": label, "files": files}
    if diff:
        result["diff"] = diff
    return result


def parse_input(state: SoftwareState) -> dict[str, Any]:
    cs = build_change_set(state)
    findings: list[SoftwareFinding] = []
    cs, stripped = strip_oversized_content(cs)  # type: ignore[arg-type]
    if stripped:
        # Keep path+status; warn. ERROR only when nothing usable remains.
        has_paths = bool((cs or {}).get("files"))
        severity = "warning" if has_paths else "error"
        findings.append(
            {
                "check": "scope",
                "severity": severity,  # type: ignore[typeddict-item]
                "code": "input.content_too_large",
                "message": (
                    "Lean changeSet: stripped oversized embedded content for "
                    f"{', '.join(stripped[:5])}. Prefer path+status + "
                    "unified diff (≤32KB request guidance)."
                ),
                "fix": "Omit ChangedFile.content; use diff --git headers.",
            }
        )
    goal = coerce_text(state.get("goal")).strip()
    requirements = coerce_text(state.get("requirements")).strip()
    if not goal and not cs:
        findings.append(
            {
                "check": "scope",
                "severity": "error",
                "code": "input.goal_or_changeset_required",
                "message": "SoftDev requires a goal and/or a changeSet (input ERROR)",
            }
        )
    return {
        "changeSet": cs,
        "goal": goal,
        "requirements": requirements,
        "findings": findings,
        "steps": ["parse_input"],
    }


def load_gssc5_context_node(
    state: SoftwareState,
    config: RunnableConfig,
) -> dict[str, Any]:
    configurable = (config or {}).get("configurable") or {}
    query = "\n".join(
        part for part in [state.get("goal") or "", state.get("requirements") or ""] if part
    )
    opts: dict[str, Any] = {
        "query": query,
        "requireSkills": ["software-closeout-review"],
        "maxSkills": 3,
        "maxMemories": 2,
    }
    if configurable.get("gssc5Root") is not None:
        opts["root"] = configurable["gssc5Root"]
    if configurable.get("gssc5Enabled") is not None:
        opts["enabled"] = configurable["gssc5Enabled"]
    bundle = load_gssc5_context_for_role("software", opts)
    return {
        "gssc5Context": bundle,
        "gssc5ContextText": format_gssc5_context(bundle),
        "gssc5Root": bundle["root"],
        "steps": ["load_gssc5_context"],
    }


def plan_work(state: SoftwareState) -> dict[str, Any]:
    goal = (state.get("goal") or "").strip()
    req = (state.get("requirements") or "").strip()
    combined = "\n".join(part for part in [goal, req] if part)
    plan = build_plan(
        combined or goal,
        state.get("changeSet"),
        requirements=req,
        domain_hint=state.get("domainHint"),
    )
    domains = pin_domains(
        goal=goal,
        requirements=req,
        change_set=state.get("changeSet"),  # type: ignore[arg-type]
        domain_hint=state.get("domainHint"),
    )
    return {
        "plan": plan,
        "domains": domains,
        "steps": ["plan_work"],
    }


def _make_check_node(check_id: SoftwareCheckId):
    def node(state: SoftwareState) -> dict[str, Any]:
        # Skip remaining checks when input already ERROR'd.
        if any(
            f.get("severity") == "error"
            and str(f.get("code") or "").startswith(("changeset.", "input."))
            for f in (state.get("findings") or [])
        ):
            return {"checksRun": [check_id], "steps": [f"check_{check_id}"]}
        findings = CHECK_RUNNERS[check_id](
            state.get("goal") or "",
            state.get("changeSet"),
        )
        return {
            "findings": findings,
            "checksRun": [check_id],
            "steps": [f"check_{check_id}"],
        }

    node.__name__ = f"check_{check_id}"
    return node


def finalize(state: SoftwareState) -> dict[str, Any]:
    findings = list(state.get("findings") or [])
    plan = list(state.get("plan") or [])
    verdict = verdict_from(findings)
    summary = summarize(verdict, findings, len(plan))
    note: SpecialistNote = {
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": verdict,  # type: ignore[typeddict-item]
        "summary": summary,
    }
    label = (state.get("changeSet") or {}).get("label") or state.get("label")
    if label:
        note["label"] = label
    goal = (state.get("goal") or "").strip()
    if goal:
        note["goal"] = goal
    return {
        "verdict": verdict,
        "summary": summary,
        "specialistNotes": [note],
        "steps": ["verdict"],
    }


async def synthesize(
    state: SoftwareState,
    config: RunnableConfig,
) -> dict[str, Any]:
    configurable = (config or {}).get("configurable") or {}
    if (state.get("verdict") or "") == "ERROR":
        return {
            "narrativeSummary": "",
            "proposedMemoryUpdates": [],
            "synthesisNote": "skipped — input ERROR",
            "steps": ["synthesize"],
        }
    cs = state.get("changeSet")
    paths: list[str] = []
    if isinstance(cs, dict):
        paths = [
            str(f.get("path") or "")
            for f in (cs.get("files") or [])
            if f.get("path")
        ]
    if not paths and state.get("files"):
        paths = list((state.get("files") or {}).keys())
    synth_input: dict[str, Any] = {
        "verdict": state.get("verdict") or "",
        "summary": state.get("summary") or "",
        "goal": state.get("goal") or "",
        "plan": list(state.get("plan") or []),
        "findings": list(state.get("findings") or []),
        "gssc5ContextText": state.get("gssc5ContextText") or "",
        "changeSetPaths": paths,
    }
    if configurable.get("synthesisEnabled") is not None:
        synth_input["enabled"] = configurable["synthesisEnabled"]
    result = await synthesize_software(synth_input)  # type: ignore[arg-type]
    return {
        "narrativeSummary": result["narrativeSummary"],
        "proposedMemoryUpdates": result["proposedMemoryUpdates"],
        "synthesisNote": result["note"],
        "steps": ["synthesize"],
    }


def emit_response(state: SoftwareState) -> dict[str, Any]:
    include_bodies = bool(state.get("includeContextBodies"))
    ref, slim = context_ref_from_bundle(
        state.get("gssc5Context"),  # type: ignore[arg-type]
        include_bodies=include_bodies,
    )
    findings = normalize_findings(state.get("findings"))  # type: ignore[arg-type]
    # Prefer explicit input codes when present.
    for i, raw in enumerate(state.get("findings") or []):
        if raw.get("code") and i < len(findings):
            findings[i]["code"] = str(raw["code"])
    domains = list(state.get("domains") or []) or pin_domains(
        goal=state.get("goal") or "",
        requirements=state.get("requirements") or "",
        change_set=state.get("changeSet"),  # type: ignore[arg-type]
        domain_hint=state.get("domainHint"),
    )
    label = (
        (state.get("changeSet") or {}).get("label")
        or state.get("label")
        or ""
    )
    payload: dict[str, Any] = {
        "goal": state.get("goal") or "",
        "plan": list(state.get("plan") or []),
        "checksRun": list(state.get("checksRun") or []),
        "narrativeSummary": state.get("narrativeSummary") or "",
        "synthesisNote": state.get("synthesisNote") or "",
        "proposedMemoryUpdates": list(state.get("proposedMemoryUpdates") or []),
    }
    response = build_graph_response(
        tool="GSSC_Software_Dev",
        verdict=state.get("verdict") or "FAIL",  # type: ignore[arg-type]
        summary=state.get("summary") or "",
        findings=findings,
        domains=domains,  # type: ignore[arg-type]
        payload=payload,
        label=str(label),
        context_ref=ref,
    )
    out: dict[str, Any] = {
        "response": response,
        "schemaVersion": "2",
        "domains": domains,
        "steps": ["emit_response"],
    }
    # Slim default: drop fat skill/memory echoes from final MCP state.
    # Coordinators must branch on ``response`` (schemaVersion 2).
    if not include_bodies:
        out["gssc5ContextText"] = ""
        if slim is not None:
            out["gssc5Context"] = slim  # type: ignore[assignment]
    return out


_CHECK_ORDER: list[SoftwareCheckId] = [
    "scope",
    "trace",
    "match",
    "quality",
    "third_party",
    "discipline",
]

builder = StateGraph(SoftwareState)
builder.add_node("parse_input", parse_input)
builder.add_node("load_gssc5_context", load_gssc5_context_node)
builder.add_node("plan_work", plan_work)
for _cid in _CHECK_ORDER:
    builder.add_node(f"check_{_cid}", _make_check_node(_cid))
builder.add_node("finalize", finalize)
builder.add_node("synthesize", synthesize)
builder.add_node("emit_response", emit_response)

builder.add_edge(START, "parse_input")
builder.add_edge("parse_input", "load_gssc5_context")
builder.add_edge("load_gssc5_context", "plan_work")
builder.add_edge("plan_work", "check_scope")
builder.add_edge("check_scope", "check_trace")
builder.add_edge("check_trace", "check_match")
builder.add_edge("check_match", "check_quality")
builder.add_edge("check_quality", "check_third_party")
builder.add_edge("check_third_party", "check_discipline")
builder.add_edge("check_discipline", "finalize")
builder.add_edge("finalize", "synthesize")
builder.add_edge("synthesize", "emit_response")
builder.add_edge("emit_response", END)

# Agent Server injects its own checkpointer; do not attach InMemorySaver here.
graph = builder.compile(name="GSSC Software Dev")
