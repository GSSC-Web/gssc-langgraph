"""Shared v2 GraphResponse envelope (GLG-35…46)."""

from gssc_langgraph.envelope.budgets import (
    HARD_RESPONSE_BYTES,
    MAX_FILE_CONTENT_BYTES,
    MAX_REQUEST_BODY_BYTES,
    TARGET_RESPONSE_BYTES,
    change_set_content_oversized,
    strip_oversized_content,
)
from gssc_langgraph.envelope.build import (
    apply_response_budgets,
    build_friction,
    build_graph_response,
    build_next_actions,
    context_ref_from_bundle,
    normalize_findings,
)
from gssc_langgraph.envelope.coerce import coerce_text
from gssc_langgraph.envelope.domains import domains_from_paths, pin_domains
from gssc_langgraph.envelope.types import (
    ContextRef,
    Digest,
    DomainId,
    EnvelopeFinding,
    Friction,
    GraphResponse,
    GraphVerdict,
    NextAction,
    ToolName,
)

__all__ = [
    "HARD_RESPONSE_BYTES",
    "MAX_FILE_CONTENT_BYTES",
    "MAX_REQUEST_BODY_BYTES",
    "TARGET_RESPONSE_BYTES",
    "ContextRef",
    "Digest",
    "DomainId",
    "EnvelopeFinding",
    "Friction",
    "GraphResponse",
    "GraphVerdict",
    "NextAction",
    "ToolName",
    "apply_response_budgets",
    "build_friction",
    "build_graph_response",
    "build_next_actions",
    "change_set_content_oversized",
    "coerce_text",
    "context_ref_from_bundle",
    "domains_from_paths",
    "normalize_findings",
    "pin_domains",
    "strip_oversized_content",
]
