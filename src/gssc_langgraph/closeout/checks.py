"""
Deterministic closeout checks for the closeout_review assistant.

Mirrors gssc5 peer closeout skills (requirements / software / test) adapted
for this Python LangGraph Agent Server. No StrictDoc @relation audits.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from gssc_langgraph.closeout.criteria import (
    BASELINE_ASSISTANT_IDS,
    GRAPH_GOD_FILE_LINES,
    MODEL_FREE_ASSISTANT_IDS,
    REINVENTED_SERVER_HINTS,
    SECRET_PATTERNS,
)
from gssc_langgraph.closeout.types import (
    ChangeSet,
    ChangedFile,
    CloseoutCheckId,
    CloseoutFinding,
    CloseoutVerdict,
)

GRAPH_FILE_RE = re.compile(
    r"^(?:src/gssc_langgraph/graphs|src/graphs)/([^/]+)/graph\.py$"
)
TEST_FILE_RE = re.compile(r"^tests/.+\.py$")

CHAT_MODEL_RE = re.compile(
    r"ChatOpenAI|ChatAnthropic|ChatXAI|init_chat_model|initChatModel|"
    r"create_chat_model|createChatModel|"
    r"langchain_openai|langchain_anthropic|langchain_xai|"
    r"""from\s+["']@langchain/(?:openai|anthropic|xai)["']"""
)
EMPTY_CATCH_RE = re.compile(
    r"except(?:\s+\w+(?:\s+as\s+\w+)?)?\s*:\s*(?:pass|\.\.\.)\s*(?:#.*)?$",
    re.MULTILINE,
)
COMPILE_RE = re.compile(
    r"\.compile\s*\(|\bcompile_with_memory\s*\(|\bcompileWithMemory\s*\("
    r"|\bcompile_graph\s*\(|\bcompileGraph\s*\("
)
GRAPH_EXPORT_RE = re.compile(r"(?m)^\s*graph\s*=")
ADD_NODE_RE = re.compile(r"\.add_node\s*\(|\.addNode\s*\(")
GRAPH_NAME_RE = re.compile(
    r"graph\.name\s*=|"
    r"\b(?:compile|compile_with_memory|compileWithMemory|compile_graph|"
    r"compileGraph)\s*\([^)]*\bname\s*="
)

CRITERIA_EXCLUDE = frozenset(
    {
        "src/closeout/criteria.ts",
        "src/software/criteria.ts",
        "src/review/criteria.ts",
        "src/gssc_langgraph/closeout/criteria.py",
        "src/gssc_langgraph/software/criteria.py",
        "src/gssc_langgraph/review/criteria.py",
    }
)


def _file_by_path(cs: ChangeSet, path: str) -> ChangedFile | None:
    for f in cs["files"]:
        if f["path"] == path:
            return f
    return None


def _text_of(file: ChangedFile | None) -> str:
    if not file:
        return ""
    return file.get("content") or file.get("patch") or ""


