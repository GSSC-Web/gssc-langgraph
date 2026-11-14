"""Coerce MCP/JSON text fields that callers may send as string or list."""

from __future__ import annotations

from typing import Any


def coerce_text(value: Any) -> str:
    """Normalize ``str | list[str]`` (and nested lists) to a single string.

    MCP / JSON callers often pass ``requirements`` (and similar) as a string
    array. Joining without coercion raises ``TypeError``. Empty after coerce
    yields ``""`` so parsers can emit structured input ERROR.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        parts = [coerce_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)
