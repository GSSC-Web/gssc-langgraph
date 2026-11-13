"""
Test-development criteria for gssc-langgraph.

Behavioral reference: gssc5 test agent and test-closeout-review skill.
Adapted for a Python LangGraph Agent Server with pytest.
"""

from __future__ import annotations

from dataclasses import dataclass

from gssc_langgraph.test_dev.types import TestDevCheckId


@dataclass(frozen=True)
class Criterion:
    id: TestDevCheckId
    title: str
    description: str


CRITERIA: list[Criterion] = [
    Criterion(
        id="scope",
        title="Scope",
        description=(
            "Identify in-scope graphs and their documented contracts for this "
            "change set or workspace."
        ),
    ),
    Criterion(
        id="coverage_map",
        title="Coverage map",
        description=(
            "Exactly one permanent pytest (or focused test module) should lock "
            "each in-scope contract — no silent gaps."
        ),
    ),
    Criterion(
        id="target",
        title="Target",
        description=(
            "Tests validate the documented contract (README / graph docs / "
            "baseline API), not “whatever the software currently does.”"
        ),
    ),
    Criterion(
        id="asserts",
        title="Asserts",
        description=(
            "Assert status/behavior named by the contract; avoid empty or "
            "tautological asserts; body/contents only when the contract names them."
        ),
    ),
    Criterion(
        id="timing",
        title="Timing",
        description=(
            "Prefer focused harness runs (`pytest <file>` / "
            "`uv run pytest <file>`); avoid redundant suite weight and slow "
            "integration where unit invoke suffices."
        ),
    ),
]

CONFLICT_GUIDANCE = (
    "If the test is wrong, fix the test. If software and the documented "
    "contract conflict, ask the owner before changing either."
)