def _parse_langgraph_json(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _graph_paths(graph_id: str) -> list[str]:
    return [
        f"src/gssc_langgraph/graphs/{graph_id}/graph.py",
        f"src/graphs/{graph_id}/graph.py",
    ]


def _primary_graph_path(graph_id: str) -> str:
    return f"src/gssc_langgraph/graphs/{graph_id}/graph.py"


def _changed_graph_ids(cs: ChangeSet) -> list[str]:
    ids: set[str] = set()
    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if m and f["status"] not in ("unchanged", "deleted"):
            ids.add(m.group(1))
    return sorted(ids)


def _graph_dirs_from_files(cs: ChangeSet) -> list[str]:
    ids: set[str] = set()
    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if m and f["status"] != "deleted":
            ids.add(m.group(1))
    return sorted(ids)


def _uses_chat_model(body: str) -> bool:
    return bool(CHAT_MODEL_RE.search(body))


def _has_langgraph_dep(text: str) -> bool:
    return bool(
        re.search(r"(?m)^\s*[\"']langgraph[\"']\s*[=~<>]", text)
        or re.search(r"(?m)^\s*langgraph\s*[=~<>\[]", text)
        or re.search(r"(?i)\blanggraph\b", text)
    )


def _has_test_touching(cs: ChangeSet, graph_id: str) -> bool:
    spaced = graph_id.replace("_", " ")
    for f in cs["files"]:
        if not TEST_FILE_RE.match(f["path"]) or f["status"] == "deleted":
            continue
        body = _text_of(f)
        if (
            f"src/gssc_langgraph/graphs/{graph_id}/" in body
            or f"src/graphs/{graph_id}/" in body
            or f"graphs/{graph_id}/" in body
            or f'"{graph_id}"' in body
            or f"'{graph_id}'" in body
            or spaced.lower() in body.lower()
        ):
            return True
    return False


def check_scope(cs: ChangeSet | None) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []
    if not cs or not cs.get("files"):
        findings.append(
            {
                "check": "scope",
                "severity": "error",
                "message": "No change set — nothing in scope for closeout review",
                "fix": "Pass a git range / --workspace / --diff / paths.",
            }
        )
    return findings


def check_contracts(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []

    for f in cs["files"]:
        if f["path"] != "langgraph.json":
            continue
        patch = f.get("patch") or ""
        content = f.get("content") or ""
        for aid in BASELINE_ASSISTANT_IDS:
            if patch:
                removed = re.search(rf'(?m)^-\s*"{aid}"\s*:', patch)
                added = re.search(rf'(?m)^\+\s*"{aid}"\s*:', patch)
                if removed and not added:
                    findings.append(
                        {
                            "check": "contracts",
                            "severity": "error",
                            "path": "langgraph.json",
                            "uid": aid,
                            "message": (
                                f'Diff removes baseline assistant_id "{aid}" '
                                "(silent contract rewrite)"
                            ),
                            "fix": (
                                "Do not drop baseline assistants without "
                                "explicit owner approval."
                            ),
                        }
                    )
            if content:
                parsed = _parse_langgraph_json(content)
                graphs = (parsed or {}).get("graphs")
                if isinstance(graphs, dict) and aid not in graphs:
                    findings.append(
                        {
                            "check": "contracts",
                            "severity": "error",
                            "path": "langgraph.json",
                            "uid": aid,
                            "message": (
                                f'Baseline assistant_id "{aid}" missing '
                                "from registry"
                            ),
                            "fix": (
                                f'Keep "{aid}" registered or get owner '
                                "approval to break the gssc5 contract."
                            ),
                        }
                    )

    if any(f["path"] == "README.md" and f["status"] == "deleted" for f in cs["files"]):
        findings.append(
            {
                "check": "contracts",
                "severity": "error",
                "path": "README.md",
                "message": "README deleted — would silently drop gssc5 contract docs",
                "fix": "Restore README; update docs in place instead of deleting.",
            }
        )

    if cs.get("label") == "workspace":
        lg = _file_by_path(cs, "langgraph.json")
        parsed = _parse_langgraph_json(lg.get("content") or "") if lg else None
        graphs = (parsed or {}).get("graphs") if parsed else None
        if isinstance(graphs, dict):
            for aid in BASELINE_ASSISTANT_IDS:
                if aid not in graphs:
                    findings.append(
                        {
                            "check": "contracts",
                            "severity": "error",
                            "path": "langgraph.json",
                            "uid": aid,
                            "message": (
                                f'Baseline assistant_id "{aid}" missing '
                                "from workspace registry"
                            ),
                            "fix": f'Register "{aid}" in langgraph.json.',
                        }
                    )

    return findings


def check_software_trace(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []
    lg = _file_by_path(cs, "langgraph.json")
    raw = (lg.get("content") or "") if lg else ""
    parsed = _parse_langgraph_json(raw) if raw else None
    graphs = (parsed or {}).get("graphs") if parsed else None

    if lg and lg.get("status") == "deleted":
        findings.append(
            {
                "check": "software_trace",
                "severity": "error",
                "path": "langgraph.json",
                "message": "langgraph.json was deleted",
                "fix": "Restore langgraph.json and register all shipped graphs.",
            }
        )
        return findings

    for gid in _changed_graph_ids(cs):
        candidates = _graph_paths(gid)
        added = any(
            f["path"] in candidates and f["status"] == "added" for f in cs["files"]
        )
        if not added:
            continue
        graph_path = next(
            (p for p in candidates if any(f["path"] == p for f in cs["files"])),
            _primary_graph_path(gid),
        )
        if isinstance(graphs, dict) and gid not in graphs:
            findings.append(
                {
                    "check": "software_trace",
                    "severity": "error",
                    "path": graph_path,
                    "uid": gid,
                    "message": (
                        f'New assistant "{gid}" is not registered in langgraph.json'
                    ),
                    "fix": (
                        f'Add "{gid}": "./{graph_path}:graph" '
                        "(gssc5 software-trace analogue)."
                    ),
                }
            )
        readme = _file_by_path(cs, "README.md")
        readme_text = _text_of(readme)
        if (
            readme
            and readme.get("status") != "deleted"
            and readme_text
            and gid not in readme_text
        ):
            findings.append(
                {
                    "check": "software_trace",
                    "severity": "warning",
                    "path": "README.md",
                    "uid": gid,
                    "message": f'New assistant "{gid}" is not mentioned in README',
                    "fix": (
                        "Document the assistant id and input shape for "
                        "gssc5 consumers."
                    ),
                }
            )
        elif not readme_text and added:
            findings.append(
                {
                    "check": "software_trace",
                    "severity": "info",
                    "path": "README.md",
                    "uid": gid,
                    "message": (
                        "README not in change set — cannot verify docs for "
                        f'new assistant "{gid}"'
                    ),
                    "fix": "Include README.md when adding assistants, or run --workspace.",
                }
            )

    if cs.get("label") == "workspace" and isinstance(graphs, dict):
        for gid in _graph_dirs_from_files(cs):
            if gid not in graphs:
                findings.append(
                    {
                        "check": "software_trace",
                        "severity": "error",
                        "path": _primary_graph_path(gid),
                        "uid": gid,
                        "message": (
                            f'Graph "{gid}" exists on disk but is not registered'
                        ),
                        "fix": f'Register "{gid}" in langgraph.json.',
                    }
                )
        for gid, entry in graphs.items():
            on_disk = any(
                f["path"] in _graph_paths(str(gid)) and f["status"] != "deleted"
                for f in cs["files"]
            )
            if not on_disk:
                findings.append(
                    {
                        "check": "software_trace",
                        "severity": "error",
                        "path": "langgraph.json",
                        "uid": str(gid),
                        "message": (
                            f'Registry entry "{gid}" → {entry} has no matching '
                            "graph file in workspace"
                        ),
                        "fix": (
                            f"Add {_primary_graph_path(str(gid))} or remove the "
                            "orphan registry entry."
                        ),
                    }
                )
    elif not raw and any(GRAPH_FILE_RE.match(f["path"]) for f in cs["files"]):
        findings.append(
            {
                "check": "software_trace",
                "severity": "warning",
                "path": "langgraph.json",
                "message": (
                    "Graph files changed but langgraph.json content was not "
                    "in the change set"
                ),
                "fix": (
                    "Include langgraph.json when adding/renaming graphs, "
                    "or run --workspace."
                ),
            }
        )

    return findings


def check_software_match(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []
    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if not m or f["status"] == "deleted":
            continue
        body = f.get("content") or ""
        if not body:
            continue
        gid = m.group(1)
        has_compile = bool(COMPILE_RE.search(body))
        if "StateGraph" not in body or not has_compile:
            findings.append(
                {
                    "check": "software_match",
                    "severity": "error",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Graph "{gid}" does not look like a compiled '
                        "StateGraph assistant"
                    ),
                    "fix": (
                        "Use StateGraph + compile()/compile_with_memory and "
                        "assign graph = … like health/conversation."
                    ),
                }
            )
        if not GRAPH_EXPORT_RE.search(body):
            findings.append(
                {
                    "check": "software_match",
                    "severity": "error",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Graph "{gid}" must assign compiled `graph` for '
                        "Agent Server"
                    ),
                    "fix": "graph = builder.compile()  # or compile_with_memory(...)",
                }
            )
        if "StateGraph" in body and not ADD_NODE_RE.search(body):
            findings.append(
                {
                    "check": "software_match",
                    "severity": "warning",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Graph "{gid}" has no nodes — likely does not '
                        "realize intended behavior"
                    ),
                    "fix": (
                        "Add at least one node that implements the closeout / "
                        "domain behavior."
                    ),
                }
            )
    return findings


def check_software_quality(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []
    model_free = set(MODEL_FREE_ASSISTANT_IDS)

    for f in cs["files"]:
        m = GRAPH_FILE_RE.match(f["path"])
        if not m or f["status"] == "deleted":
            continue
        body = f.get("content") or ""
        if not body:
            continue
        gid = m.group(1)
        lines = body.count("\n") + 1

        if lines > GRAPH_GOD_FILE_LINES:
            findings.append(
                {
                    "check": "software_quality",
                    "severity": "warning",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Graph module "{gid}" is large ({lines} lines) — '
                        "risk of god file"
                    ),
                    "fix": (
                        "Split checks/helpers into sibling modules under "
                        "src/gssc_langgraph/<domain>/."
                    ),
                }
            )

        if EMPTY_CATCH_RE.search(body):
            findings.append(
                {
                    "check": "software_quality",
                    "severity": "warning",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Empty catch in "{gid}" — prefer fail-fast or '
                        "explicit handling"
                    ),
                    "fix": (
                        "Surface errors or rethrow; do not swallow failures "
                        "silently."
                    ),
                }
            )

        if not GRAPH_NAME_RE.search(body):
            findings.append(
                {
                    "check": "software_quality",
                    "severity": "warning",
                    "path": f["path"],
                    "uid": gid,
                    "message": f'Graph "{gid}" does not set graph.name',
                    "fix": (
                        'Set graph.name = "…" or '
                        "compile_with_memory(builder, name=…)."
                    ),
                }
            )

        if gid in model_free and _uses_chat_model(body):
            findings.append(
                {
                    "check": "software_quality",
                    "severity": "error",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Smoke/tooling assistant "{gid}" should stay model-free'
                    ),
                    "fix": (
                        "Keep closeout/smoke assistants free of LLM nodes, "
                        "or add a separate domain graph."
                    ),
                }
            )
    return findings


