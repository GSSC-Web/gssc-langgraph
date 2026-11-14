"""GLG-52: ticket-scoped Agent Server Store handoff."""

from __future__ import annotations

import uuid

import pytest
from langgraph.store.memory import InMemoryStore

from gssc_langgraph.graphs.closeout_review.graph import builder as closeout_builder
from gssc_langgraph.graphs.software_dev.graph import builder as software_builder
from gssc_langgraph.graphs.test_development.graph import builder as test_dev_builder
from gssc_langgraph.ticket_store import (
    TICKET_ARTIFACT_SCHEMA_VERSION,
    get_ticket_artifact,
    join_key_from_mapping,
    put_ticket_artifact,
    ticket_namespace,
)


def test_join_key_prefers_kaneo_task_id() -> None:
    assert (
        join_key_from_mapping({"label": "L", "kaneoTaskId": "GLG-52"}) == "GLG-52"
    )
    assert join_key_from_mapping({"label": "GSSC5-65"}) == "GSSC5-65"
    assert join_key_from_mapping({}) is None


def test_put_get_roundtrip_inmemory() -> None:
    store = InMemoryStore()
    state = {
        "label": "GSSC5-65",
        "domains": ["backend"],
        "plan": [{"id": "tests", "title": "Add bun test", "domain": "backend"}],
        "verdict": "PASS",
        "findings": [{"code": "check.scope", "severity": "info", "message": "ok"}],
    }
    put = put_ticket_artifact(store, state, updated_by="SoftDev")
    assert put is not None
    assert put["schemaVersion"] == TICKET_ARTIFACT_SCHEMA_VERSION
    assert put["softDevVerdict"] == "PASS"
    got = get_ticket_artifact(store, {"label": "GSSC5-65"})
    assert got is not None
    assert got["plan"][0]["id"] == "tests"
    assert store.get(ticket_namespace(), "GSSC5-65") is not None


def test_opt_out_skips_store() -> None:
    store = InMemoryStore()
    assert (
        put_ticket_artifact(
            store,
            {"label": "x", "storeHandoff": False, "verdict": "PASS"},
            updated_by="SoftDev",
        )
        is None
    )


@pytest.mark.asyncio
async def test_softdev_testdev_closeout_store_handoff() -> None:
    store = InMemoryStore()
    soft = software_builder.compile(name="SoftDev store test", store=store)
    test_dev = test_dev_builder.compile(name="TestDev store test", store=store)
    closeout = closeout_builder.compile(name="Closeout store test", store=store)
    label = f"handoff-{uuid.uuid4().hex[:8]}"
    cfg = {
        "configurable": {
            "thread_id": f"store-{uuid.uuid4()}",
            "gssc5Enabled": False,
            "synthesisEnabled": False,
            "ticketWorkspace": "test-ws",
        }
    }

    soft_out = await soft.ainvoke(
        {
            "goal": "Harden Elysia login session cookies",
            "label": label,
            "domainHint": "backend",
        },
        cfg,
    )
    assert soft_out["verdict"] in ("PASS", "FAIL")
    assert soft_out.get("ticketHandoff", {}).get("softDevVerdict")
    assert soft_out["ticketHandoff"]["plan"]

    artifact = get_ticket_artifact(
        store,
        {"label": label},
        configurable={"ticketWorkspace": "test-ws"},
    )
    assert artifact is not None
    assert artifact["updatedBy"] == "SoftDev"

    td_out = await test_dev.ainvoke(
        {
            "label": label,
            "goal": "UID PLLR-99: straddling needle boundary",
            "domainHint": "backend",
            "changeSet": {
                "label": label,
                "files": [
                    {
                        "path": "apps/backend/src/accounts.ts",
                        "status": "modified",
                    },
                    {
                        "path": "apps/backend/src/accounts.test.ts",
                        "status": "modified",
                        "content": "test('cookie', () => { expect(1).toBe(1) })",
                    },
                ],
            },
        },
        {
            "configurable": {
                **cfg["configurable"],
                "thread_id": f"store-td-{uuid.uuid4()}",
            }
        },
    )
    assert td_out.get("ticketHandoff", {}).get("testDevVerdict")
    assert "backend" in td_out["domains"]
    # SoftDev plan survived merge
    assert td_out["ticketHandoff"].get("softDevVerdict")
    assert td_out["ticketHandoff"].get("plan")

    co_out = await closeout.ainvoke(
        {
            "label": label,
            "kaneoTaskId": label,
            "changeSet": {
                "label": label,
                "files": [
                    {"path": "apps/backend/src/accounts.ts", "status": "modified"},
                ],
                "diff": (
                    "diff --git a/apps/backend/src/accounts.ts "
                    "b/apps/backend/src/accounts.ts\n"
                    "--- a/apps/backend/src/accounts.ts\n"
                    "+++ b/apps/backend/src/accounts.ts\n"
                    "+export const x = 1\n"
                ),
            },
        },
        {
            "configurable": {
                **cfg["configurable"],
                "thread_id": f"store-co-{uuid.uuid4()}",
            }
        },
    )
    assert "load_ticket_handoff" in co_out["steps"]
    assert co_out.get("ticketHandoff")
    assert co_out["response"]["payload"].get("ticketHandoff", {}).get("plan")
    assert any(
        f.get("code") == "handoff.prior_findings"
        for f in co_out.get("findings") or []
    ) or co_out["ticketHandoff"].get("softDevVerdict")
