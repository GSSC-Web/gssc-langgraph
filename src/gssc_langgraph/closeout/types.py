"""Shared types for the closeout_review workflow."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

CloseoutVerdict = Literal["PASS", "FAIL", "ERROR"]
FindingSeverity = Literal["error", "warning", "info"]

CloseoutCheckId = Literal[
    "scope",
    "contracts",
    "software_trace",
    "software_match",
    "software_quality",
    "third_party",
    "test_coverage",
    "test_target",
    "secrets",
]

FileStatus = Literal["added", "modified", "deleted", "unchanged"]


class CloseoutFinding(TypedDict):
    check: CloseoutCheckId
    severity: FindingSeverity
    message: str
    path: NotRequired[str]
    uid: NotRequired[str]
    fix: NotRequired[str]
    code: NotRequired[str]


class ChangedFile(TypedDict):
    path: str
    status: FileStatus
    content: NotRequired[str]
    patch: NotRequired[str]


class ChangeSet(TypedDict):
    label: str
    files: list[ChangedFile]
    diff: NotRequired[str]


class CloseoutReport(TypedDict):
    verdict: CloseoutVerdict
    summary: str
    findings: list[CloseoutFinding]
    checksRun: list[CloseoutCheckId]


class CloseoutInputScope(TypedDict, total=False):
    """How the caller scoped this closeout turn."""

    kaneoTaskId: str
    prScope: str
    uids: list[str]


class ProposedMemoryUpdate(TypedDict):
    memoryId: str
    summary: str
    rationale: NotRequired[str]


class CloseoutSynthesis(TypedDict):
    narrativeSummary: str
    proposedMemoryUpdates: list[ProposedMemoryUpdate]
    note: str


class ReviewMemoryNote(TypedDict, total=False):
    at: str
    verdict: CloseoutVerdict
    summary: str
    label: str
