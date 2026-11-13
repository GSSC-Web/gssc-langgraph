"""Resolve an existing gssc5 checkout that owns `.agents/` (no clone)."""

from __future__ import annotations

import os
import re
from pathlib import Path


def looks_like_git_url(value: str) -> bool:
    """True when a value looks like a git remote URL (not a filesystem path)."""
    v = value.strip()
    return bool(
        re.match(r"^https?://", v, re.IGNORECASE)
        or re.match(r"^git@", v, re.IGNORECASE)
        or re.match(r"^ssh://", v, re.IGNORECASE)
        or re.match(r"^git://", v, re.IGNORECASE)
        or v.endswith(".git")
    )


def is_gssc5_root(root: str) -> bool:
    if not root:
        return False
    base = Path(root)
    return (
        (base / ".agents" / "skills").exists()
        or (base / ".agents" / "memories").exists()
        or (base / ".agents" / "agents.md").exists()
    )


def agents_dir(root: str) -> Path:
    return Path(root) / ".agents"


def resolve_gssc5_root(
    override: str | None = None,
    cwd: str | None = None,
) -> str:
    """Resolve an **existing** gssc5 checkout that owns `.agents/` (no clone).

    Order:
    1. Explicit `override` argument (filesystem path — not a URL)
    2. `GSSC5_ROOT` env (filesystem path — not a URL)
    3. Sibling checkout `../gssc5` relative to cwd
    4. `./gssc5` under cwd

    For clone/fetch into a cache dir, use `ensure_gssc5_checkout`.
    Returns `""` when no usable local root is found.
    """
    base = Path(cwd) if cwd is not None else Path.cwd()
    candidates: list[Path] = []

    if override and override.strip():
        if looks_like_git_url(override):
            return ""
        candidates.append((base / override.strip()).resolve())

    env = (os.environ.get("GSSC5_ROOT") or "").strip()
    if env:
        if looks_like_git_url(env):
            # Path-only env; URLs belong in GSSC5_REPO_URL.
            pass
        else:
            candidates.append((base / env).resolve())

    candidates.append((base / ".." / "gssc5").resolve())
    candidates.append((base / "gssc5").resolve())

    for root in candidates:
        root_str = str(root)
        if is_gssc5_root(root_str):
            return root_str
    return ""
