"""Agentic test-development workflow (model-free analysis + optional LLM
synthesis).

Invoke via assistant id ``test_development``, or ``test-dev`` CLI.

Emits a v2 ``response`` GraphResponse envelope (GLG-35…46).

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
    context_ref_from_bundle,
    normalize_findings,
    pin_domains,
    strip_oversized_content,
)
from gssc_langgraph.gssc5 import format_gssc5_context, load_gssc5_context_for_role
from gssc_langgraph.gssc5.types import Gssc5ContextBundle
from gssc_langgraph.test_dev.analyze import run_analysis, summarize, verdict_from
from gssc_langgraph.test_dev.synthesize import synthesize_test_dev
from gssc_langgraph.test_dev.types import (
    ChangeSet,
    ChangedFile,
    Contract,
    CoverageLink,
    FileStatus,
    Finding,
    PlanItem,
    ProposedMemoryUpdate,
    SpecialistNote,
    TestDevCheckId,
    TestDevVerdict,
)


def replace_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return right if right is not None else []


def replace_nullable(left: Any, right: Any) -> Any:
    return right if right is not None else None


class TestDevState(TypedDict, total=False):
    diff: str
    files: dict[str, str]
    label: str
    requirements: str
    fileStatuses: dict[str, FileStatus]
    changeSet: ChangeSet | None
    domainHint: str | list[str]
    includeContextBodies: bool
    scopeGraphIds: Annotated[list[str], replace_list]
    contracts: Annotated[list[Contract], replace_list]
    coverage: Annotated[list[CoverageLink], replace_list]
    findings: Annotated[list[Finding], add]
    checksRun: Annotated[list[TestDevCheckId], add]
    plan: Annotated[list[PlanItem], replace_list]
    commands: Annotated[list[str], replace_list]
    testCases: Annotated[list[dict[str, Any]], replace_list]
    gaps: Annotated[list[dict[str, Any]], replace_list]
    verdict: TestDevVerdict | str
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


def build_change_set(state: TestDevState) -> ChangeSet:
    if state.get("changeSet"):
        return state["changeSet"]  # type: ignore[return-value]

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

    label = (state.get("label") or "").strip() or ("diff" if diff else "files")
    result: ChangeSet = {"label": label, "files": files}
    if diff:
        result["diff"] = diff
    return result


def parse_changeset(state: TestDevState) -> dict[str, Any]:
    cs = build_change_set(state)
    findings: list[Finding] = []
    cs, stripped = strip_oversized_content(cs)  # type: ignore[arg-type]
    if stripped:
        has_paths = bool((cs or {}).get("files"))
        severity = "warning" if has_paths else "error"
        findings.append(
            {
                "check": "scope",
                "severity": severity,  # type: ignore[typeddict-item]
                "code": "input.content_too_large",
                "message": (
                    "Lean changeSet: stripped oversized embedded content for "
                    f"{', '.join(stripped[:5])}"
                ),
            }
        )
    return {
        "changeSet": cs,
        "findings": findings,
        "steps": ["parse_changeset"],
    }


def load_gssc5_context_node(
    state: TestDevState,
    config: RunnableConfig,
) -> dict[str, Any]:
    configurable = (config or {}).get("configurable") or {}
    cs = state.get("changeSet") or build_change_set(state)
    path_hints = " ".join(f["path"] for f in (cs.get("files") or [])[:20])
    query = " ".join(
        part
        for part in [
            state.get("label") or "",
            state.get("requirements") or "",
            path_hints,
            "test closeout",
        ]
        if part
    )
    opts: dict[str, Any] = {
        "query": query,
        "requireSkills": ["test-closeout-review"],
        "maxSkills": 3,
        "maxMemories": 2,
    }
    if configurable.get("gssc5Root") is not None:
        opts["root"] = configurable["gssc5Root"]
    if configurable.get("gssc5Enabled") is not None:
        opts["enabled"] = configurable["gssc5Enabled"]
    bundle = load_gssc5_context_for_role("test", opts)
    return {
        "gssc5Context": bundle,
        "gssc5ContextText": format_gssc5_context(bundle),
        "gssc5Root": bundle["root"],
        "steps": ["load_gssc5_context"],
    }


def analyze_scope(state: TestDevState) -> dict[str, Any]:
    cs = state.get("changeSet") or build_change_set(state)
    if any(
        f.get("severity") == "error"
        and str(f.get("code") or "").startswith(("changeset.", "input."))
        for f in (state.get("findings") or [])
    ):
        domains = pin_domains(
            requirements=state.get("requirements") or "",
            change_set=cs,  # type: ignore[arg-type]
            domain_hint=state.get("domainHint"),
        )
        return {
            "changeSet": cs,
            "domains": domains,
            "testCases": [],
            "gaps": [],
            "steps": ["analyze"],
        }
    result = run_analysis(cs, requirements=state.get("requirements") or "")
    domains = pin_domains(
        requirements=state.get("requirements") or "",
        change_set=cs,  # type: ignore[arg-type]
        domain_hint=state.get("domainHint"),
    )
    return {
        "changeSet": cs,
        "scopeGraphIds": result["scopeGraphIds"],
        "contracts": result["contracts"],
        "coverage": result["coverage"],
        "findings": result["findings"],
        "checksRun": result["checksRun"],
        "plan": result["plan"],
        "commands": result["commands"],
        "testCases": result.get("testCases") or [],
        "gaps": result.get("gaps") or [],
        "domains": domains,
        "steps": ["analyze"],
    }


def finalize(state: TestDevState) -> dict[str, Any]:
    findings = list(state.get("findings") or [])
    plan = list(state.get("plan") or [])
    extra: list[Finding] = []
    # Blocking gaps (error severity) force FAIL even if soft PASS otherwise.
    if any(
        isinstance(g, dict) and g.get("severity") == "error"
        for g in (state.get("gaps") or [])
    ) and not any(
        str(f.get("code") or "").startswith(("changeset.", "input.")) for f in findings
    ):
        if not any(f.get("severity") == "error" for f in findings):
            extra.append(
                {
                    "check": "coverage_map",
                    "severity": "error",
                    "code": "gap.blocking",
                    "message": "Blocking coverage gaps remain — cannot PASS",
                }
            )
    all_findings = findings + extra
    verdict = verdict_from(all_findings)
    summary = summarize(verdict, all_findings, plan)
    note: SpecialistNote = {
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": verdict,  # type: ignore[typeddict-item]
        "summary": summary,
    }
    label = (state.get("changeSet") or {}).get("label") or state.get("label")
    if label:
        note["label"] = label
    out: dict[str, Any] = {
        "verdict": verdict,
        "summary": summary,
        "specialistNotes": [note],
        "steps": ["verdict"],
    }
    if extra:
        out["findings"] = extra
    return out


async def synthesize(
    state: TestDevState,
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
    synth_input: dict[str, Any] = {
        "verdict": state.get("verdict") or "",
        "summary": state.get("summary") or "",
        "findings": list(state.get("findings") or []),
        "plan": list(state.get("plan") or []),
        "scopeGraphIds": list(state.get("scopeGraphIds") or []),
        "commands": list(state.get("commands") or []),
        "gssc5ContextText": state.get("gssc5ContextText") or "",
    }
    if configurable.get("synthesisEnabled") is not None:
        synth_input["enabled"] = configurable["synthesisEnabled"]
    result = await synthesize_test_dev(synth_input)  # type: ignore[arg-type]
    return {
        "narrativeSummary": result["narrativeSummary"],
        "proposedMemoryUpdates": result["proposedMemoryUpdates"],
        "synthesisNote": result["note"],
        "steps": ["synthesize"],
    }


def emit_response(state: TestDevState) -> dict[str, Any]:
    include_bodies = bool(state.get("includeContextBodies"))
    ref, slim = context_ref_from_bundle(
        state.get("gssc5Context"),  # type: ignore[arg-type]
        include_bodies=include_bodies,
    )
    findings = normalize_findings(state.get("findings"))  # type: ignore[arg-type]
    for i, raw in enumerate(state.get("findings") or []):
        if raw.get("code") and i < len(findings):
            findings[i]["code"] = str(raw["code"])
    domains = list(state.get("domains") or []) or pin_domains(
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
        "plan": list(state.get("plan") or []),
        "commands": list(state.get("commands") or []),
        "testCases": list(state.get("testCases") or []),
        "gaps": list(state.get("gaps") or []),
        "scopeGraphIds": list(state.get("scopeGraphIds") or []),
        "checksRun": list(state.get("checksRun") or []),
        "narrativeSummary": state.get("narrativeSummary") or "",
        "synthesisNote": state.get("synthesisNote") or "",
    }
    response = build_graph_response(
        tool="GSSC_Test_Development",
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
    if not include_bodies and slim is not None:
        out["gssc5Context"] = slim  # type: ignore[assignment]
    return out


builder = StateGraph(TestDevState)
builder.add_node("parse_changeset", parse_changeset)
builder.add_node("load_gssc5_context", load_gssc5_context_node)
builder.add_node("analyze", analyze_scope)
builder.add_node("finalize", finalize)
builder.add_node("synthesize", synthesize)
builder.add_node("emit_response", emit_response)

builder.add_edge(START, "parse_changeset")
builder.add_edge("parse_changeset", "load_gssc5_context")
builder.add_edge("load_gssc5_context", "analyze")
builder.add_edge("analyze", "finalize")
builder.add_edge("finalize", "synthesize")
builder.add_edge("synthesize", "emit_response")
builder.add_edge("emit_response", END)

# Agent Server injects its own checkpointer; do not attach InMemorySaver here.
graph = builder.compile(name="GSSC Test Development")
