"""Request/response size budgets for v2 envelopes (GLG-39, GLG-43)."""

from __future__ import annotations

import json
from typing import Any

# Guidance for callers (lean changeSet).
MAX_REQUEST_BODY_BYTES = 32 * 1024
# Reject a single ChangedFile.content larger than this.
MAX_FILE_CONTENT_BYTES = 16 * 1024
# Typical target / hard cap for emitted GraphResponse JSON.
TARGET_RESPONSE_BYTES = 24 * 1024
HARD_RESPONSE_BYTES = 48 * 1024
MAX_SUMMARY_CHARS = 240
MAX_CHAT_ONELINER_CHARS = 120
MAX_FINDING_MESSAGE_CHARS = 280
MAX_PR_BODY_CHARS = 2_000


def utf8_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def truncate_chars(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    if limit <= 1:
        return "…", True
    return text[: limit - 1] + "…", True


def change_set_content_oversized(change_set: dict[str, Any] | None) -> list[str]:
    """Return paths whose embedded ``content`` exceeds the lean budget."""
    if not change_set:
        return []
    oversized: list[str] = []
    for f in change_set.get("files") or []:
        if not isinstance(f, dict):
            continue
        content = f.get("content")
        if content is None:
            continue
        raw = content if isinstance(content, str) else str(content)
        if len(raw.encode("utf-8")) > MAX_FILE_CONTENT_BYTES:
            path = str(f.get("path") or "(unknown)")
            oversized.append(path)
    return oversized


def strip_oversized_content(
    change_set: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Drop oversized ``content`` fields; keep path+status (+diff).

    Returns ``(possibly_mutated_change_set, stripped_paths)``.
    """
    if not change_set:
        return change_set, []
    oversized = change_set_content_oversized(change_set)
    if not oversized:
        return change_set, []
    drop = set(oversized)
    files = []
    for f in change_set.get("files") or []:
        if not isinstance(f, dict):
            continue
        if f.get("path") in drop and "content" in f:
            slim = {k: v for k, v in f.items() if k != "content"}
            files.append(slim)
        else:
            files.append(f)
    out = {**change_set, "files": files}
    return out, oversized
