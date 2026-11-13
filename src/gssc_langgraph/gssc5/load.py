"""Load a relevance-filtered bundle of gssc5 skills + memories."""

from __future__ import annotations

from gssc_langgraph.gssc5.checkout import EnsureGssc5CheckoutOptions, ensure_gssc5_checkout
from gssc_langgraph.gssc5.select import select_and_load
from gssc_langgraph.gssc5.types import (
    ROLE_PRESETS,
    Gssc5ContextBundle,
    Gssc5RoleHint,
    LoadGssc5ContextOptions,
)


def empty_gssc5_context(note: str, query: str = "") -> Gssc5ContextBundle:
    return {
        "root": "",
        "query": query,
        "skills": [],
        "memories": [],
        "selected": [],
        "note": note,
    }


def load_gssc5_context(
    options: LoadGssc5ContextOptions | None = None,
) -> Gssc5ContextBundle:
    """Load a relevance-filtered bundle of gssc5 skills + memories.

    Resolves an existing local checkout first; otherwise clones/updates
    GSSC-Web/gssc5 into a cache directory (see `ensure_gssc5_checkout`).
    """
    opts: LoadGssc5ContextOptions = options or {}
    query = (opts.get("query") or "").strip()
    if opts.get("enabled") is False:
        return empty_gssc5_context("disabled", query)

    checkout_opts: EnsureGssc5CheckoutOptions = {}
    if "root" in opts:
        checkout_opts["root"] = opts["root"]
    if "autoCheckout" in opts:
        checkout_opts["autoCheckout"] = opts["autoCheckout"]
    if "cacheDir" in opts:
        checkout_opts["cacheDir"] = opts["cacheDir"]
    if "repoUrl" in opts:
        checkout_opts["repoUrl"] = opts["repoUrl"]
    if "ref" in opts:
        checkout_opts["ref"] = opts["ref"]

    checkout = ensure_gssc5_checkout(checkout_opts)

    if not checkout["root"]:
        return empty_gssc5_context(checkout["note"], query)

    selected_bundle = select_and_load(checkout["root"], opts)
    skills = selected_bundle["skills"]
    memories = selected_bundle["memories"]
    selected = selected_bundle["selected"]

    if len(skills) + len(memories) == 0:
        note = (
            f"no skills/memories met the relevance threshold ({checkout['note']})"
        )
    else:
        mem_word = "y" if len(memories) == 1 else "ies"
        note = (
            f"loaded {len(skills)} skill(s), {len(memories)} memor{mem_word} "
            f"from {checkout['root']} ({checkout['source']})"
        )

    return {
        "root": checkout["root"],
        "query": query,
        "skills": skills,
        "memories": memories,
        "selected": selected,
        "note": note,
    }


def load_gssc5_context_for_role(
    role: Gssc5RoleHint,
    options: LoadGssc5ContextOptions | None = None,
) -> Gssc5ContextBundle:
    opts: LoadGssc5ContextOptions = dict(options or {})
    preset = ROLE_PRESETS[role]
    opts["preferSkills"] = [
        *(preset.get("preferSkills") or []),
        *(opts.get("preferSkills") or []),
    ]
    opts["preferMemories"] = [
        *(preset.get("preferMemories") or []),
        *(opts.get("preferMemories") or []),
    ]
    return load_gssc5_context(opts)


def format_gssc5_context(bundle: Gssc5ContextBundle) -> str:
    """Flatten selected docs into a single prompt-friendly string."""
    if not bundle["skills"] and not bundle["memories"]:
        return bundle["note"] or "(no gssc5 context)"
    parts: list[str] = []
    for skill in bundle["skills"]:
        parts.append(f"## Skill: {skill['id']}\n\n{skill['body'].strip()}")
    for memory in bundle["memories"]:
        parts.append(f"## Memory: {memory['id']}\n\n{memory['body'].strip()}")
    return "\n\n---\n\n".join(parts)
