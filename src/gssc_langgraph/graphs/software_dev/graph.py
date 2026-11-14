"""Agentic software development workflow (model-free plan/checks + optional LLM
synthesis).

Invoke via Agent Server assistant id ``software_dev``, or ``software`` CLI.

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
    return {
        "changeSet": build_change_set(state),
        "goal": state.get("goal") or "",
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
    plan = build_plan(combined or goal, state.get("changeSet"))
    return {
        "plan": plan,
        "steps": ["plan_work"],
    }


def _make_check_node(check_id: SoftwareCheckId):
    def node(state: SoftwareState) -> dict[str, Any]:
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
        "verdict": verdict,
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
builder.add_edge("synthesize", END)

# Agent Server injects its own checkpointer; do not attach InMemorySaver here.
graph = builder.compile(name="GSSC Software Dev")
