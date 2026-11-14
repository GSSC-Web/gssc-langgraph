"""v2 GraphResponse envelope (GLG-35…46)."""

from __future__ import annotations

import uuid

import pytest

from gssc_langgraph.envelope import (
    TARGET_RESPONSE_BYTES,
    apply_response_budgets,
    build_graph_response,
    pin_domains,
)
from gssc_langgraph.envelope.budgets import utf8_size
from gssc_langgraph.graphs.closeout_review.graph import graph as closeout_graph
from gssc_langgraph.graphs.conversation.graph import graph as conversation_graph
from gssc_langgraph.graphs.health.graph import graph as health_graph
from gssc_langgraph.graphs.software_dev.graph import graph as software_graph
from gssc_langgraph.graphs.test_development.graph import graph as test_dev_graph
from gssc_langgraph.software.plan import build_plan


def test_pin_domains_be_paths() -> None:
    domains = pin_domains(
        change_set={
            "label": "be",
            "files": [
                {"path": "gssc5-web/apps/backend/src/login-session.ts", "status": "modified"}
            ],
        }
    )
    assert domains == ["backend"]


def test_pin_domains_mixed() -> None:
    domains = pin_domains(
        change_set={
            "label": "mixed",
            "files": [
                {"path": "apps/backend/src/accounts.ts", "status": "modified"},
                {"path": "apps/public/src/app/header.ts", "status": "modified"},
            ],
        }
    )
    assert "backend" in domains
    assert any(d.endswith("-fe") for d in domains)


def test_pin_domains_honors_hint() -> None:
    assert pin_domains(domain_hint="backend") == ["backend"]
    assert pin_domains(domain_hint=["public-fe", "backend"])[0] in (
        "backend",
        "public-fe",
    )


def test_softdev_plan_steps_have_domain_tags() -> None:
    plan = build_plan(
        "fix backend cookie helpers",
        {
            "label": "be",
            "files": [
                {
                    "path": "apps/backend/src/accounts.ts",
                    "status": "modified",
                }
            ],
        },
    )
    assert plan
    assert all(step.get("domain") for step in plan)
    assert all(step.get("kind") for step in plan)
    test_step = next(s for s in plan if s["id"] == "tests")
    assert "bun test" in (test_step.get("commands") or [])


def test_health_emits_v2_envelope() -> None:
    result = health_graph.invoke({})
    assert result["status"] == "ok"
    resp = result["response"]
    assert resp["schemaVersion"] == "2"
    assert resp["tool"] == "GSSC_Health"
    assert resp["verdict"] == "PASS"
    assert resp["digest"]["chatOneLiner"]
    assert resp["payload"]["service"] == "gssc-langgraph"


def test_conversation_emits_v2_envelope() -> None:
    result = conversation_graph.invoke({"message": "ping"})
    assert "ping" in result["reply"]
    resp = result["response"]
    assert resp["schemaVersion"] == "2"
    assert resp["verdict"] == "PASS"
    assert resp["payload"]["reply"] == result["reply"]


@pytest.mark.asyncio
async def test_softdev_response_envelope_and_domains() -> None:
    result = await software_graph.ainvoke(
        {
            "goal": "Update Elysia login session cookies",
            "label": "GSSC5-60",
            "changeSet": {
                "label": "GSSC5-60",
                "files": [
                    {
                        "path": "apps/backend/src/login-session.ts",
                        "status": "modified",
                    }
                ],
            },
        },
        {
            "configurable": {
                "thread_id": f"env-sd-{uuid.uuid4()}",
                "gssc5Enabled": False,
                "synthesisEnabled": False,
            }
        },
    )
    resp = result["response"]
    assert resp["schemaVersion"] == "2"
    assert resp["tool"] == "GSSC_Software_Dev"
    assert resp["verdict"] in ("PASS", "FAIL", "ERROR")
    assert "backend" in resp["domains"]
    assert resp["digest"]["chatOneLiner"]
    assert resp["friction"]["fileOnKaneo"] in (True, False)
    assert resp["payload"]["plan"]
    assert all("domain" in step for step in resp["payload"]["plan"])


@pytest.mark.asyncio
async def test_softdev_error_without_goal_or_changeset() -> None:
    result = await software_graph.ainvoke(
        {},
        {
            "configurable": {
                "thread_id": f"env-sd-err-{uuid.uuid4()}",
                "gssc5Enabled": False,
                "synthesisEnabled": False,
            }
        },
    )
    assert result["verdict"] == "ERROR"
    assert result["response"]["verdict"] == "ERROR"


@pytest.mark.asyncio
async def test_testdev_emits_test_cases_and_boundary_gap() -> None:
    result = await test_dev_graph.ainvoke(
        {
            "label": "GSSC5-65",
            "requirements": (
                "UID PLLR-99: add straddling needle boundary negative for o\\nW "
                "cross-field case"
            ),
            "changeSet": {
                "label": "GSSC5-65",
                "files": [
                    {
                        "path": "apps/backend/src/accounts.ts",
                        "status": "modified",
                    },
                    {
                        "path": "apps/backend/src/accounts.test.ts",
                        "status": "modified",
                        "content": (
                            "test('accounts cookie', () => { "
                            "expect(readCookie('sid')).toBeTruthy() })"
                        ),
                    },
                ],
            },
        },
        {
            "configurable": {
                "thread_id": f"env-td-{uuid.uuid4()}",
                "gssc5Enabled": False,
                "synthesisEnabled": False,
            }
        },
    )
    resp = result["response"]
    assert resp["schemaVersion"] == "2"
    cases = resp["payload"]["testCases"]
    gaps = resp["payload"]["gaps"]
    assert any("boundary" in c["id"] or "Boundary" in c["title"] for c in cases)
    assert gaps
    assert resp["verdict"] == "FAIL"


@pytest.mark.asyncio
async def test_closeout_lean_paths_can_pass() -> None:
    result = await closeout_graph.ainvoke(
        {
            "label": "lean",
            "changeSet": {
                "label": "lean",
                "files": [
                    {"path": "README.md", "status": "modified"},
                ],
                "diff": (
                    "diff --git a/README.md b/README.md\n"
                    "--- a/README.md\n"
                    "+++ b/README.md\n"
                    "+note\n"
                ),
            },
        },
        {
            "configurable": {
                "thread_id": f"env-co-{uuid.uuid4()}",
                "gssc5Enabled": False,
                "synthesisEnabled": False,
            }
        },
    )
    assert result["response"]["schemaVersion"] == "2"
    assert result["verdict"] in ("PASS", "FAIL")
    assert "changeset.required" not in [
        f.get("code") for f in result["response"]["findings"]
    ]


def test_truncation_preserves_verdict_and_summary() -> None:
    huge = "x" * 5000
    response = build_graph_response(
        tool="GSSC_Closeout_Review",
        verdict="FAIL",
        summary="keep-me-summary",
        findings=[
            {"code": "check.x", "severity": "error", "message": huge}
            for _ in range(40)
        ],
        domains=["backend"],
        payload={
            "narrativeSummary": huge * 10,
            "synthesisNote": huge * 10,
            "gssc5ContextText": huge * 10,
            "plan": [{"id": "1", "title": "t"}],
        },
        label="truncate-me",
    )
    assert response["verdict"] == "FAIL"
    assert "keep-me-summary" in response["summary"]
    assert bool(response.get("truncated"))
    assert utf8_size(response) <= 48 * 1024
    assert TARGET_RESPONSE_BYTES > 0
    assert callable(apply_response_budgets)
