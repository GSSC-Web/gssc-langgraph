"""Minimal YAML frontmatter parser for gssc5 skill/memory markdown.

Handles the subset used in Dot Agents files (scalars, simple lists).
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

_FM_RE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$")


class ParsedFrontmatter(TypedDict):
    meta: dict[str, Any]
    body: str
    raw: str


def parse_frontmatter(raw: str) -> ParsedFrontmatter:
    m = _FM_RE.match(raw)
    if not m:
        return {"meta": {}, "body": raw, "raw": raw}
    return {
        "meta": _parse_simple_yaml(m.group(1) or ""),
        "body": (m.group(2) or "").lstrip(),
        "raw": raw,
    }


def _parse_simple_yaml(block: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    lines = re.split(r"\r?\n", block)
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        folded = re.match(r"^([A-Za-z0-9_-]+):\s*>-\s*$", line)
        if folded:
            key = folded.group(1)
            parts: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if re.match(r"^\S", nxt) and ":" in nxt:
                    break
                if not nxt.strip():
                    i += 1
                    break
                parts.append(nxt.strip())
                i += 1
            meta[key] = " ".join(parts).strip()
            continue

        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not kv:
            continue
        key = kv.group(1)
        rest = (kv.group(2) or "").strip()

        if rest.startswith("[") and rest.endswith("]"):
            meta[key] = [
                s.strip().strip("\"'")
                for s in rest[1:-1].split(",")
                if s.strip().strip("\"'")
            ]
            continue

        if rest in ("", "|", ">", ">-"):
            parts = []
            while i < len(lines):
                nxt = lines[i]
                if re.match(r"^\S", nxt) and ":" in nxt:
                    break
                parts.append(nxt.strip())
                i += 1
            join_with_space = rest in (">", ">-")
            meta[key] = (" " if join_with_space else "\n").join(parts).strip()
            continue

        if rest in ("true", "false"):
            meta[key] = rest == "true"
            continue

        meta[key] = rest.strip("\"'")
    return meta


def as_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [
            (v.strip() if isinstance(v, str) else str(v))
            for v in value
            if (v.strip() if isinstance(v, str) else str(v))
        ]
    if isinstance(value, str) and value.strip():
        return [s.strip() for s in re.split(r"[,\s]+", value) if s.strip()]
    return []


def as_bool(value: Any, fallback: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v == "true":
            return True
        if v == "false":
            return False
    return fallback
