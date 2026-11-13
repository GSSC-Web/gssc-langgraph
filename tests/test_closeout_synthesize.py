"""closeout synthesis (model-optional)."""

from __future__ import annotations

import os

import pytest

from gssc_langgraph.closeout.synthesize import synthesize_closeout

KEY = "XAI_API_KEY"


@pytest.fixture(autouse=True)
def _restore_xai_key() -> None:
    saved = os.environ.get(KEY)
    yield
    if saved is None:
        os.environ.pop(KEY, None)
    else:
        os.environ[KEY] = saved


@pytest.mark.asyncio
async def test_skips_without_api_key() -> None:
    os.environ.pop(KEY, None)
    out = await synthesize_closeout(
        {
            "verdict": "PASS",
            "summary": "PASS — 0 findings",
            "findings": [],
        }
    )
    assert out["note"] == "skipped: no XAI_API_KEY"
    assert out["narrativeSummary"] == "PASS — 0 findings"
    assert out["proposedMemoryUpdates"] == []


@pytest.mark.asyncio
async def test_respects_enabled_false() -> None:
    os.environ[KEY] = "test-key-not-for-production"
    out = await synthesize_closeout(
        {
            "verdict": "FAIL",
            "summary": "FAIL — 1 finding",
            "findings": [],
            "enabled": False,
        }
    )
    assert out["note"] == "skipped: disabled"
    assert out["narrativeSummary"] == "FAIL — 1 finding"
