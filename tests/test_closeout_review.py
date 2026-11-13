"""closeout_review graph + deterministic checks."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from gssc_langgraph.checkpoint import compile_with_memory, thread_config
from gssc_langgraph.closeout.checks import (
    check_contracts,
    check_scope,
    check_secrets,
    check_software_match,
    check_software_trace,
    check_third_party,
    verdict_from,
)
from gssc_langgraph.closeout.criteria import BASELINE_ASSISTANT_IDS
from gssc_langgraph.closeout.types import ChangeSet
from gssc_langgraph.graphs.closeout_review.graph import builder as closeout_builder
from gssc_langgraph.graphs.closeout_review.graph import graph as closeout_graph
from gssc_langgraph.gssc5 import ARCH_MEMORY_IDS, CLOSEOUT_PEER_SKILL_IDS
from gssc_langgraph.review.collect import collect_workspace

FIXTURE_ROOT = str(Path(__file__).resolve().parent / "fixtures" / "gssc5")

MINIMAL_FILES = {
    "langgraph.json": json.dumps(
        {
            "graphs": {
                "health": "./src/gssc_langgraph/graphs/health/graph.py:graph",
            }
        }
    ),
    "src/gssc_langgraph/graphs/health/graph.py": '''
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
''',
}


def test_closeout_graph_is_compiled() -> None:
    assert closeout_graph is not None
    assert closeout_graph.name == "GSSC Closeout Review"


def test_baseline_contract_is_health_only() -> None:
    assert list(BASELINE_ASSISTANT_IDS) == ["health"]
    assert "sample_agent" not in BASELINE_ASSISTANT_IDS


@pytest.mark.asyncio
async def test_loads_gssc5_reviewer_context_and_returns_verdict() -> None:
    result = await closeout_graph.ainvoke(
        {
            "label": "minimal-closeout",
            "kaneoTaskId": "KANEO-1",
            "prScope": "origin/master...HEAD",
            "uids": ["health"],
            "files": MINIMAL_FILES,
        },
        {
            "configurable": {
                "thread_id": f"closeout-gssc5-{uuid.uuid4()}",
                "gssc5Root": FIXTURE_ROOT,
            }
        },
    )

    assert "load_gssc5_context" in result["steps"]
    assert "verdict" in result["steps"]
    assert "synthesize" in result["steps"]
    assert result["verdict"] in ("PASS", "FAIL")
    assert result["gssc5Root"] == FIXTURE_ROOT
    assert result["gssc5Context"]
    for skill_id in CLOSEOUT_PEER_SKILL_IDS:
        assert any(s["id"] == skill_id for s in result["gssc5Context"]["skills"])
    for mem_id in ARCH_MEMORY_IDS:
        assert any(m["id"] == mem_id for m in result["gssc5Context"]["memories"])
    assert "## Skill: software-closeout-review" in result["gssc5ContextText"]
    assert result["synthesisNote"].startswith(("ok", "skipped:", "error:"))
    assert isinstance(result["narrativeSummary"], str)


@pytest.mark.asyncio
async def test_missing_gssc5_checkout_still_returns_verdict() -> None:
    result = await closeout_graph.ainvoke(
        {
            "label": "missing-gssc5",
            "files": MINIMAL_FILES,
        },
        {
            "configurable": {
                "thread_id": f"closeout-missing-{uuid.uuid4()}",
                "gssc5Root": "/tmp/missing-gssc5-closeout-xyz",
                "gssc5Enabled": True,
            }
        },
    )
    assert result["verdict"] in ("PASS", "FAIL")
    assert "load_gssc5_context" in result["steps"]


@pytest.mark.asyncio
async def test_gssc5_disabled_yields_empty_context() -> None:
    result = await closeout_graph.ainvoke(
        {
            "label": "disabled-gssc5",
            "files": MINIMAL_FILES,
        },
        {
            "configurable": {
                "thread_id": f"closeout-disabled-{uuid.uuid4()}",
                "gssc5Enabled": False,
            }
        },
    )
    assert result["verdict"] in ("PASS", "FAIL")
    assert result["gssc5Context"]["note"] == "disabled"
    assert result["gssc5Context"]["skills"] == []
    assert result["synthesisNote"].startswith(("skipped:", "ok", "error:"))


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
    result = await closeout_graph.ainvoke(
        {
            "label": cs["label"],
            "changeSet": cs,
            "files": {
                f["path"]: f["content"]
                for f in cs["files"]
                if f.get("content") is not None
            },
        },
        thread_config(f"closeout-workspace-{uuid.uuid4()}"),
    )
    assert result["verdict"] == "PASS"
    assert "scope" in result["checksRun"]
    assert "contracts" in result["checksRun"]
    assert "secrets" in result["checksRun"]
    assert "verdict" in result["steps"]
    assert "load_gssc5_context" in result["steps"]
    assert "synthesize" in result["steps"]
    assert len(result["reviewMemory"]) == 1
    assert result["reviewMemory"][0]["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_appends_review_memory_across_thread_turns() -> None:
    # Multi-turn note accumulation needs a checkpointer; Agent Server export
    # has none — compile the builder with MemorySaver for this unit test.
    graph = compile_with_memory(
        closeout_builder, {"name": "GSSC Closeout Review (test memory)"}
    )
    config = thread_config(f"closeout-mem-{uuid.uuid4()}")
    inp = {"label": "empty-scope", "files": {}}
    first = await graph.ainvoke(inp, config)
    assert len(first["reviewMemory"]) == 1
    second = await graph.ainvoke(inp, config)
    assert len(second["reviewMemory"]) == 2
    assert all(n["summary"] for n in second["reviewMemory"])


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
    findings = [*check_software_trace(cs), *check_software_match(cs)]
    assert any(f["check"] == "software_trace" for f in findings)
    assert verdict_from(findings) == "FAIL"


def test_does_not_require_sample_agent_in_contracts() -> None:
    findings = check_contracts(
        {
            "label": "diff",
            "files": [
                {
                    "path": "langgraph.json",
                    "status": "modified",
                    "content": json.dumps(
                        {
                            "graphs": {
                                "health": (
                                    "./src/gssc_langgraph/graphs/health/"
                                    "graph.py:graph"
                                ),
                                "closeout_review": (
                                    "./src/gssc_langgraph/graphs/closeout_review/"
                                    "graph.py:graph"
                                ),
                            }
                        }
                    ),
                    "patch": (
                        '-  "sample_agent": '
                        '"./src/graphs/sample_agent/graph.ts:graph",\n'
                    ),
                }
            ],
        }
    )
    assert not any(
        f.get("uid") == "sample_agent" or "sample_agent" in f["message"]
        for f in findings
    )
    assert verdict_from(findings) == "PASS"


def test_fails_when_baseline_health_removed() -> None:
    findings = check_contracts(
        {
            "label": "diff",
            "files": [
                {
                    "path": "langgraph.json",
                    "status": "modified",
                    "content": json.dumps(
                        {
                            "graphs": {
                                "closeout_review": (
                                    "./src/gssc_langgraph/graphs/closeout_review/"
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
        f["check"] == "contracts" and "health" in f["message"] for f in findings
    )
    assert verdict_from(findings) == "FAIL"


def test_fails_on_bun_only_packaging() -> None:
    """Python+uv is required; Bun-only package.json is an error."""
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


def test_fails_when_pyproject_missing_langgraph() -> None:
    findings = check_third_party(
        {
            "label": "diff",
            "files": [
                {
                    "path": "pyproject.toml",
                    "status": "added",
                    "content": "[project]\nname='x'\n",
                }
            ],
        }
    )
    assert any(f["severity"] == "error" for f in findings)


def test_fails_on_committed_secret_looking_keys() -> None:
    # Assemble at runtime so this test file itself does not trip workspace secrets.
    fake_key = "".join(["sk", "-", "abcdefghijklmnopqrstuvwxyz012345"])
    findings = check_secrets(
        {
            "label": "diff",
            "files": [
                {
                    "path": "src/oops.py",
                    "status": "added",
                    "content": f'k = "{fake_key}"\n',
                }
            ],
        }
    )
    assert any(f["check"] == "secrets" for f in findings)


def test_scope_errors_when_empty() -> None:
    findings = check_scope(None)
    assert verdict_from(findings) == "FAIL"


def test_scope_soft_warns_on_prose_diff_without_files() -> None:
    findings = check_scope(
        {
            "label": "prose",
            "files": [],
            "diff": (
                "Summary: swapped Prompt Overlay invalid chrome to gssc "
                "failure tokens across six fields."
            ),
        }
    )
    assert verdict_from(findings) == "PASS"
    assert any(
        f["check"] == "scope"
        and f["severity"] == "warning"
        and "Prose/summary" in f["message"]
        for f in findings
    )
    assert any(f.get("fix") and "diff --git" in f["fix"] for f in findings)


@pytest.mark.asyncio
async def test_graph_soft_pass_on_prose_diff() -> None:
    result = await closeout_graph.ainvoke(
        {
            "label": "gssc5-54-prose",
            "diff": "Changed text-field invalid classes to border-gssc-dark-red.",
        },
        {
            "configurable": {
                "thread_id": f"closeout-prose-{uuid.uuid4()}",
                "gssc5Enabled": False,
                "synthesisEnabled": False,
            }
        },
    )
    assert result["verdict"] == "PASS"
    assert any(
        f["check"] == "scope" and f["severity"] == "warning" for f in result["findings"]
    )
