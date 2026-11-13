"""gssc5 skills/memories loader for LangGraph graphs.

Reads Dot Agents content from a local gssc5 checkout, or clones/updates
GSSC-Web/gssc5 into a cache dir (see `ensure_gssc5_checkout`).
Does not modify upstream gssc5 content; this service only consumes `.agents/`.
"""

from gssc_langgraph.gssc5.catalog import list_memories, list_skills, load_doc, load_docs
from gssc_langgraph.gssc5.checkout import (
    DEFAULT_GSSC5_REF,
    DEFAULT_GSSC5_REPO_URL,
    EnsureGssc5CheckoutOptions,
    GitRunner,
    Gssc5CheckoutResult,
    checkout_gssc5_to_cache,
    default_gssc5_cache_dir,
    ensure_gssc5_checkout,
    resolve_gssc5_ref,
    resolve_gssc5_repo_url,
)
from gssc_langgraph.gssc5.load import (
    empty_gssc5_context,
    format_gssc5_context,
    load_gssc5_context,
    load_gssc5_context_for_role,
)
from gssc_langgraph.gssc5.node import (
    Gssc5ContextNodeConfig,
    Gssc5ContextNodeState,
    create_load_gssc5_context_node,
)
from gssc_langgraph.gssc5.parse import parse_frontmatter
from gssc_langgraph.gssc5.root import (
    agents_dir,
    is_gssc5_root,
    looks_like_git_url,
    resolve_gssc5_root,
)
from gssc_langgraph.gssc5.select import score_doc, select_and_load, tokenize
from gssc_langgraph.gssc5.types import (
    ARCH_MEMORY_IDS,
    CLOSEOUT_PEER_SKILL_IDS,
    ROLE_PRESETS,
    Gssc5ContextBundle,
    Gssc5Doc,
    Gssc5DocKind,
    Gssc5DocMeta,
    Gssc5RoleHint,
    Gssc5ScoredDoc,
    LoadGssc5ContextOptions,
    SelectGssc5Options,
)

__all__ = [
    "ARCH_MEMORY_IDS",
    "CLOSEOUT_PEER_SKILL_IDS",
    "DEFAULT_GSSC5_REF",
    "DEFAULT_GSSC5_REPO_URL",
    "EnsureGssc5CheckoutOptions",
    "GitRunner",
    "Gssc5CheckoutResult",
    "Gssc5ContextBundle",
    "Gssc5ContextNodeConfig",
    "Gssc5ContextNodeState",
    "Gssc5Doc",
    "Gssc5DocKind",
    "Gssc5DocMeta",
    "Gssc5RoleHint",
    "Gssc5ScoredDoc",
    "LoadGssc5ContextOptions",
    "ROLE_PRESETS",
    "SelectGssc5Options",
    "agents_dir",
    "checkout_gssc5_to_cache",
    "create_load_gssc5_context_node",
    "default_gssc5_cache_dir",
    "empty_gssc5_context",
    "ensure_gssc5_checkout",
    "format_gssc5_context",
    "is_gssc5_root",
    "list_memories",
    "list_skills",
    "load_doc",
    "load_docs",
    "load_gssc5_context",
    "load_gssc5_context_for_role",
    "looks_like_git_url",
    "parse_frontmatter",
    "resolve_gssc5_ref",
    "resolve_gssc5_repo_url",
    "resolve_gssc5_root",
    "score_doc",
    "select_and_load",
    "tokenize",
]