def check_third_party(cs: ChangeSet) -> list[CloseoutFinding]:
    """Python+uv + LangGraph Agent Server first; flag reinvented HTTP / Bun-only."""
    findings: list[CloseoutFinding] = []

    for f in cs["files"]:
        if f["status"] == "deleted":
            continue
        body = _text_of(f)
        path = f["path"]

        if (
            (path.startswith("src/") or path in ("package.json", "pyproject.toml"))
            and body
            and path not in CRITERIA_EXCLUDE
        ):
            for hint in REINVENTED_SERVER_HINTS:
                if hint.search(body):
                    findings.append(
                        {
                            "check": "third_party",
                            "severity": "warning",
                            "path": path,
                            "message": (
                                "Custom HTTP framework detected — prefer the "
                                "official langgraph CLI Agent Server "
                                "(third-party-first)"
                            ),
                            "fix": (
                                "Serve via `langgraph dev` / langgraph CLI "
                                "unless the owner approved a custom server."
                            ),
                        }
                    )
                    break

    pyproject = _file_by_path(cs, "pyproject.toml")
    pyproject_text = (pyproject.get("content") or "") if pyproject else ""
    pkg = _file_by_path(cs, "package.json")
    pkg_text = (pkg.get("content") or "") if pkg else ""

    if pyproject_text:
        if not _has_langgraph_dep(pyproject_text):
            findings.append(
                {
                    "check": "third_party",
                    "severity": "error",
                    "path": "pyproject.toml",
                    "message": "Missing adopted langgraph dependency in pyproject.toml",
                    "fix": "Add langgraph (and prefer uv for packaging).",
                }
            )
    else:
        # Require Python packaging when reviewing a workspace / packaging surface.
        packaging_in_scope = any(
            f["path"]
            in (
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "langgraph.json",
            )
            or f["path"].startswith("src/")
            for f in cs["files"]
        )
        if packaging_in_scope and (
            cs.get("label") == "workspace" or pkg_text or any(
                f["path"].endswith(".py") for f in cs["files"]
            )
        ):
            findings.append(
                {
                    "check": "third_party",
                    "severity": "error",
                    "path": "pyproject.toml",
                    "message": "Missing pyproject.toml — Python+uv is the required stack",
                    "fix": "Add pyproject.toml with a langgraph dependency; prefer uv.",
                }
            )

    # Leftover Bun/TS as the only packaging story.
    if pkg_text and not pyproject_text:
        bun_only = bool(re.search(r'"packageManager"\s*:\s*"bun@', pkg_text))
        findings.append(
            {
                "check": "third_party",
                "severity": "error" if bun_only else "warning",
                "path": "package.json",
                "message": (
                    "package.json is the only packaging — leftover Bun/TS "
                    "primary stack; prefer Python+uv"
                    if bun_only
                    else "package.json present without pyproject.toml — "
                    "prefer Python+uv as primary packaging"
                ),
                "fix": (
                    "Add pyproject.toml with langgraph; use uv. Do not keep "
                    "Bun as the sole package manager."
                ),
            }
        )
    elif pkg_text and pyproject_text:
        if re.search(r'"packageManager"\s*:\s*"bun@', pkg_text):
            findings.append(
                {
                    "check": "third_party",
                    "severity": "warning",
                    "path": "package.json",
                    "message": (
                        "Leftover Bun packageManager alongside pyproject — "
                        "prefer Python+uv"
                    ),
                    "fix": (
                        "Migrate scripts/tooling to uv/pytest; drop Bun as "
                        "primary packageManager."
                    ),
                }
            )

    return findings


