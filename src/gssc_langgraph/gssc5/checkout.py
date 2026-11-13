"""Clone or update gssc5 into a local cache when no checkout exists."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypedDict

from gssc_langgraph.gssc5.root import is_gssc5_root, looks_like_git_url, resolve_gssc5_root

DEFAULT_GSSC5_REPO_URL = "https://github.com/GSSC-Web/gssc5.git"
DEFAULT_GSSC5_REF = "master"

GitResult = TypedDict(
    "GitResult",
    {
        "status": int,
        "stdout": str,
        "stderr": str,
    },
)

GitRunner = Callable[..., GitResult]


class EnsureGssc5CheckoutOptions(TypedDict, total=False):
    """Explicit filesystem root (same as GSSC5_ROOT). Not a URL."""

    root: str
    """Working directory for relative path resolution."""
    cwd: str
    """Clone/update cache directory (contains a `gssc5` checkout)."""
    cacheDir: str
    """Git remote URL. Default: GSSC-Web/gssc5."""
    repoUrl: str
    """Branch/tag/ref to check out. Default: master."""
    ref: str
    """When true (default), clone/fetch into the cache if no local root exists."""
    autoCheckout: bool
    """Injectable git runner (tests)."""
    git: GitRunner


class Gssc5CheckoutResult(TypedDict):
    root: str
    """How the root was obtained."""
    source: Literal["override", "env", "sibling", "cache", "none"]
    note: str


def default_gssc5_cache_dir(cwd: str | None = None) -> str:
    base = Path(cwd) if cwd is not None else Path.cwd()
    env = (os.environ.get("GSSC5_CACHE_DIR") or "").strip()
    if env:
        return str((base / env).resolve())
    # Prefer XDG cache when available; fall back to tmp + home.
    xdg = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg:
        return str(Path(xdg) / "gssc-langgraph" / "gssc5-repo")
    home = Path.home()
    if str(home):
        return str(home / ".cache" / "gssc-langgraph" / "gssc5-repo")
    return str(Path(tempfile.gettempdir()) / "gssc-langgraph" / "gssc5-repo")


def resolve_gssc5_repo_url(override: str | None = None) -> str:
    return (
        (override or "").strip()
        or (os.environ.get("GSSC5_REPO_URL") or "").strip()
        or DEFAULT_GSSC5_REPO_URL
    )


def resolve_gssc5_ref(override: str | None = None) -> str:
    return (
        (override or "").strip()
        or (os.environ.get("GSSC5_REF") or "").strip()
        or DEFAULT_GSSC5_REF
    )


def _auto_checkout_enabled(override: bool | None = None) -> bool:
    if isinstance(override, bool):
        return override
    env = (os.environ.get("GSSC5_AUTO_CHECKOUT") or "").strip().lower()
    if env in ("0", "false", "no", "off"):
        return False
    return True


def default_git_runner(
    args: list[str],
    *,
    cwd: str | None = None,
) -> GitResult:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    return {
        "status": result.returncode if result.returncode is not None else 1,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }


def _run_git(
    git: GitRunner,
    args: list[str],
    *,
    cwd: str | None = None,
) -> GitResult:
    # Support both keyword and positional options styles (TS injects `{ cwd }`).
    try:
        return git(args, cwd=cwd)
    except TypeError:
        return git(args, {"cwd": cwd} if cwd is not None else None)


def _is_git_repo(dir_path: str, git: GitRunner) -> bool:
    if not (Path(dir_path) / ".git").exists():
        return False
    r = _run_git(git, ["rev-parse", "--is-inside-work-tree"], cwd=dir_path)
    return r["status"] == 0 and r["stdout"].strip() == "true"


def checkout_gssc5_to_cache(
    options: EnsureGssc5CheckoutOptions | None = None,
) -> Gssc5CheckoutResult:
    """Clone or update gssc5 into the cache directory.

    Returns the checkout path when `.agents/` is present.
    """
    opts = options or {}
    cwd = opts.get("cwd") or str(Path.cwd())
    cache_dir_opt = (opts.get("cacheDir") or "").strip()
    cache_dir = str(
        (Path(cwd) / (cache_dir_opt or default_gssc5_cache_dir(cwd))).resolve()
    )
    target = str(Path(cache_dir) / "gssc5")
    repo_url = resolve_gssc5_repo_url(opts.get("repoUrl"))
    ref = resolve_gssc5_ref(opts.get("ref"))
    git = opts.get("git") or default_git_runner

    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    try:
        if _is_git_repo(target, git) and is_gssc5_root(target):
            # Best-effort update; keep existing tree if fetch fails (offline).
            fetch = _run_git(
                git,
                ["fetch", "--depth", "1", "origin", ref],
                cwd=target,
            )
            if fetch["status"] == 0:
                co = _run_git(git, ["checkout", "-f", "FETCH_HEAD"], cwd=target)
                if co["status"] != 0:
                    _run_git(git, ["checkout", "-f", ref], cwd=target)
            if is_gssc5_root(target):
                return {
                    "root": target,
                    "source": "cache",
                    "note": f"using cached gssc5 at {target} (ref {ref})",
                }

        if Path(target).exists():
            shutil.rmtree(target, ignore_errors=True)

        clone = _run_git(
            git,
            [
                "clone",
                "--depth",
                "1",
                "--branch",
                ref,
                "--single-branch",
                repo_url,
                target,
            ],
            cwd=cache_dir,
        )
        if clone["status"] != 0:
            detail = (
                clone["stderr"].strip()
                or clone["stdout"].strip()
                or f"exit {clone['status']}"
            )
            return {
                "root": "",
                "source": "none",
                "note": f"git clone failed ({repo_url}@{ref}): {detail}",
            }

        if not is_gssc5_root(target):
            return {
                "root": "",
                "source": "none",
                "note": f"cloned {repo_url} but .agents/ not found under {target}",
            }

        return {
            "root": target,
            "source": "cache",
            "note": f"cloned gssc5 into {target} (ref {ref})",
        }
    except Exception as err:  # noqa: BLE001 — match TS catch-all
        message = str(err)
        return {
            "root": "",
            "source": "none",
            "note": f"gssc5 checkout error: {message}",
        }


def ensure_gssc5_checkout(
    options: EnsureGssc5CheckoutOptions | None = None,
) -> Gssc5CheckoutResult:
    """Resolve a usable gssc5 root: existing local path first, else clone/update cache.

    `GSSC5_ROOT` / `root` must be a **filesystem path**, not a git URL.
    Use `GSSC5_REPO_URL` for a custom remote.
    """
    opts = options or {}
    cwd = opts.get("cwd") or str(Path.cwd())
    override = (opts.get("root") or "").strip() or None

    if override and looks_like_git_url(override):
        return {
            "root": "",
            "source": "none",
            "note": (
                "GSSC5_ROOT/root must be a filesystem path, not a URL — "
                "set GSSC5_REPO_URL for a custom remote"
            ),
        }

    env_root = (os.environ.get("GSSC5_ROOT") or "").strip() or None
    if env_root and looks_like_git_url(env_root) and not override:
        return {
            "root": "",
            "source": "none",
            "note": (
                "GSSC5_ROOT must be a filesystem path, not a URL — "
                "set GSSC5_REPO_URL for a custom remote"
            ),
        }

    # Prefer explicit override / env / sibling without cloning.
    if override:
        resolved = str((Path(cwd) / override).resolve())
        if is_gssc5_root(resolved):
            return {
                "root": resolved,
                "source": "override",
                "note": f"using override root {resolved}",
            }
        # Explicit root that does not exist: hard miss (do not fall through to clone).
        return {
            "root": "",
            "source": "none",
            "note": f"gssc5 root not found at override path {resolved}",
        }

    if env_root:
        resolved = str((Path(cwd) / env_root).resolve())
        if is_gssc5_root(resolved):
            return {
                "root": resolved,
                "source": "env",
                "note": f"using GSSC5_ROOT {resolved}",
            }

    sibling = resolve_gssc5_root(None, cwd)
    if sibling:
        source: Literal["override", "env", "sibling", "cache", "none"] = (
            "env"
            if env_root and str((Path(cwd) / env_root).resolve()) == sibling
            else "sibling"
        )
        return {
            "root": sibling,
            "source": source,
            "note": f"using local gssc5 at {sibling}",
        }

    if not _auto_checkout_enabled(opts.get("autoCheckout")):
        return {
            "root": "",
            "source": "none",
            "note": (
                "gssc5 root not found (set GSSC5_ROOT, place sibling ../gssc5, "
                "or enable auto-checkout)"
            ),
        }

    return checkout_gssc5_to_cache(opts)
