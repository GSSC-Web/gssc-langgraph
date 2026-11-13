"""
Closeout review criteria for gssc-langgraph.

Behavioral reference: gssc5 peer closeout skills — requirements / software /
test closeout-review. Adapted for this Python LangGraph Agent Server.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from gssc_langgraph.closeout.types import CloseoutCheckId

Peer = Literal["requirements", "software", "test", "ops"]


@dataclass(frozen=True)
class Criterion:
    id: CloseoutCheckId
    title: str
    peer: Peer
    description: str


CRITERIA: list[Criterion] = [
    Criterion(
        id="scope",
        title="Scope",
        peer="requirements",
        description=(
            "Identify an in-scope change set (or explicit workspace scan) for "
            "closeout — same spirit as gssc5 Scope across the three peer skills."
        ),
    ),
    Criterion(
        id="contracts",
        title="Contracts",
        peer="requirements",
        description=(
            "Documented / baseline assistant contracts stay intact "
            "(requirements-closeout analogue): no silent baseline drops or "
            "README contract deletion."
        ),
    ),
    Criterion(
        id="software_trace",
        title="Software trace",
        peer="software",
        description=(
            "Each shipped graph is registered in langgraph.json "
            "(software-closeout Trace analogue without StrictDoc "
            "Implementation @relation)."
        ),
    ),
    Criterion(
        id="software_match",
        title="Software match",
        peer="software",
        description=(
            "Software realizes the LangGraph assistant contract "
            "(StateGraph + compile + graph = export), not a hollow stub."
        ),
    ),
    Criterion(
        id="software_quality",
        title="Software quality",
        peer="software",
        description=(
            "Logic and error paths sound; fail-fast; no oversized god modules; "
            "smoke assistants stay model-free when intended."
        ),
    ),
    Criterion(
        id="third_party",
        title="Third parties",
        peer="software",
        description=(
            "Prefer LangGraph, langgraph CLI Agent Server, Python+uv — flag "
            "reinvented HTTP servers or leftover Bun/TS-as-primary packaging."
        ),
    ),
    Criterion(
        id="test_coverage",
        title="Test coverage",
        peer="test",
        description=(
            "Changed / registered graphs have permanent pytest coverage "
            "(test-closeout Trace analogue without Test @relation)."
        ),
    ),
    Criterion(
        id="test_target",
        title="Test target",
        peer="test",
        description=(
            "Tests assert documented contracts / invoke smoke — not empty "
            "asserts; do not “fix” by deleting covering tests with SW edits."
        ),
    ),
    Criterion(
        id="secrets",
        title="Secrets / ops",
        peer="ops",
        description=(
            "Never commit secrets; .env.example stays placeholder-only "
            "(gssc5 agents.md core rule)."
        ),
    ),
]

BASELINE_ASSISTANT_IDS: tuple[str, ...] = ("health",)

MODEL_FREE_ASSISTANT_IDS: tuple[str, ...] = ("health", "conversation")

# Paths / imports that imply reinventing the Agent Server (Python + leftover JS).
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

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("xai-key", re.compile(r"xai-[A-Za-z0-9_-]{20,}")),
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "bearer-literal",
        re.compile(
            r"""Authorization["']?\s*:\s*["']Bearer\s+[A-Za-z0-9._-]{20,}"""
        ),
    ),
]
