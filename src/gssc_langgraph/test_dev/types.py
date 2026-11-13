"""Shared types for the test_development workflow."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

TestDevVerdict = Literal["PASS", "FAIL"]
FindingSeverity = Literal["error", "warning", "info"]

TestDevCheckId = Literal[
    "scope",
    "coverage_map",
    "target",
    "asserts",
    "timing",
]

PlanAction = Literal[
    "add_test",
    "update_test",
    "add_assert",
    "run_focused",
    "ask_owner",
]

FileStatus = Literal["added", "modified", "deleted", "unchanged"]
ContractSource = Literal["baseline", "readme", "graph_docs", "inferred"]


class Finding(TypedDict):
    check: TestDevCheckId
    severity: FindingSeverity
    message: str
    path: NotRequired[str]
    graphId: NotRequired[str]
    contractId: NotRequired[str]
    fix: NotRequired[str]


class Contract(TypedDict):
    id: str
    graphId: str
    title: str
    requirement: str
    assertHints: list[str]
    source: ContractSource


class CoverageLink(TypedDict):
    contractId: str
    graphId: str
    covered: bool
    testPath: NotRequired[str]
    notes: NotRequired[str]


class PlanItem(TypedDict):
    action: PlanAction
    description: str
    graphId: NotRequired[str]
    contractId: NotRequired[str]
    path: NotRequired[str]
    suggestedTest: NotRequired[str]


class ChangedFile(TypedDict):
    path: str
    status: FileStatus
    content: NotRequired[str]
    patch: NotRequired[str]


class ChangeSet(TypedDict):
    label: str
    files: list[ChangedFile]
    diff: NotRequired[str]


class TestDevReport(TypedDict):
    verdict: TestDevVerdict
    summary: str
    findings: list[Finding]
    checksRun: list[TestDevCheckId]
    scopeGraphIds: list[str]
    contracts: list[Contract]
    coverage: list[CoverageLink]
    plan: list[PlanItem]
    commands: list[str]


class SpecialistNote(TypedDict, total=False):
    at: str
    verdict: TestDevVerdict
    summary: str
    label: str


class ProposedMemoryUpdate(TypedDict):
    memoryId: str
    summary: str
    rationale: NotRequired[str]


class TestDevSynthesis(TypedDict):
    narrativeSummary: str
    proposedMemoryUpdates: list[ProposedMemoryUpdate]
    note: str
