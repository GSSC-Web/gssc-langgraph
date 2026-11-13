"""software_dev graph + checks + plan."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from gssc_langgraph.checkpoint import compile_with_memory, thread_config
from gssc_langgraph.graphs.software_dev.graph import builder as software_builder
from gssc_langgraph.graphs.software_dev.graph import graph as software_graph
from gssc_langgraph.review.collect import collect_workspace
from gssc_langgraph.software.checks import (
    check_discipline,
    check_match,
    check_scope,
    check_third_party,
    check_trace,
    verdict_from,
)
from gssc_langgraph.software.plan import build_plan
from gssc_langgraph.software.types import ChangeSet


def test_software_graph_is_compiled() -> None:
    assert software_graph is not None
    assert software_graph.name == "GSSC Software Dev"


@pytest.mark.asyncio
async def test_passes_current_workspace_closeout() -> None:
    raw = collect_workspace(str(Path.cwd()))
    cs: ChangeSet = {
        "label": raw["label"],
        "diff": raw.get("diff"),
        "files": [
            {
                "path": f["path"],
                "content": f.get("content"),
                "patch": f.get("patch"),
                "status": f["status"],
            }
            for f in raw["files"]
        ],
    }
    result = await software_graph.ainvoke(
        {
            "goal": "Close out current gssc-langgraph software",
            "label": cs["label"],
            "changeSet": cs,
            "files": {
                f["path"]: f["content"]
                for f in cs["files"]
                if f.get("content") is not None
            },
        },
        thread_config(f"software-workspace-{uuid.uuid4()}"),
    )
    assert result["verdict"] == "PASS"
    assert len(result["plan"]) > 0
    assert "scope" in result["checksRun"]
    assert "discipline" in result["checksRun"]
    assert "verdict" in result["steps"]
    assert "synthesize" in result["steps"]
    assert result["synthesisNote"].startswith(("ok", "skipped:", "error:"))
    assert isinstance(result["narrativeSummary"], str)
    assert len(result["specialistNotes"]) == 1
    assert result["specialistNotes"][0]["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_plans_from_goal_alone() -> None:
    result = await software_graph.ainvoke(
        {"goal": "Add a new domain graph for membership lookups"},
        thread_config(f"software-plan-{uuid.uuid4()}"),
    )
    assert result["verdict"] == "PASS"
    assert any(s["id"] == "scaffold_graph" for s in result["plan"])
    assert any(s["id"] == "closeout" for s in result["plan"])
    assert "synthesize" in result["steps"]
    assert result["synthesisNote"].startswith(("ok", "skipped:", "error:"))
    assert len(result["specialistNotes"]) == 1


@pytest.mark.asyncio
async def test_appends_specialist_notes_across_thread_turns() -> None:
    graph = compile_with_memory(
        software_builder, {"name": "GSSC Software Dev (test memory)"}
    )
    config = thread_config(f"software-mem-{uuid.uuid4()}")
    first = await graph.ainvoke({"goal": "First planning pass"}, config)
    assert len(first["specialistNotes"]) == 1
    second = await graph.ainvoke(
        {"goal": "Second planning pass"}, config
    )
    assert len(second["specialistNotes"]) == 2
    assert "Second" in second["specialistNotes"][1]["goal"]


def test_fails_when_new_graph_unregistered() -> None:
    cs: ChangeSet = {
        "label": "diff",
        "files": [
            {
                "path": "src/gssc_langgraph/graphs/orphan/graph.py",
                "status": "added",
                "content": '''
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

class S(TypedDict, total=False):
    x: str

builder = StateGraph(S)
builder.add_node("n", lambda _s: {"x": "1"})
builder.add_edge(START, "n")
builder.add_edge("n", END)
graph = builder.compile(name="Orphan")
''',
            },
            {
                "path": "langgraph.json",
                "status": "unchanged",
                "content": json.dumps(
                    {
                        "graphs": {
                            "health": (
                                "./src/gssc_langgraph/graphs/health/graph.py:graph"
                            ),
                        }
                    }
                ),
            },
        ],
    }
    findings = [*check_trace(cs), *check_match(cs)]
    assert any(f["check"] == "trace" for f in findings)
    assert verdict_from(findings) == "FAIL"


def test_fails_on_bun_only_packaging() -> None:
    findings = check_third_party(
        {
            "label": "diff",
            "files": [
                {
                    "path": "package.json",
                    "status": "added",
                    "content": (
                        '{\n  "name": "x",\n'
                        '  "packageManager": "bun@1.4.4"\n}\n'
                    ),
                }
            ],
        }
    )
    assert any(f["severity"] == "error" for f in findings)


def test_fails_when_baseline_assistant_removed() -> None:
    findings = check_discipline(
        {
            "label": "diff",
            "files": [
                {
                    "path": "langgraph.json",
                    "status": "modified",
                    "content": json.dumps(
                        {
                            "graphs": {
                                "software_dev": (
                                    "./src/gssc_langgraph/graphs/software_dev/"
                                    "graph.py:graph"
                                ),
                            }
                        }
                    ),
                    "patch": (
                        '-  "health": '
                        '"./src/gssc_langgraph/graphs/health/graph.py:graph",\n'
                    ),
                }
            ],
        }
    )
    assert any(
        f["check"] == "discipline" and "health" in f["message"] for f in findings
    )


def test_scope_errors_when_empty() -> None:
    findings = check_scope("", None)
    assert verdict_from(findings) == "FAIL"


def test_build_plan_mentions_closeout_and_third_party() -> None:
    plan = build_plan("fix health checkedAt", None)
    assert any(s["id"] == "reproduce_fix" for s in plan)
    assert any(s["id"] == "third_party" for s in plan)
    assert any(s["id"] == "closeout" for s in plan)
