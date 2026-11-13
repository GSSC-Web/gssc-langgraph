"""Shared change-set types for tooling CLIs (collect + software / test_dev)."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

FileStatus = Literal["added", "modified", "deleted", "unchanged"]


class ChangedFile(TypedDict):
    path: str
    status: FileStatus
    """Full file contents when available (workspace / collected files)."""
    content: NotRequired[str | None]
    """Unified-diff hunks for this path when reviewing a diff."""
    patch: NotRequired[str | None]


class ChangeSet(TypedDict):
    """Human label: e.g. git base ref or "workspace"."""

    label: str
    files: list[ChangedFile]
    """Raw unified diff when present."""
    diff: NotRequired[str | None]
