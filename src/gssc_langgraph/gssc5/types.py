"""Types for loading gssc5 Dot Agents skills / memories into LangGraph state.

Source layout (sibling repo GSSC-Web/gssc5, read-only):
  .agents/skills/<id>/SKILL.md
  .agents/memories/<id>.md
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

Gssc5DocKind = Literal["skill", "memory"]
Gssc5RoleHint = Literal["software", "test", "general", "reviewer"]


class Gssc5DocMeta(TypedDict):
    id: str
    kind: Gssc5DocKind
    """Absolute or resolved path under the gssc5 root."""
    path: str
    """Relative path from `.agents/` (e.g. `skills/foo/SKILL.md`)."""
    relPath: str
    tags: list[str]
    enabled: bool
    name: NotRequired[str | None]
    title: NotRequired[str | None]
    description: NotRequired[str | None]
    importance: NotRequired[str | None]


class Gssc5Doc(Gssc5DocMeta):
    """Full markdown body including frontmatter."""

    content: str
    """Body without YAML frontmatter."""
    body: str


class Gssc5ScoredDoc(TypedDict):
    doc: Gssc5Doc
    score: float
    reasons: list[str]


class Gssc5SelectedEntry(TypedDict):
    id: str
    kind: Gssc5DocKind
    score: float
    reasons: list[str]


class Gssc5ContextBundle(TypedDict):
    """Resolved gssc5 checkout root, or empty when unavailable."""

    root: str
    query: str
    skills: list[Gssc5Doc]
    memories: list[Gssc5Doc]
    """Selection diagnostics (ids + scores)."""
    selected: list[Gssc5SelectedEntry]
    """Why nothing loaded (missing root, empty catalog, etc.)."""
    note: str


class SelectGssc5Options(TypedDict, total=False):
    """Free-text query (goal, message, task brief)."""

    query: str
    """Soft boost for these skill ids."""
    preferSkills: list[str]
    """Soft boost for these memory ids."""
    preferMemories: list[str]
    """Hard-include these skill ids when present in the catalog."""
    requireSkills: list[str]
    """Hard-include these memory ids when present in the catalog."""
    requireMemories: list[str]
    maxSkills: int
    maxMemories: int
    """Minimum score to keep (after required docs). Default 1."""
    minScore: float


class LoadGssc5ContextOptions(SelectGssc5Options, total=False):
    """Explicit filesystem path to a gssc5 checkout (not a git URL).

    For a custom remote, set `repoUrl` / `GSSC5_REPO_URL` instead.
    """

    root: str
    """Skip filesystem work when false. Default true."""
    enabled: bool
    """Clone/fetch gssc5 into a cache dir when no local root exists.

    Default true (disable with `GSSC5_AUTO_CHECKOUT=false`).
    """
    autoCheckout: bool
    """Cache directory for auto-checkout (default: XDG/home `.cache/gssc-langgraph/gssc5-repo`)."""
    cacheDir: str
    """Git remote URL (default `https://github.com/GSSC-Web/gssc5.git`)."""
    repoUrl: str
    """Branch/tag/ref for auto-checkout (default `master`)."""
    ref: str


ARCH_MEMORY_IDS: tuple[str, ...] = (
    "backend-arch",
    "public-arch",
    "members-arch",
)

CLOSEOUT_PEER_SKILL_IDS: tuple[str, ...] = (
    "requirements-closeout-review",
    "software-closeout-review",
    "test-closeout-review",
)

ROLE_PRESETS: dict[Gssc5RoleHint, dict[str, list[str]]] = {
    "software": {
        "preferSkills": ["software-closeout-review", "requirements-closeout-review"],
        "preferMemories": list(ARCH_MEMORY_IDS),
    },
    "test": {
        "preferSkills": ["test-closeout-review", "requirements-closeout-review"],
        "preferMemories": list(ARCH_MEMORY_IDS),
    },
    "general": {
        "preferSkills": [],
        "preferMemories": list(ARCH_MEMORY_IDS),
    },
    # Peer closeout reviewer — all three closeout skills + arch memories.
    "reviewer": {
        "preferSkills": list(CLOSEOUT_PEER_SKILL_IDS),
        "preferMemories": list(ARCH_MEMORY_IDS),
    },
}
