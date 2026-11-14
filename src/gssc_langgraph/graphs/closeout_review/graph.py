"""Agentic closeout review workflow (model-free checks + optional LLM synthesis).

Invoke via Agent Server assistant id ``closeout_review``, or ``closeout`` CLI.

Required input: populated ``files`` / ``changeSet.files``, or a real unified
diff with ``diff --git`` headers. Prose/summary ``diff`` alone yields
``verdict: ERROR`` with ``changeset.required`` (GLG-36/39).

Emits a v2 ``response`` GraphResponse envelope (GLG-35…46).

The ``langgraph.json`` export compiles **without** a custom checkpointer —
Agent Server owns thread persistence (``POSTGRES_URI`` for durable store).
``reviewMemory`` accumulates across Agent Server / SDK threads. For unit
tests that need an in-process saver, use ``compile_with_memory(builder, …)``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from operator import add
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from gssc_langgraph.closeout.checks import CHECK_RUNNERS, summarize, verdict_from
from gssc_langgraph.closeout.synthesize import synthesize_closeout
from gssc_langgraph.closeout.types import (
    ChangeSet,
    ChangedFile,
    CloseoutCheckId,
    CloseoutFinding,
    CloseoutVerdict,
    FileStatus,
    ProposedMemoryUpdate,
    ReviewMemoryNote,
)
from gssc_langgraph.envelope import (
    build_graph_response,
    context_ref_from_bundle,
    normalize_findings,
    pin_domains,
    strip_oversized_content,
)
from gssc_langgraph.gssc5 import (
    ARCH_MEMORY_IDS,
    CLOSEOUT_PEER_SKILL_IDS,
    format_gssc5_context,
    load_gssc5_context_for_role,
)
from gssc_langgraph.gssc5.types import Gssc5ContextBundle


def replace_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return right if right is not None else []


def replace_nullable(left: Any, right: Any) -> Any:
    return right if right is not None else None


class CloseoutState(TypedDict, total=False):
    diff: str
    files: dict[str, str]
    label: str
    fileStatuses: dict[str, FileStatus]
    kaneoTaskId: str
    prScope: str
    uids: Annotated[list[str], replace_list]
    changeSet: ChangeSet | None
    domainHint: str | list[str]
    includeContextBodies: bool
    findings: Annotated[list[CloseoutFinding], add]
    checksRun: Annotated[list[CloseoutCheckId], add]
    verdict: CloseoutVerdict | str
    summary: str
    gssc5Context: Annotated[Gssc5ContextBundle | None, replace_nullable]
    gssc5ContextText: str
    gssc5Root: str
    narrativeSummary: str
    proposedMemoryUpdates: Annotated[list[ProposedMemoryUpdate], replace_list]
    synthesisNote: str
    reviewMemory: Annotated[list[ReviewMemoryNote], add]
    steps: Annotated[list[str], add]
    response: dict[str, Any]
    schemaVersion: str
    domains: list[str]


_DIFF_PATH_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)


def build_change_set(state: CloseoutState) -> ChangeSet:
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


def parse_changeset(state: CloseoutState) -> dict[str, Any]:
    cs = build_change_set(state)
    findings: list[CloseoutFinding] = []
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
                    f"{', '.join(stripped[:5])}. Prefer path+status + "
                    "unified diff (≤32KB request guidance)."
                ),
                "fix": "Omit ChangedFile.content; keep diff --git only.",
            }
        )
    domains = pin_domains(
        change_set=cs,  # type: ignore[arg-type]
        domain_hint=state.get("domainHint"),
    )
    return {
        "changeSet": cs,
        "findings": findings,
        "domains": domains,
        "steps": ["parse_changeset"],
    }


def load_gssc5_context_node(
    state: CloseoutState,
    config: RunnableConfig,
) -> dict[str, Any]:
    configurable = (config or {}).get("configurable") or {}
    cs = state.get("changeSet") or build_change_set(state)
    path_hints = " ".join(f["path"] for f in (cs.get("files") or [])[:20])
    query = " ".join(
        part
        for part in [
            state.get("label") or "",
            state.get("kaneoTaskId") or "",
            state.get("prScope") or "",
            " ".join(state.get("uids") or []),
            path_hints,
            "closeout review requirements software test",
        ]
        if part
    )

    opts: dict[str, Any] = {
        "query": query,
        "requireSkills": list(CLOSEOUT_PEER_SKILL_IDS),
        "requireMemories": list(ARCH_MEMORY_IDS),
        "maxSkills": 3,
        "maxMemories": 3,
    }
    if configurable.get("gssc5Root") is not None:
        opts["root"] = configurable["gssc5Root"]
    if configurable.get("gssc5Enabled") is not None:
        opts["enabled"] = configurable["gssc5Enabled"]
    bundle = load_gssc5_context_for_role("reviewer", opts)

    return {
        "gssc5Context": bundle,
        "gssc5ContextText": format_gssc5_context(bundle),
        "gssc5Root": bundle["root"],
        "steps": ["load_gssc5_context"],
    }


def _make_check_node(check_id: CloseoutCheckId):
    def node(state: CloseoutState) -> dict[str, Any]:
        if any(
            f.get("severity") == "error"
            and str(f.get("code") or "").startswith(("changeset.", "input."))
            for f in (state.get("findings") or [])
        ):
            return {
                "changeSet": state.get("changeSet") or build_change_set(state),
                "checksRun": [check_id],
                "steps": [f"check_{check_id}"],
            }
        cs = state.get("changeSet") or build_change_set(state)
        findings = CHECK_RUNNERS[check_id](cs)
        return {
            "changeSet": cs,
            "findings": findings,
            "checksRun": [check_id],
            "steps": [f"check_{check_id}"],
        }

    node.__name__ = f"check_{check_id}"
    return node


def finalize(state: CloseoutState) -> dict[str, Any]:
    findings = list(state.get("findings") or [])
    verdict = verdict_from(findings)
    summary = summarize(verdict, findings)
    note: ReviewMemoryNote = {
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": verdict,  # type: ignore[typeddict-item]
        "summary": summary,
    }
    label = (state.get("changeSet") or {}).get("label") or state.get("label")
    if label:
        note["label"] = label
    return {
        "verdict": verdict,
        "summary": summary,
        "reviewMemory": [note],
        "steps": ["verdict"],
    }


async def synthesize(state: CloseoutState, config: RunnableConfig) -> dict[str, Any]:
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
        "gssc5ContextText": state.get("gssc5ContextText") or "",
        "kaneoTaskId": state.get("kaneoTaskId") or "",
        "prScope": state.get("prScope") or "",
        "uids": list(state.get("uids") or []),
    }
    if configurable.get("synthesisEnabled") is not None:
        synth_input["enabled"] = configurable["synthesisEnabled"]
    result = await synthesize_closeout(synth_input)  # type: ignore[arg-type]
    return {
        "narrativeSummary": result["narrativeSummary"],
        "proposedMemoryUpdates": result["proposedMemoryUpdates"],
        "synthesisNote": result["note"],
        "steps": ["synthesize"],
    }


def emit_response(state: CloseoutState) -> dict[str, Any]:
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
        change_set=state.get("changeSet"),  # type: ignore[arg-type]
        domain_hint=state.get("domainHint"),
    )
    label = (
        (state.get("changeSet") or {}).get("label")
        or state.get("label")
        or state.get("kaneoTaskId")
        or ""
    )
    payload: dict[str, Any] = {
        "checksRun": list(state.get("checksRun") or []),
        "kaneoTaskId": state.get("kaneoTaskId") or "",
        "prScope": state.get("prScope") or "",
        "uids": list(state.get("uids") or []),
        "narrativeSummary": state.get("narrativeSummary") or "",
        "synthesisNote": state.get("synthesisNote") or "",
    }
    response = build_graph_response(
        tool="GSSC_Closeout_Review",
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


_CHECK_ORDER: list[CloseoutCheckId] = [
    "scope",
    "contracts",
    "software_trace",
    "software_match",
    "software_quality",
    "third_party",
    "test_coverage",
    "test_target",
    "secrets",
]

builder = StateGraph(CloseoutState)
builder.add_node("parse_changeset", parse_changeset)
builder.add_node("load_gssc5_context", load_gssc5_context_node)
for _cid in _CHECK_ORDER:
    builder.add_node(f"check_{_cid}", _make_check_node(_cid))
builder.add_node("finalize", finalize)
builder.add_node("synthesize", synthesize)
builder.add_node("emit_response", emit_response)

builder.add_edge(START, "parse_changeset")
builder.add_edge("parse_changeset", "load_gssc5_context")
builder.add_edge("load_gssc5_context", "check_scope")
builder.add_edge("check_scope", "check_contracts")
builder.add_edge("check_contracts", "check_software_trace")
builder.add_edge("check_software_trace", "check_software_match")
builder.add_edge("check_software_match", "check_software_quality")
builder.add_edge("check_software_quality", "check_third_party")
builder.add_edge("check_third_party", "check_test_coverage")
builder.add_edge("check_test_coverage", "check_test_target")
builder.add_edge("check_test_target", "check_secrets")
builder.add_edge("check_secrets", "finalize")
builder.add_edge("finalize", "synthesize")
builder.add_edge("synthesize", "emit_response")
builder.add_edge("emit_response", END)

# Agent Server injects its own checkpointer; do not attach InMemorySaver here.
graph = builder.compile(name="GSSC Closeout Review")
