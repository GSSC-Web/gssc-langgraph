"""Shared types for the software_dev workflow."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

SoftwareVerdict = Literal["PASS", "FAIL"]
FindingSeverity = Literal["error", "warning", "info"]

SoftwareCheckId = Literal[
    "scope",
    "trace",
    "match",
    "quality",
    "third_party",
    "discipline",
]

FileStatus = Literal["added", "modified", "deleted", "unchanged"]


class SoftwareFinding(TypedDict):
    check: SoftwareCheckId
    severity: FindingSeverity
    message: str
    path: NotRequired[str]
    uid: NotRequired[str]
    fix: NotRequired[str]


class ChangedFile(TypedDict):
    path: str
    status: FileStatus
    content: NotRequired[str]
    patch: NotRequired[str]


class ChangeSet(TypedDict):
    label: str
    files: list[ChangedFile]
    diff: NotRequired[str]


class PlanStep(TypedDict):
    id: str
    title: str
    detail: str


class SoftwareReport(TypedDict):
    verdict: SoftwareVerdict
    summary: str
    goal: str
    plan: list[PlanStep]
    findings: list[SoftwareFinding]
    checksRun: list[SoftwareCheckId]


class SpecialistNote(TypedDict, total=False):
    at: str
    verdict: SoftwareVerdict
    summary: str
    label: str
    goal: str


class ProposedMemoryUpdate(TypedDict):
    memoryId: str
    summary: str
    rationale: NotRequired[str]


class SoftwareSynthesis(TypedDict):
    narrativeSummary: str
    proposedMemoryUpdates: list[ProposedMemoryUpdate]
    note: str
