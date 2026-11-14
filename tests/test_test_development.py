"""test_development graph + analyzers."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from gssc_langgraph.checkpoint import compile_with_memory, thread_config
from gssc_langgraph.graphs.test_development.graph import builder as test_dev_builder
from gssc_langgraph.graphs.test_development.graph import graph as test_dev_graph
from gssc_langgraph.review.collect import collect_workspace
from gssc_langgraph.test_dev.analyze import (
    map_coverage,
    resolve_scope,
    run_analysis,
    verdict_from,
)
from gssc_langgraph.test_dev.contracts import BASELINE_CONTRACTS, resolve_contracts
from gssc_langgraph.test_dev.types import ChangeSet

MINIMAL_HEALTH_GRAPH = '''
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

class S(TypedDict, total=False):
    status: str

def n(_state: S) -> S:
    return {"status": "ok"}

builder = StateGraph(S)
builder.add_node("n", n)
builder.add_edge(START, "n")
builder.add_edge("n", END)
graph = builder.compile(name="GSSC Health")
'''

MINIMAL_HEALTH_TEST = '''
from gssc_langgraph.graphs.health.graph import graph as health_graph

def test_health_returns_ok():
    result = health_graph.invoke({})
    assert result["status"] == "ok"
    assert result["service"] == "gssc-langgraph"
    assert result["checkedAt"]
'''


def test_test_dev_graph_is_compiled() -> None:
    assert test_dev_graph is not None
    assert test_dev_graph.name == "GSSC Test Development"


@pytest.mark.asyncio
async def test_invoke_smoke_model_free() -> None:
    result = await test_dev_graph.ainvoke(
        {
            "label": "files",
            "files": {
                "langgraph.json": json.dumps(
                    {
                        "graphs": {
                            "health": (
                                "./src/gssc_langgraph/graphs/health/graph.py:graph"
                            ),
                        }
                    }
                ),
                "src/gssc_langgraph/graphs/health/graph.py": MINIMAL_HEALTH_GRAPH,
                "tests/test_graphs.py": MINIMAL_HEALTH_TEST,
            },
        },
        thread_config(f"test-dev-smoke-{uuid.uuid4()}"),
    )
    assert "verdict" in result["steps"]
    assert "synthesize" in result["steps"]
    assert "coverage_map" in result["checksRun"]
    assert result["verdict"] in ("PASS", "FAIL")
    assert result["synthesisNote"].startswith(("ok", "skipped:", "error:"))
    assert isinstance(result["narrativeSummary"], str)
    assert len(result["specialistNotes"]) == 1


@pytest.mark.asyncio
async def test_passes_current_workspace_for_baseline_contracts() -> None:
    cs = collect_workspace(str(Path.cwd()))
    result = await test_dev_graph.ainvoke(
        {
            "label": cs["label"],
            "changeSet": cs,
            "files": {
                f["path"]: f["content"]
                for f in cs["files"]
                if f.get("content") is not None
            },
        },
        thread_config(f"test-dev-workspace-{uuid.uuid4()}"),
    )
    assert result["verdict"] == "PASS"
    assert "health" in result["scopeGraphIds"]
    assert "test_development" in result["scopeGraphIds"]
    assert "verdict" in result["steps"]
    assert "synthesize" in result["steps"]
    assert result["synthesisNote"].startswith(("ok", "skipped:", "error:"))
    assert result["specialistNotes"][0]["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_appends_specialist_notes_across_thread_turns() -> None:
    graph = compile_with_memory(
        test_dev_builder, {"name": "GSSC Test Development (test memory)"}
    )
    config = thread_config(f"test-dev-mem-{uuid.uuid4()}")
    inp = {
        "label": "files",
        "files": {
            "langgraph.json": json.dumps(
                {
                    "graphs": {
                        "health": (
                            "./src/gssc_langgraph/graphs/health/graph.py:graph"
                        ),
                    }
                }
            ),
        },
    }
    first = await graph.ainvoke(inp, config)
    assert len(first["specialistNotes"]) == 1
    second = await graph.ainvoke(inp, config)
    assert len(second["specialistNotes"]) == 2


def test_maps_baseline_contracts_from_health_tests() -> None:
    cs = collect_workspace(str(Path.cwd()))
    scope, _ = resolve_scope(cs)
    assert "health" in scope
    contracts = resolve_contracts(cs, ["health"])
    assert len(contracts) >= len(BASELINE_CONTRACTS)
    coverage, findings = map_coverage(cs, contracts)
    assert all(c["covered"] for c in coverage)
    assert [f for f in findings if f["severity"] == "error"] == []


def test_fails_when_scoped_graph_has_no_covering_test() -> None:
    cs: ChangeSet = {
        "label": "diff",
        "files": [
            {
                "path": "src/gssc_langgraph/graphs/orphan_bot/graph.py",
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
graph = builder.compile(name="Orphan Bot")
''',
            },
            {
                "path": "langgraph.json",
                "status": "modified",
                "content": json.dumps(
                    {
                        "graphs": {
                            "orphan_bot": (
                                "./src/gssc_langgraph/graphs/orphan_bot/"
                                "graph.py:graph"
                            ),
                        }
                    }
                ),
            },
        ],
    }
    result = run_analysis(cs)
    assert "orphan_bot" in result["scopeGraphIds"]
    assert any(f["check"] == "coverage_map" for f in result["findings"])
    assert verdict_from(result["findings"]) == "FAIL"
    assert any(p["action"] == "add_test" for p in result["plan"])


def test_fe_change_set_skips_no_graphs_warning() -> None:
    cs: ChangeSet = {
        "label": "gssc5-54",
        "files": [
            {
                "path": (
                    "gssc5-web/apps/public/src/app/modules/prompt-overlay/"
                    "button-field/button-field.html"
                ),
                "status": "modified",
                "content": '[class.border-gssc-dark-red]="invalid()"\n',
            },
            {
                "path": (
                    "gssc5-web/apps/public/src/app/modules/prompt-overlay/"
                    "button-field/button-field.test.ts"
                ),
                "status": "modified",
                "content": (
                    "expect(root.querySelector('.gssc-prompt-button-field')"
                    "!.classList.contains('border-gssc-dark-red')).toBe(true);\n"
                ),
            },
        ],
    }
    result = run_analysis(cs)
    assert result["scopeGraphIds"] == []
    assert not any(
        f["message"] == "No graphs in scope for test development"
        for f in result["findings"]
    )
    assert any(
        f["check"] == "scope" and f["severity"] == "info" for f in result["findings"]
    )
    assert any("ng test" in c for c in result["commands"])
    assert any(
        p["action"] in ("add_test", "update_test", "run_focused") for p in result["plan"]
    )
    assert not any(
        "graph.invoke" in (p.get("suggestedTest") or "") for p in result["plan"]
    )
    assert verdict_from(result["findings"]) == "PASS"


def test_be_change_set_prefers_bun_test_not_ng() -> None:
    cs: ChangeSet = {
        "label": "gssc5-55",
        "files": [
            {
                "path": "gssc5-web/apps/backend/src/kvs.ts",
                "status": "modified",
                "content": "export const kvs = {}\n",
            },
            {
                "path": "gssc5-web/apps/backend/src/kvs.test.ts",
                "status": "modified",
                "content": "test('kvs', () => { expect(1).toBe(1) })\n",
            },
            {
                "path": "gssc5-web/apps/backend/src/user/users.ts",
                "status": "modified",
                "content": "export const users = {}\n",
            },
        ],
    }
    result = run_analysis(cs)
    assert result["scopeGraphIds"] == []
    assert not any(
        f["message"] == "No graphs in scope for test development"
        for f in result["findings"]
    )
    assert any(
        f["check"] == "scope"
        and f["severity"] == "info"
        and "backend" in f["message"].lower()
        for f in result["findings"]
    )
    assert any("mise run //backend:test" in c for c in result["commands"])
    assert any(c.startswith("bun test ") for c in result["commands"])
    assert not any("ng test" in c for c in result["commands"])
    assert any(
        p["action"] in ("add_test", "update_test", "run_focused") for p in result["plan"]
    )
    assert not any(
        "Lexical" in (p.get("description") or "")
        or "Angular" in (p.get("description") or "")
        for p in result["plan"]
    )
    assert not any(
        "bunx ng" in (p.get("description") or "") for p in result["plan"]
    )
    assert verdict_from(result["findings"]) == "PASS"
