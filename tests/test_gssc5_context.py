"""gssc5 root resolution, checkout, catalog, relevance, graph wiring."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

from gssc_langgraph.graphs.closeout_review.graph import graph as closeout_graph
from gssc_langgraph.graphs.software_dev.graph import graph as software_graph
from gssc_langgraph.graphs.test_development.graph import graph as test_dev_graph
from gssc_langgraph.gssc5 import (
    ARCH_MEMORY_IDS,
    CLOSEOUT_PEER_SKILL_IDS,
    ROLE_PRESETS,
    checkout_gssc5_to_cache,
    create_load_gssc5_context_node,
    ensure_gssc5_checkout,
    format_gssc5_context,
    is_gssc5_root,
    list_memories,
    list_skills,
    load_gssc5_context,
    load_gssc5_context_for_role,
    looks_like_git_url,
    parse_frontmatter,
    resolve_gssc5_root,
    select_and_load,
    tokenize,
)

FIXTURE_ROOT = str(Path(__file__).resolve().parent / "fixtures" / "gssc5")

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


def test_detects_fixture_as_gssc5_root() -> None:
    assert is_gssc5_root(FIXTURE_ROOT) is True


def test_resolve_gssc5_root_honors_override() -> None:
    assert resolve_gssc5_root(FIXTURE_ROOT) == FIXTURE_ROOT


def test_resolve_gssc5_root_returns_empty_for_nonsense() -> None:
    prev = os.environ.get("GSSC5_ROOT")
    os.environ.pop("GSSC5_ROOT", None)
    try:
        assert resolve_gssc5_root("/tmp/does-not-exist-gssc5-xyz") == ""
    finally:
        if prev is not None:
            os.environ["GSSC5_ROOT"] = prev


def test_gssc5_root_must_be_path_not_url() -> None:
    assert looks_like_git_url("https://github.com/GSSC-Web/gssc5.git") is True
    assert looks_like_git_url("/abs/path/to/gssc5") is False
    assert resolve_gssc5_root("https://github.com/GSSC-Web/gssc5.git") == ""


def test_ensure_gssc5_checkout_rejects_url_in_root_override() -> None:
    result = ensure_gssc5_checkout(
        {
            "root": "https://github.com/GSSC-Web/gssc5.git",
            "autoCheckout": False,
        }
    )
    assert result["root"] == ""
    assert "filesystem path" in result["note"]
    assert "GSSC5_REPO_URL" in result["note"]


def test_clones_into_cache_when_no_local_root_mock_git() -> None:
    cache_dir = tempfile.mkdtemp(prefix="gssc5-cache-")

    def git(args: list[str], **_kwargs: Any) -> dict[str, Any]:
        if args[0] == "clone":
            target = args[-1]
            Path(target).mkdir(parents=True, exist_ok=True)
            shutil.copytree(FIXTURE_ROOT, target, dirs_exist_ok=True)
            git_dir = Path(target) / ".git"
            git_dir.mkdir(parents=True, exist_ok=True)
            (git_dir / "HEAD").write_text(
                "ref: refs/heads/master\n", encoding="utf-8"
            )
            return {"status": 0, "stdout": "", "stderr": ""}
        if args[0] == "rev-parse":
            return {"status": 0, "stdout": "true\n", "stderr": ""}
        return {"status": 0, "stdout": "", "stderr": ""}

    prev_root = os.environ.get("GSSC5_ROOT")
    os.environ.pop("GSSC5_ROOT", None)
    try:
        result = ensure_gssc5_checkout(
            {
                "cacheDir": cache_dir,
                "autoCheckout": True,
                "git": git,
                "cwd": cache_dir,
            }
        )
        assert result["source"] == "cache"
        assert result["root"] == str(Path(cache_dir) / "gssc5")
        assert is_gssc5_root(result["root"]) is True
        assert (Path(result["root"]) / ".agents" / "skills").exists()
    finally:
        if prev_root is not None:
            os.environ["GSSC5_ROOT"] = prev_root
        shutil.rmtree(cache_dir, ignore_errors=True)


def test_updates_existing_cache_checkout_mock_fetch() -> None:
    cache_dir = tempfile.mkdtemp(prefix="gssc5-cache-upd-")
    target = Path(cache_dir) / "gssc5"
    shutil.copytree(FIXTURE_ROOT, target)
    git_dir = target / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/master\n", encoding="utf-8")

    calls: list[list[str]] = []

    def git(args: list[str], **_kwargs: Any) -> dict[str, Any]:
        calls.append(list(args))
        if args[0] == "rev-parse":
            return {"status": 0, "stdout": "true\n", "stderr": ""}
        return {"status": 0, "stdout": "", "stderr": ""}

    result = checkout_gssc5_to_cache(
        {
            "cacheDir": cache_dir,
            "git": git,
            "cwd": cache_dir,
        }
    )
    assert result["root"] == str(target)
    assert result["source"] == "cache"
    assert any(c[0] == "fetch" for c in calls)
    shutil.rmtree(cache_dir, ignore_errors=True)


def test_parses_folded_description() -> None:
    raw = """---
