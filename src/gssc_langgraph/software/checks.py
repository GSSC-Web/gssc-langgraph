"""Deterministic software_dev checks (Python LangGraph stack policy)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from gssc_langgraph.software.criteria import (
    BASELINE_ASSISTANT_IDS,
    GRAPH_GOD_FILE_LINES,
    REINVENTED_SERVER_HINTS,
)
from gssc_langgraph.software.types import (
    ChangeSet,
    ChangedFile,
    SoftwareCheckId,
    SoftwareFinding,
    SoftwareVerdict,
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
        "src/software/criteria.ts",
        "src/gssc_langgraph/software/criteria.py",
        "src/gssc_langgraph/closeout/criteria.py",
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


def _has_langgraph_dep(text: str) -> bool:
    return bool(
        re.search(r"(?m)^\s*[\"']langgraph[\"']\s*[=~<>]", text)
        or re.search(r"(?m)^\s*langgraph\s*[=~<>\[]", text)
        or re.search(r"(?i)\blanggraph\b", text)
    )


def check_scope(goal: str, cs: ChangeSet | None) -> list[SoftwareFinding]:
    findings: list[SoftwareFinding] = []
    has_goal = bool(goal.strip())
    has_files = bool(cs and cs.get("files"))
    if not has_goal and not has_files:
        findings.append(
            {
                "check": "scope",
                "severity": "error",
                "message": (
                    "No development goal and no change set — nothing to "
                    "implement or close out"
                ),
                "fix": (
                    'Pass --goal "…" and/or a git range / --workspace / --diff.'
                ),
            }
        )
        return findings
    if not has_goal:
        findings.append(
            {
                "check": "scope",
                "severity": "info",
                "message": (
                    "No free-text goal; running software closeout against "
                    "the change set only"
                ),
            }
        )
    if has_goal and len(goal.strip()) < 8:
        findings.append(
            {
                "check": "scope",
                "severity": "warning",
                "message": (
                    "Goal is very short — prefer a concrete LLR/task-style "
                    "statement"
                ),
                "fix": (
                    '--goal "Add software_dev assistant that plans LangGraph '
                    'graph changes".'
                ),
            }
        )
    return findings


def check_trace(cs: ChangeSet) -> list[SoftwareFinding]:
    findings: list[SoftwareFinding] = []
    lg = _file_by_path(cs, "langgraph.json")
    raw = (lg.get("content") or "") if lg else ""
    parsed = _parse_langgraph_json(raw) if raw else None
    graphs = (parsed or {}).get("graphs") if parsed else None

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
                    "check": "trace",
                    "severity": "error",
                    "path": graph_path,
                    "uid": gid,
                    "message": (
                        f'New assistant "{gid}" is not registered in langgraph.json'
                    ),
                    "fix": (
                        f'Add "{gid}": "./{graph_path}:graph" '
                        "(gssc5 software trace analogue)."
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
                    "check": "trace",
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
                    "check": "trace",
                    "severity": "info",
                    "path": "README.md",
                    "uid": gid,
                    "message": (
                        "README not in change set — cannot verify docs for "
                        f'new assistant "{gid}"'
                    ),
                    "fix": (
                        "Include README.md when adding assistants, or run "
                        "--workspace."
                    ),
                }
            )

    if cs.get("label") == "workspace" and isinstance(graphs, dict):
        for gid in _graph_dirs_from_files(cs):
            if gid not in graphs:
                findings.append(
                    {
                        "check": "trace",
                        "severity": "error",
                        "path": _primary_graph_path(gid),
                        "uid": gid,
                        "message": (
                            f'Graph "{gid}" exists on disk but is not registered'
                        ),
                        "fix": f'Register "{gid}" in langgraph.json.',
                    }
                )

    return findings


def check_match(cs: ChangeSet) -> list[SoftwareFinding]:
    findings: list[SoftwareFinding] = []
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
                    "check": "match",
                    "severity": "error",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Graph "{gid}" does not look like a compiled '
                        "StateGraph assistant"
                    ),
                    "fix": (
                        "Use StateGraph + compile()/compile_with_memory like "
                        "health."
                    ),
                }
            )
        if not GRAPH_EXPORT_RE.search(body):
            findings.append(
                {
                    "check": "match",
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
                    "check": "match",
                    "severity": "warning",
                    "path": f["path"],
                    "uid": gid,
                    "message": (
                        f'Graph "{gid}" has no nodes — likely does not '
                        "realize intended behavior"
                    ),
                    "fix": "Add at least one node that implements the goal.",
                }
            )
    return findings


def check_quality(cs: ChangeSet) -> list[SoftwareFinding]:
    findings: list[SoftwareFinding] = []
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
                    "check": "quality",
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
                    "check": "quality",
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
                    "check": "quality",
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

        if gid in ("health", "conversation") and CHAT_MODEL_RE.search(body):
            findings.append(
                {
                    "check": "quality",
                    "severity": "error",
                    "path": f["path"],
                    "uid": gid,
                    "message": f'Smoke assistant "{gid}" should stay model-free',
                    "fix": (
                        "Keep health/conversation free of LLM nodes, or add "
                        "a separate domain graph."
                    ),
                }
            )
    return findings


def check_third_party(cs: ChangeSet) -> list[SoftwareFinding]:
    findings: list[SoftwareFinding] = []

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
            cs.get("label") == "workspace"
            or pkg_text
            or any(f["path"].endswith(".py") for f in cs["files"])
        ):
            findings.append(
                {
                    "check": "third_party",
                    "severity": "error",
                    "path": "pyproject.toml",
                    "message": (
                        "Missing pyproject.toml — Python+uv is the required stack"
                    ),
                    "fix": (
                        "Add pyproject.toml with a langgraph dependency; prefer uv."
                    ),
                }
            )

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


def check_discipline(cs: ChangeSet) -> list[SoftwareFinding]:
    findings: list[SoftwareFinding] = []

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
                            "check": "discipline",
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
                            "check": "discipline",
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
                        "check": "discipline",
                        "severity": "error",
                        "path": t["path"],
                        "message": (
                            "Deleting tests that cover changed software — do "
                            "not “fix” by removing coverage (ask if SW vs "
                            "requirements conflict)"
                        ),
                        "fix": (
                            "Restore or rewrite tests to assert the intended "
                            "contract; peer with test_dev for test closeout."
                        ),
                    }
                )
            elif not body.strip():
                findings.append(
                    {
                        "check": "discipline",
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

    if any(f["path"] == "README.md" and f["status"] == "deleted" for f in cs["files"]):
        findings.append(
            {
                "check": "discipline",
                "severity": "error",
                "path": "README.md",
                "message": "README deleted — would silently drop gssc5 contract docs",
                "fix": "Restore README; update docs in place instead of deleting.",
            }
        )

    return findings


CHECK_RUNNERS: dict[
    SoftwareCheckId, Callable[[str, ChangeSet | None], list[SoftwareFinding]]
] = {
    "scope": check_scope,
    "trace": lambda _goal, cs: check_trace(cs) if cs else [],
    "match": lambda _goal, cs: check_match(cs) if cs else [],
    "quality": lambda _goal, cs: check_quality(cs) if cs else [],
    "third_party": lambda _goal, cs: check_third_party(cs) if cs else [],
    "discipline": lambda _goal, cs: check_discipline(cs) if cs else [],
}


def verdict_from(findings: list[SoftwareFinding]) -> SoftwareVerdict:
    return "FAIL" if any(f["severity"] == "error" for f in findings) else "PASS"


def summarize(
    verdict: SoftwareVerdict,
    findings: list[SoftwareFinding],
    plan_count: int,
) -> str:
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    plan_bit = f"{plan_count} plan step(s)"
    if verdict == "PASS" and warnings == 0:
        return f"PASS — {plan_bit}, no findings."
    if verdict == "PASS":
        return f"PASS with {warnings} warning(s) — {plan_bit}."
    return f"FAIL — {errors} error(s), {warnings} warning(s) — {plan_bit}."


def run_all_checks(
    goal: str, cs: ChangeSet | None
) -> tuple[SoftwareVerdict, list[SoftwareFinding], list[SoftwareCheckId]]:
    findings: list[SoftwareFinding] = []
    checks_run: list[SoftwareCheckId] = []
    for check_id, runner in CHECK_RUNNERS.items():
        checks_run.append(check_id)
        findings.extend(runner(goal, cs))
    return verdict_from(findings), findings, checks_run
