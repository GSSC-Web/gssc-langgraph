"""LangGraph node factory that selects + loads gssc5 skills/memories."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from gssc_langgraph.gssc5.load import format_gssc5_context, load_gssc5_context_for_role
from gssc_langgraph.gssc5.types import (
    Gssc5ContextBundle,
    Gssc5RoleHint,
    LoadGssc5ContextOptions,
)


class Gssc5ContextNodeConfig(TypedDict, total=False):
    """Default role preset when not overridden per-invoke."""

    role: Gssc5RoleHint
    """State field used as the relevance query."""
    queryField: str
    """Extra static prefer/require options."""
    loadOptions: LoadGssc5ContextOptions
    """Step name recorded in `steps` when the host graph tracks them."""
    stepName: str


class Gssc5ContextNodeState(TypedDict, total=False):
    gssc5Context: Gssc5ContextBundle | None
    gssc5ContextText: str
    gssc5Root: str
    steps: list[str]
    goal: str
    message: str


class Gssc5NodeConfigurable(TypedDict, total=False):
    gssc5Root: str
    gssc5Role: Gssc5RoleHint
    gssc5Enabled: bool
    preferSkills: list[str]
    preferMemories: list[str]
    requireSkills: list[str]
    requireMemories: list[str]


def create_load_gssc5_context_node(
    defaults: Gssc5ContextNodeConfig | None = None,
) -> Callable[..., dict[str, Any]]:
    """Factory for a LangGraph node that selects + loads gssc5 skills/memories.

    Writes:
    - `gssc5Context` — structured bundle
    - `gssc5ContextText` — flattened markdown for prompts
    - `gssc5Root` — resolved checkout path (may be empty)
    - `steps` — appends step name when the host uses a steps reducer
    """
    cfg = defaults or {}
    role_default: Gssc5RoleHint = cfg.get("role") or "general"
    query_field = cfg.get("queryField") or "message"
    step_name = cfg.get("stepName") or "load_gssc5_context"
    load_options: LoadGssc5ContextOptions = dict(cfg.get("loadOptions") or {})

    def node(
        state: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        configurable: Mapping[str, Any] = {}
        if config is not None:
            configurable = config.get("configurable") or {}

        role: Gssc5RoleHint = configurable.get("gssc5Role") or role_default
        raw_query = state.get(query_field)
        if isinstance(raw_query, str):
            query = raw_query
        elif isinstance(state.get("goal"), str):
            query = state["goal"]
        elif isinstance(state.get("message"), str):
            query = state["message"]
        else:
            query = ""

        opts: LoadGssc5ContextOptions = {
            **load_options,
            "query": query,
            "root": configurable.get("gssc5Root", load_options.get("root")),
            "enabled": configurable.get(
                "gssc5Enabled", load_options.get("enabled")
            ),
            "preferSkills": [
                *(load_options.get("preferSkills") or []),
                *(configurable.get("preferSkills") or []),
            ],
            "preferMemories": [
                *(load_options.get("preferMemories") or []),
                *(configurable.get("preferMemories") or []),
            ],
            "requireSkills": [
                *(load_options.get("requireSkills") or []),
                *(configurable.get("requireSkills") or []),
            ],
            "requireMemories": [
                *(load_options.get("requireMemories") or []),
                *(configurable.get("requireMemories") or []),
            ],
        }
        # Drop None roots/enabled so TypedDict optionals stay clean.
        if opts.get("root") is None:
            opts.pop("root", None)
        if opts.get("enabled") is None:
            opts.pop("enabled", None)

        bundle = load_gssc5_context_for_role(role, opts)
        return {
            "gssc5Context": bundle,
            "gssc5ContextText": format_gssc5_context(bundle),
            "gssc5Root": bundle["root"],
            "steps": [step_name],
        }

    return node
