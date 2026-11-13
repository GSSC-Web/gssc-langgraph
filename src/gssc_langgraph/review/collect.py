"""Collect workspace / git / path change sets for specialist graphs."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from gssc_langgraph.review.types import ChangeSet, ChangedFile, FileStatus

SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        ".cursor",
        "coverage",
        ".venv",
        "__pycache__",
    }
)

# Prefer Python project surfaces; still accept package.json when present.
_INTERESTING_EXACT = frozenset(
    {
        "langgraph.json",
        "pyproject.toml",
        "README.md",
        ".env.example",
        "package.json",
        "requirements.txt",
    }
)

_GRAPH_PATH_RE = re.compile(
    r"^(?:src/gssc_langgraph/graphs/|src/graphs/)"
)


def _walk_files(root: Path, directory: Path) -> list[str]:
    out: list[str] = []
    try:
        entries = sorted(directory.iterdir(), key=lambda p: p.name)
    except OSError:
        return out
    for ent in entries:
        if ent.name in SKIP_DIRS:
            continue
        if ent.is_dir():
            out.extend(_walk_files(root, ent))
        elif ent.is_file():
            rel = ent.relative_to(root).as_posix()
            out.append(rel)
    return out


def _read_optional(root: Path, path: str) -> str | None:
    try:
        return (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _is_interesting(path: str) -> bool:
    if path in _INTERESTING_EXACT:
        return True
    if path.startswith("src/") or path.startswith("tests/"):
        return True
    if path.endswith(".py"):
        return True
    return False


def collect_workspace(root: str) -> ChangeSet:
    """Full workspace snapshot for structural review."""
    root_path = Path(root)
    paths = _walk_files(root_path, root_path)
    interesting = [p for p in paths if _is_interesting(p)]

    files: list[ChangedFile] = []
    for path in interesting:
        content = _read_optional(root_path, path)
        files.append(
            {
                "path": path,
                "content": content,
                "status": "unchanged",
            }
        )

    return {"label": "workspace", "files": files}


def _parse_diff_paths(
    diff: str,
) -> dict[str, dict[str, str]]:
    """Return path → {status, patch}."""
    result: dict[str, dict[str, str]] = {}
    parts = [p for p in re.split(r"^diff --git ", diff, flags=re.MULTILINE) if p]
    for part in parts:
        header = part.split("\n", 1)[0] if part else ""
        m = re.search(r"a/(.+?)\s+b/(.+)$", header)
        if not m:
            continue
        a_path = m.group(1)
        b_path = m.group(2)
        body = f"diff --git {part}"
        status: FileStatus = "modified"
        if re.search(r"^new file mode", part, re.MULTILINE) or a_path == "/dev/null":
            status = "added"
        if (
            re.search(r"^deleted file mode", part, re.MULTILINE)
            or b_path == "/dev/null"
        ):
            status = "deleted"
        path = a_path if status == "deleted" else b_path
        result[path] = {"status": status, "patch": body}
    return result


def _is_graph_path(path: str) -> bool:
    return bool(_GRAPH_PATH_RE.match(path))


def collect_from_diff(
    root: str,
    diff: str,
    label: str = "diff",
) -> ChangeSet:
    """Build a ChangeSet from a unified diff, enriching with on-disk contents."""
    root_path = Path(root)
    parsed = _parse_diff_paths(diff)
    files: list[ChangedFile] = []

    for path, meta in parsed.items():
        content: str | None = None
        if meta["status"] != "deleted":
            content = _read_optional(root_path, path)
        files.append(
            {
                "path": path,
                "content": content,
                "patch": meta["patch"],
                "status": meta["status"],  # type: ignore[typeddict-item]
            }
        )

    # Always attach registry/package/README/.env.example when present.
    for extra in ("langgraph.json", "package.json", "README.md", ".env.example", "pyproject.toml"):
        if any(f["path"] == extra for f in files):
            continue
        content = _read_optional(root_path, extra)
        if content is not None:
            files.append({"path": extra, "content": content, "status": "unchanged"})

    # Attach existing test files for coverage heuristics when graphs change.
    graph_changed = any(_is_graph_path(f["path"]) for f in files)
    if graph_changed:
        test_dir = root_path / "tests"
        if test_dir.is_dir():
            tests = _walk_files(root_path, test_dir)
            for path in tests:
                if any(f["path"] == path for f in files):
                    continue
                content = _read_optional(root_path, path)
                files.append(
                    {"path": path, "content": content, "status": "unchanged"}
                )

    return {"label": label, "files": files, "diff": diff}


def _git(
    root: str,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", root, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _collect_untracked(root: str) -> list[ChangedFile]:
    listed = _git(root, "ls-files", "--others", "--exclude-standard")
    if listed.returncode != 0:
        return []
    root_path = Path(root)
    paths = [
        p.strip().replace("\\", "/")
        for p in listed.stdout.split("\n")
        if p.strip() and _is_interesting(p.strip().replace("\\", "/"))
    ]
    files: list[ChangedFile] = []
    for path in paths:
        content = _read_optional(root_path, path)
        files.append({"path": path, "content": content, "status": "added"})
    return files


def collect_git_diff(root: str, base_ref: str) -> ChangeSet:
    """Collect merge-base...HEAD + staged/unstaged + untracked; empty → workspace."""
    diff = ""
    try:
        merged = _git(root, "merge-base", base_ref, "HEAD")
        merge_base = merged.stdout.strip() if merged.returncode == 0 else base_ref
        range_spec = f"{merge_base}...HEAD"
        result = _git(root, "diff", "--no-ext-diff", range_spec)
        diff = result.stdout
        unstaged = _git(root, "diff", "--no-ext-diff")
        staged = _git(root, "diff", "--no-ext-diff", "--cached")
        extra = f"{staged.stdout}{unstaged.stdout}"
        if extra.strip():
            diff = f"{diff}\n{extra}" if diff else extra
    except OSError:
        result = _git(root, "diff", "--no-ext-diff", f"{base_ref}...HEAD")
        diff = result.stdout

    untracked = _collect_untracked(root)

    if not diff.strip() and len(untracked) == 0:
        ws = collect_workspace(root)
        return {
            **ws,
            "label": f"workspace (no diff vs {base_ref})",
        }

    if diff.strip():
        cs = collect_from_diff(root, diff, f"git {base_ref}...HEAD")
    else:
        cs = {"label": f"git {base_ref}...HEAD", "files": []}

    for f in untracked:
        if not any(x["path"] == f["path"] for x in cs["files"]):
            cs["files"].append(f)

    # Ensure registry is present when untracked graphs appear.
    if any(_is_graph_path(f["path"]) for f in untracked) and not any(
        f["path"] == "langgraph.json" for f in cs["files"]
    ):
        content = _read_optional(Path(root), "langgraph.json")
        if content is not None:
            cs["files"].append(
                {"path": "langgraph.json", "content": content, "status": "unchanged"}
            )
    return cs


def collect_paths(root: str, paths: list[str]) -> ChangeSet:
    root_path = Path(root)
    files: list[ChangedFile] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        content = _read_optional(root_path, normalized)
        files.append(
            {
                "path": normalized,
                "content": content,
                "status": "deleted" if content is None else "modified",
            }
        )
    for extra in (
        "langgraph.json",
        "package.json",
        "README.md",
        ".env.example",
        "pyproject.toml",
    ):
        if any(f["path"] == extra for f in files):
            continue
        content = _read_optional(root_path, extra)
        if content is not None:
            files.append({"path": extra, "content": content, "status": "unchanged"})
    return {"label": "paths", "files": files}
