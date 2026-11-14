"""Shared v2 GraphResponse envelope types (GLG-35…46)."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

SchemaVersion = Literal["2"]
GraphVerdict = Literal["PASS", "FAIL", "ERROR"]
FindingSeverity = Literal["error", "warning", "info"]
DomainId = Literal[
    "backend",
    "public-fe",
    "members-fe",
    "admin-fe",
    "langgraph",
    "unknown",
]
ToolName = Literal[
    "GSSC_Software_Dev",
    "GSSC_Test_Development",
    "GSSC_Closeout_Review",
    "GSSC_Health",
    "GSSC_Conversation",
]
NextActionOwner = Literal["worker", "coordinator", "human", "system"]


class EnvelopeFinding(TypedDict):
    code: str
    severity: FindingSeverity
    message: str
    path: NotRequired[str]
    uid: NotRequired[str]
    truncated: NotRequired[bool]


class NextAction(TypedDict):
    action: str
    owner: NextActionOwner
    detail: NotRequired[str]


class Digest(TypedDict):
    chatOneLiner: str
    prBodyMarkdown: str
    truncated: NotRequired[bool]


class Friction(TypedDict):
    fileOnKaneo: bool
    notes: str
    suggestedTitle: NotRequired[str]


class ContextRef(TypedDict):
    root: str
    cacheKey: str
    skillIds: list[str]
    memoryIds: list[str]


class GraphResponse(TypedDict):
    """Canonical coordinator/worker response (schemaVersion 2)."""

    schemaVersion: SchemaVersion
    tool: ToolName
    label: str
    verdict: GraphVerdict
    summary: str
    findings: list[EnvelopeFinding]
    nextActions: list[NextAction]
    digest: Digest
    friction: Friction
    domains: list[DomainId]
    payload: dict[str, Any]
    contextRef: NotRequired[ContextRef]
    truncated: NotRequired[bool]
