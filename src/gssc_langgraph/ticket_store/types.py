"""Lean ticket handoff artifact stored in Agent Server Store (GLG-52)."""

from __future__ import annotations

from typing import Any, TypedDict


TICKET_ARTIFACT_SCHEMA_VERSION = "1"

# Default TTL for ticket artifacts (hours). Agent Server / store backends
# may evict earlier; workers must still pass a lean changeSet.
DEFAULT_TICKET_TTL_HOURS = 72.0


class TicketArtifact(TypedDict, total=False):
    """Cross-thread SoftDev→TestDev→Closeout handoff — no file bodies/secrets."""

    schemaVersion: str
    label: str
    kaneoTaskId: str
    domains: list[str]
    plan: list[dict[str, Any]]
    softDevVerdict: str
    testDevVerdict: str
    testCasesSummary: list[dict[str, Any]]
    gapsSummary: list[dict[str, Any]]
    findingCodes: list[str]
    contextRef: dict[str, Any]
    updatedAt: str
    updatedBy: str