id: sample
description: >-
  Line one
  line two
enabled: true
---

# Body
"""
    parsed = parse_frontmatter(raw)
    assert parsed["meta"]["id"] == "sample"
    assert "Line one" in str(parsed["meta"]["description"])
    assert parsed["body"].strip() == "# Body"


def test_lists_fixture_skills_and_memories() -> None:
    skills = list_skills(FIXTURE_ROOT)
    memories = list_memories(FIXTURE_ROOT)
    skill_ids = [s["id"] for s in skills]
    memory_ids = [m["id"] for m in memories]
    assert "software-closeout-review" in skill_ids
    assert "test-closeout-review" in skill_ids
    assert "requirements-closeout-review" in skill_ids
    assert "kaneo-create-task" in skill_ids
    assert "backend-arch" in memory_ids
    assert "public-arch" in memory_ids
    assert "members-arch" in memory_ids


def test_reviewer_preset_prefers_closeout_skills_and_arch_memories() -> None:
    assert ROLE_PRESETS["reviewer"]["preferSkills"] == list(CLOSEOUT_PEER_SKILL_IDS)
    assert ROLE_PRESETS["reviewer"]["preferMemories"] == list(ARCH_MEMORY_IDS)


def test_temp_gssc5_root_fixture_reviewer_preset() -> None:
    temp_root = tempfile.mkdtemp(prefix="gssc5-root-reviewer-")
    shutil.copytree(FIXTURE_ROOT, temp_root, dirs_exist_ok=True)
    prev_root = os.environ.get("GSSC5_ROOT")
    os.environ["GSSC5_ROOT"] = temp_root
    try:
        assert is_gssc5_root(temp_root) is True
        bundle = load_gssc5_context_for_role(
            "reviewer",
            {
                "query": "closeout review requirements software test",
                "requireSkills": list(CLOSEOUT_PEER_SKILL_IDS),
                "requireMemories": list(ARCH_MEMORY_IDS),
                "maxSkills": 3,
                "maxMemories": 3,
                "autoCheckout": False,
            },
        )
        assert bundle["root"] == temp_root
        assert "not found" not in bundle["note"].lower()
        for skill_id in CLOSEOUT_PEER_SKILL_IDS:
            assert any(s["id"] == skill_id for s in bundle["skills"])
        for mem_id in ARCH_MEMORY_IDS:
            assert any(m["id"] == mem_id for m in bundle["memories"])
        assert "## Skill: requirements-closeout-review" in format_gssc5_context(
            bundle
        )
    finally:
        if prev_root is not None:
            os.environ["GSSC5_ROOT"] = prev_root
        else:
            os.environ.pop("GSSC5_ROOT", None)
        shutil.rmtree(temp_root, ignore_errors=True)


def test_tokenize_drops_stopwords() -> None:
    assert tokenize("the software closeout for backend") == [
        "software",
        "closeout",
        "backend",
    ]


def test_software_query_prefers_software_closeout_and_backend_memory() -> None:
    selected = select_and_load(
        FIXTURE_ROOT,
        {
            "query": "software closeout for backend elysia prisma",
            "preferSkills": ["software-closeout-review"],
            "preferMemories": ["backend-arch"],
            "maxSkills": 2,
            "maxMemories": 1,
        },
    )
    assert selected["skills"][0]["id"] == "software-closeout-review"
    assert selected["memories"][0]["id"] == "backend-arch"
    assert any(s["id"] == "software-closeout-review" for s in selected["selected"])
    assert "Software closeout review" in selected["skills"][0]["body"]


def test_kaneo_defect_query_ranks_kaneo_create_task() -> None:
    selected = select_and_load(
        FIXTURE_ROOT,
        {
            "query": "create kaneo defect ticket for weekly scan",
            "maxSkills": 1,
            "maxMemories": 0,
        },
    )
    assert selected["skills"][0]["id"] == "kaneo-create-task"


def test_require_skills_hard_includes_even_with_weak_query() -> None:
    selected = select_and_load(
        FIXTURE_ROOT,
        {
            "query": "zzz",
            "requireSkills": ["test-closeout-review"],
            "maxSkills": 1,
            "maxMemories": 0,
            "minScore": 50,
        },
    )
    assert [s["id"] for s in selected["skills"]] == ["test-closeout-review"]


def test_load_gssc5_context_for_role_software_requires_closeout_skill() -> None:
    bundle = load_gssc5_context_for_role(
        "software",
        {
            "root": FIXTURE_ROOT,
            "query": "implement LLR in backend",
        },
    )
    assert bundle["root"] == FIXTURE_ROOT
    assert any(s["id"] == "software-closeout-review" for s in bundle["skills"])
    assert "## Skill: software-closeout-review" in format_gssc5_context(bundle)


def test_missing_root_yields_empty_bundle_note() -> None:
    bundle = load_gssc5_context(
        {
            "root": "/tmp/missing-gssc5-root",
            "query": "anything",
            "autoCheckout": False,
        }
    )
    assert bundle["skills"] == []
    assert "not found" in bundle["note"]


def test_create_load_gssc5_context_node_writes_context_fields() -> None:
    node = create_load_gssc5_context_node(
        {
            "role": "general",
            "queryField": "message",
        }
    )
    out = node(
        {"message": "backend elysia software closeout"},
        {"configurable": {"gssc5Root": FIXTURE_ROOT}},
    )
    assert out["gssc5Root"] == FIXTURE_ROOT
    assert len(out["gssc5Context"]["skills"]) > 0
    assert out["steps"] == ["load_gssc5_context"]


@pytest.mark.asyncio
async def test_software_dev_includes_load_gssc5_context_step() -> None:
    result = await software_graph.ainvoke(
        {"goal": "Add backend membership graph with elysia"},
        {
            "configurable": {
                "thread_id": f"gssc5-software-{uuid.uuid4()}",
                "gssc5Root": FIXTURE_ROOT,
            }
        },
    )
    assert "load_gssc5_context" in result["steps"]
    assert any(
        s["id"] == "software-closeout-review"
        for s in (result.get("gssc5Context") or {}).get("skills", [])
    )
    assert result["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_test_development_includes_load_gssc5_context_step() -> None:
    result = await test_dev_graph.ainvoke(
        {
            "label": "test closeout",
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
        {
            "configurable": {
                "thread_id": f"gssc5-test-dev-{uuid.uuid4()}",
                "gssc5Root": FIXTURE_ROOT,
            }
        },
    )
    assert "load_gssc5_context" in result["steps"]
    assert any(
        s["id"] == "test-closeout-review"
        for s in (result.get("gssc5Context") or {}).get("skills", [])
    )


@pytest.mark.asyncio
async def test_closeout_review_includes_load_gssc5_context_with_reviewer_requires() -> (
    None
):
    result = await closeout_graph.ainvoke(
        {
            "label": "closeout gssc5",
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
            },
        },
        {
            "configurable": {
                "thread_id": f"gssc5-closeout-{uuid.uuid4()}",
                "gssc5Root": FIXTURE_ROOT,
            }
        },
    )
    assert "load_gssc5_context" in result["steps"]
    assert result["verdict"] in ("PASS", "FAIL")
    for skill_id in CLOSEOUT_PEER_SKILL_IDS:
        assert any(
            s["id"] == skill_id
            for s in (result.get("gssc5Context") or {}).get("skills", [])
        )
    for mem_id in ARCH_MEMORY_IDS:
        assert any(
            m["id"] == mem_id
            for m in (result.get("gssc5Context") or {}).get("memories", [])
        )
