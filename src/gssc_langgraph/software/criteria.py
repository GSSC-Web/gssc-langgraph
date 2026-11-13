"""
Software development / closeout criteria for gssc-langgraph.

Behavioral reference: gssc5 software agent and software-closeout-review skill.
Adapted for this Python LangGraph Agent Server.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gssc_langgraph.software.types import SoftwareCheckId


@dataclass(frozen=True)
class Criterion:
    id: SoftwareCheckId
    title: str
    description: str


CRITERIA: list[Criterion] = [
    Criterion(
        id="scope",
        title="Scope",
        description=(
            "A clear development goal (or reviewable change set) is present; "
            "work stays on LangGraph service concerns."
        ),
    ),
    Criterion(
        id="trace",
        title="Trace / wiring",
        description=(
            "New or changed assistants are registered in langgraph.json and "
            "discoverable (assign `graph = …`, documented assistant id)."
        ),
    ),
    Criterion(
        id="match",
        title="Match intent",
        description=(
            "Software realizes the stated goal / LangGraph assistant contract "
            "(StateGraph + compile + graph =), not a hollow stub."
        ),
    ),
    Criterion(
        id="quality",
        title="Quality",
        description=(
            "Logic and error paths are sound; fail-fast; no oversized god "
            "modules; smoke assistants stay model-free when intended."
        ),
    ),
    Criterion(
        id="third_party",
        title="Third parties",
        description=(
            "Prefer LangGraph, langgraph CLI Agent Server, Python+uv — flag "
            "reinvented HTTP servers or leftover Bun/TS-as-primary packaging."
        ),
    ),
    Criterion(
        id="discipline",
        title="Dev discipline",
        description=(
            "Do not silently rewrite contracts or delete baseline assistants; "
            "do not “fix” software by deleting covering tests in the same change."
        ),
    ),
]

BASELINE_ASSISTANT_IDS: tuple[str, ...] = ("health",)

PREFERRED_STACK: tuple[str, ...] = (
    "langgraph",
    "langgraph-cli",
    "langchain-core",
    "uv",
    "pytest",
)

REINVENTED_SERVER_HINTS: list[re.Pattern[str]] = [
    re.compile(r"\bfrom\s+fastapi\b|\bimport\s+fastapi\b"),
    re.compile(r"\bfrom\s+flask\b|\bimport\s+flask\b"),
    re.compile(r"\bfrom\s+django\b|\bimport\s+django\b"),
    re.compile(r"\bfrom\s+starlette\b|\bimport\s+starlette\b"),
    re.compile(r"\bFastAPI\s*\("),
    re.compile(r"\bFlask\s*\("),
    re.compile(r"""from\s+["']elysia["']|import\s+elysia\b"""),
    re.compile(r"""from\s+["']express["']|require\s*\(\s*["']express["']"""),
    re.compile(r"""from\s+["']hono["']|import\s+.*\bhono\b"""),
    re.compile(r"""from\s+["']fastify["']|require\s*\(\s*["']fastify["']"""),
    re.compile(r"""from\s+["']koa["']|require\s*\(\s*["']koa["']"""),
    re.compile(r"\bcreateServer\s*\("),
    re.compile(r"\bhttp\.createServer\s*\("),
    re.compile(r"\buvicorn\.run\s*\("),
    re.compile(r"\bHypercorn\b|\bgunicorn\b"),
]

GRAPH_GOD_FILE_LINES = 400