def check_test_coverage(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []
    ids = (
        _graph_dirs_from_files(cs)
        if cs.get("label") == "workspace"
        else _changed_graph_ids(cs)
    )
    changed = _changed_graph_ids(cs)

    for gid in ids:
        if _has_test_touching(cs, gid):
            continue
        any_tests = any(TEST_FILE_RE.match(f["path"]) for f in cs["files"])
        if cs.get("label") == "workspace" or any_tests or gid in changed:
            findings.append(
                {
                    "check": "test_coverage",
                    "severity": "error" if cs.get("label") == "workspace" else "warning",
                    "path": _primary_graph_path(gid),
                    "uid": gid,
                    "message": (
                        f'No pytest coverage found for graph "{gid}" in the '
                        "change set"
                    ),
                    "fix": (
                        f"Add or include tests/test_{gid}.py (or tests/**/*.py) "
                        f"that imports/invokes graphs/{gid} "
                        "(test-closeout Trace analogue)."
                    ),
                }
            )
    return findings


def check_test_target(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []

    for f in cs["files"]:
        if not TEST_FILE_RE.match(f["path"]) or f["status"] == "deleted":
            continue
        body = f.get("content") or ""
        if not body:
            continue

        if not re.search(r"\bassert\b", body) and not re.search(
            r"\bexpect\s*\(", body
        ):
            findings.append(
                {
                    "check": "test_target",
                    "severity": "warning",
                    "path": f["path"],
                    "message": (
                        "Test file has no assert / expect(…) — may not lock "
                        "a contract"
                    ),
                    "fix": (
                        "Assert documented contract behavior "
                        "(status/reply/steps), not incidental SW."
                    ),
                }
            )
        if re.search(r"(?m)^\s*assert\s+True\b", body) or re.search(
            r"expect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)", body
        ):
            findings.append(
                {
                    "check": "test_target",
                    "severity": "warning",
                    "path": f["path"],
                    "message": (
                        "Tautological assert True / expect(true).toBe(true) — "
                        "does not validate a contract"
                    ),
                    "fix": "Assert the documented contract verb/status/body.",
                }
            )

    touched_graphs = _changed_graph_ids(cs)
    if touched_graphs:
        deleted_tests = [
            f
            for f in cs["files"]
            if TEST_FILE_RE.match(f["path"]) and f["status"] == "deleted"
        ]
        for t in deleted_tests:
            body = f"{t.get('patch') or ''}\n{t.get('content') or ''}"
            covers = any(
                f"graphs/{gid}/" in body
                or f'"{gid}"' in body
                or gid.replace("_", " ").lower() in body.lower()
                for gid in touched_graphs
            )
            if covers:
                findings.append(
                    {
                        "check": "test_target",
                        "severity": "error",
                        "path": t["path"],
                        "message": (
                            "Deleting tests that cover changed software — do "
                            "not “fix” by removing coverage (ask if SW vs "
                            "contracts conflict)"
                        ),
                        "fix": (
                            "Restore or rewrite tests to assert the intended "
                            "contract; peer with test_development for test "
                            "planning."
                        ),
                    }
                )
            elif not body.strip():
                findings.append(
                    {
                        "check": "test_target",
                        "severity": "warning",
                        "path": t["path"],
                        "message": (
                            "Test file deleted while graphs changed — confirm "
                            "it was not covering the SW under edit"
                        ),
                        "fix": (
                            "Include the deleted test contents in the change "
                            "set, or restore coverage."
                        ),
                    }
                )

    return findings


def check_secrets(cs: ChangeSet) -> list[CloseoutFinding]:
    findings: list[CloseoutFinding] = []
    skip_paths = frozenset(
        {
            "bun.lock",
            "src/closeout/criteria.ts",
            "src/review/criteria.ts",
            "src/gssc_langgraph/closeout/criteria.py",
            "src/gssc_langgraph/review/criteria.py",
        }
    )

    for f in cs["files"]:
        if f["status"] == "deleted":
            continue
        body = _text_of(f)
        if not body:
            continue
        path = f["path"]

        if path == ".env.example":
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(body):
                    findings.append(
                        {
                            "check": "secrets",
                            "severity": "error",
                            "path": path,
                            "message": (
                                f".env.example looks like it contains a real {name}"
                            ),
                            "fix": (
                                "Keep placeholders empty or clearly fake "
                                "(e.g. xai-… truncated)."
                            ),
                        }
                    )
            continue

        if path.endswith(".lock") or path in skip_paths:
            continue

        for name, pattern in SECRET_PATTERNS:
            if pattern.search(body):
                findings.append(
                    {
                        "check": "secrets",
                        "severity": "error",
                        "path": path,
                        "message": f"Possible committed secret ({name})",
                        "fix": (
                            "Remove the secret; use .env (gitignored) and "
                            "placeholders in .env.example."
                        ),
                    }
                )
                break

    return findings


CHECK_RUNNERS: dict[
    CloseoutCheckId, Callable[[ChangeSet | None], list[CloseoutFinding]]
] = {
    "scope": check_scope,
    "contracts": lambda cs: check_contracts(cs) if cs else [],
    "software_trace": lambda cs: check_software_trace(cs) if cs else [],
    "software_match": lambda cs: check_software_match(cs) if cs else [],
    "software_quality": lambda cs: check_software_quality(cs) if cs else [],
    "third_party": lambda cs: check_third_party(cs) if cs else [],
    "test_coverage": lambda cs: check_test_coverage(cs) if cs else [],
    "test_target": lambda cs: check_test_target(cs) if cs else [],
    "secrets": lambda cs: check_secrets(cs) if cs else [],
}


def verdict_from(findings: list[CloseoutFinding]) -> CloseoutVerdict:
    return "FAIL" if any(f["severity"] == "error" for f in findings) else "PASS"


def summarize(verdict: CloseoutVerdict, findings: list[CloseoutFinding]) -> str:
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    if verdict == "PASS" and warnings == 0:
        return "PASS — closeout review clean."
    if verdict == "PASS":
        return f"PASS with {warnings} warning(s)."
    return f"FAIL — {errors} error(s), {warnings} warning(s)."


def run_all_checks(cs: ChangeSet | None) -> tuple[
    CloseoutVerdict, str, list[CloseoutFinding], list[CloseoutCheckId]
]:
    findings: list[CloseoutFinding] = []
    checks_run: list[CloseoutCheckId] = []
    for check_id, runner in CHECK_RUNNERS.items():
        checks_run.append(check_id)
        findings.extend(runner(cs))
    verdict = verdict_from(findings)
    return verdict, summarize(verdict, findings), findings, checks_run
