"""Work-surface detection + unified-diff helpers."""

from __future__ import annotations

from gssc_langgraph.work_surface import detect_work_surface, looks_like_unified_diff


def test_looks_like_unified_diff() -> None:
    assert looks_like_unified_diff(
        "diff --git a/a.ts b/a.ts\n--- a/a.ts\n+++ b/a.ts\n"
    )
    assert not looks_like_unified_diff("Summary of FE token swap")
    assert not looks_like_unified_diff("")


def test_detect_gssc5_fe_from_paths() -> None:
    surface = detect_work_surface(
        change_set={
            "label": "pr",
            "files": [
                {
                    "path": "gssc5-web/apps/public/src/app/modules/prompt-overlay/x.html",
                    "status": "modified",
                }
            ],
        }
    )
    assert surface == "gssc5_fe"


def test_detect_langgraph_from_paths() -> None:
    surface = detect_work_surface(
        change_set={
            "label": "pr",
            "files": [
                {
                    "path": "src/gssc_langgraph/graphs/health/graph.py",
                    "status": "modified",
                }
            ],
        }
    )
    assert surface == "langgraph"


def test_detect_fe_from_goal() -> None:
    assert (
        detect_work_surface("Fix Angular Prompt Overlay Tailwind failure tokens")
        == "gssc5_fe"
    )
