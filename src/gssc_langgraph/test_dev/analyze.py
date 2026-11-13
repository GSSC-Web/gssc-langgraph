"""
Test-development analyzers (model-free).

Mirrors gssc5 test-closeout-review steps: scope → map → target → asserts →
timing → verdict — without StrictDoc @relation markers. Prefers pytest.
"""

from __future__ import annotations

import re

from gssc_langgraph.test_dev.contracts import (
    BASELINE_CONTRACTS,
    TOOLING_GRAPH_IDS,
    changed_graph_ids,
    graph_ids_from_change_set,
    resolve_contracts,
)
from gssc_langgraph.test_dev.criteria import CONFLICT_GUIDANCE
from gssc_langgraph.test_dev.types import (
    ChangeSet,
    Contract,
    CoverageLink,
    Finding,
    PlanItem,
    TestDevCheckId,
    TestDevVerdict,
)

TEST_FILE_RE = re.compile(r"^tests/.+\.py$")


def _text_of(cs: ChangeSet, path: str) -> str:
    for f in cs["files"]:
        if f["path"] == path:
            return f.get("content") or ""
    return ""


def _test_files(cs: ChangeSet) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for f in cs["files"]:
        if TEST_FILE_RE.match(f["path"]) and f["status"] != "deleted":
            out.append({"path": f["path"], "body": f.get("content") or ""})
    return out


def _mentions_graph(body: str, graph_id: str) -> bool:
    spaced = graph_id.replace("_", " ")
    return (
        f"src/gssc_langgraph/graphs/{graph_id}/" in body
        or f"src/graphs/{graph_id}/" in body
        or f"graphs/{graph_id}/" in body
        or f'"{graph_id}"' in body
        or f"'{graph_id}'" in body
        or spaced.lower() in body.lower()
    )


def _hints_covered(body: str, hints: list[str]) -> int:
    lower = body.lower()
    return sum(1 for h in hints if h.lower() in lower)


def _primary_graph_path(graph_id: str) -> str:
    return f"src/gssc_langgraph/graphs/{graph_id}/graph.py"


def resolve_scope(cs: ChangeSet) -> tuple[list[str], list[Finding]]:
    findings: list[Finding] = []
    changed = changed_graph_ids(cs)
    all_ids = graph_ids_from_change_set(cs)
    label = cs.get("label") or ""

    if label == "workspace" or label.startswith("workspace"):
        graph_ids = all_ids
    elif changed:
        graph_ids = changed
    else:
        touched_tests = []
        for t in _test_files(cs):
            f = next((x for x in cs["files"] if x["path"] == t["path"]), None)
            if f and f["status"] != "unchanged":
                touched_tests.append(t)
        mentioned: set[str] = set()
        for t in touched_tests:
            for gid in all_ids:
                if _mentions_graph(t["body"], gid):
                    mentioned.add(gid)
        if mentioned:
            graph_ids = sorted(mentioned)
        else:
            graph_ids = [
                gid
                for gid in all_ids
                if any(c["graphId"] == gid for c in BASELINE_CONTRACTS)
                or gid in TOOLING_GRAPH_IDS
            ]
            if not graph_ids:
                graph_ids = all_ids

    if not graph_ids:
        findings.append(
            {
                "check": "scope",
                "severity": "warning",
                "message": "No graphs in scope for test development",
                "fix": (
                    "Pass --workspace, a diff that touches graphs, or "
                    "explicit paths."
                ),
            }
        )

    return graph_ids, findings


def map_coverage(
    cs: ChangeSet, contracts: list[Contract]
) -> tuple[list[CoverageLink], list[Finding]]:
    findings: list[Finding] = []
    tests = _test_files(cs)
    coverage: list[CoverageLink] = []

    for c in contracts:
        candidates = [t for t in tests if _mentions_graph(t["body"], c["graphId"])]
        best: dict[str, object] | None = None
        for t in candidates:
            score = _hints_covered(t["body"], c["assertHints"])
            if best is None or score > int(best["score"]):
                best = {"path": t["path"], "score": score}

        covered = bool(best and int(best["score"]) > 0)
        if covered and best:
            notes = (
                f"Matched {best['score']}/{len(c['assertHints'])} assert "
                f"hints in {best['path']}"
            )
        elif candidates:
            notes = (
                f'Tests mention graph "{c["graphId"]}" but miss contract '
                "assert hints"
            )
        else:
            notes = f'No test file references graph "{c["graphId"]}"'

        link: CoverageLink = {
            "contractId": c["id"],
            "graphId": c["graphId"],
            "covered": covered,
            "notes": notes,
        }
        if best:
            link["testPath"] = str(best["path"])
        coverage.append(link)

        if not covered:
            findings.append(
                {
                    "check": "coverage_map",
                    "severity": "error",
                    "path": str(best["path"]) if best else _primary_graph_path(c["graphId"]),
                    "graphId": c["graphId"],
                    "contractId": c["id"],
                    "message": f'Contract "{c["id"]}" has no permanent test locking it',
                    "fix": f"Add a pytest that asserts: {c['requirement']}",
                }
            )

    return coverage, findings


def check_target(
    cs: ChangeSet,
    contracts: list[Contract],
    coverage: list[CoverageLink],
) -> list[Finding]:
    findings: list[Finding] = []
    tests = _test_files(cs)

    for t in tests:
        related = [c for c in contracts if _mentions_graph(t["body"], c["graphId"])]
        if not related:
            continue

        has_contract_assert = any(
            _hints_covered(t["body"], c["assertHints"]) > 0 for c in related
        )
        only_smoke = (
            bool(re.search(r"\bis\s+not\s+None\b|\btoBeDefined\s*\(", t["body"]))
            and not has_contract_assert
            and any(c["source"] == "baseline" for c in related)
        )
        if only_smoke:
            findings.append(
                {
                    "check": "target",
                    "severity": "warning",
                    "path": t["path"],
                    "message": (
                        "Test looks like compile-only smoke without asserting "
                        "documented contract behavior"
                    ),
                    "fix": (
                        f"Assert the requirement (e.g. {related[0]['requirement']}). "
                        f"{CONFLICT_GUIDANCE}"
                    ),
                }
            )

        if re.search(
            r"whatever (the )?software|match(es)? current (impl|behavior)|"
            r"snapshot of sw",
            t["body"],
            re.IGNORECASE,
        ):
            findings.append(
                {
                    "check": "target",
                    "severity": "error",
                    "path": t["path"],
                    "message": (
                        "Test comments suggest asserting current software "
                        "instead of the documented contract"
                    ),
                    "fix": CONFLICT_GUIDANCE,
                }
            )

    for link in coverage:
        if not link["covered"] or not link.get("testPath"):
            continue
        c = next((x for x in contracts if x["id"] == link["contractId"]), None)
        if not c or c["source"] != "baseline":
            continue
        body = _text_of(cs, link["testPath"])
        if body and not re.search(r"\.invoke\s*\(", body) and not re.search(
            r"\bassert\b|\bexpect\s*\(", body
        ):
            findings.append(
                {
                    "check": "target",
                    "severity": "error",
                    "path": link["testPath"],
                    "graphId": c["graphId"],
                    "contractId": c["id"],
                    "message": (
                        f'Covering file for "{c["id"]}" does not invoke the '
                        "graph or assert outcomes"
                    ),
                    "fix": "Use graph.invoke(...) and assert against the contract.",
                }
            )

    return findings


def check_asserts(
    cs: ChangeSet,
    contracts: list[Contract],
    coverage: list[CoverageLink],
) -> list[Finding]:
    findings: list[Finding] = []

    for link in coverage:
        if not link["covered"] or not link.get("testPath"):
            continue
        c = next((x for x in contracts if x["id"] == link["contractId"]), None)
        if not c:
            continue
        body = _text_of(cs, link["testPath"])
        if not body:
            continue

        hit = _hints_covered(body, c["assertHints"])
        needed = min(2, len(c["assertHints"]))
        if hit < needed and c["source"] == "baseline":
            findings.append(
                {
                    "check": "asserts",
                    "severity": "error",
                    "path": link["testPath"],
                    "graphId": c["graphId"],
                    "contractId": c["id"],
                    "message": (
                        f'Baseline contract "{c["id"]}" is weakly asserted '
                        f"({hit}/{len(c['assertHints'])} hints)"
                    ),
                    "fix": (
                        f"Assert behavior from the contract verb: "
                        f"{c['requirement']}"
                    ),
                }
            )

        if re.search(r"(?m)^\s*assert\s+True\b", body) or re.search(
            r"expect\s*\(\s*true\s*\)", body
        ):
            findings.append(
                {
                    "check": "asserts",
                    "severity": "error",
                    "path": link["testPath"],
                    "message": "Tautological or empty assert/expect found",
                    "fix": "Replace with asserts derived from the contract.",
                }
            )

    return findings


def check_timing(
    cs: ChangeSet, scope_graph_ids: list[str]
) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    commands: list[str] = []
    tests = _test_files(cs)

    focused_files: set[str] = set()
    for gid in scope_graph_ids:
        for t in tests:
            if _mentions_graph(t["body"], gid):
                focused_files.add(t["path"])

    if not focused_files:
        for gid in scope_graph_ids:
            commands.append(f"uv run pytest tests/test_{gid}.py")
    else:
        for path in sorted(focused_files):
            commands.append(f"uv run pytest {path}")

    for t in tests:
        if re.search(r"playwright|puppeteer|selenium|cypress", t["body"], re.I) and any(
            _mentions_graph(t["body"], gid) for gid in scope_graph_ids
        ):
            findings.append(
                {
                    "check": "timing",
                    "severity": "warning",
                    "path": t["path"],
                    "message": (
                        "Browser/E2E harness detected for a LangGraph unit "
                        "contract — prefer graph.invoke in pytest"
                    ),
                    "fix": (
                        "Keep permanent contract tests unit-level; reserve E2E "
                        "for explicit integration tasks."
                    ),
                }
            )

    if len(commands) > 1:
        files = sorted(focused_files)
        if len(files) > 1:
            commands.insert(0, f"uv run pytest {' '.join(files)}")

    return findings, commands


def build_plan(
    contracts: list[Contract],
    coverage: list[CoverageLink],
    findings: list[Finding],
    commands: list[str],
) -> list[PlanItem]:
    plan: list[PlanItem] = []

    for link in coverage:
        if link["covered"]:
            continue
        c = next((x for x in contracts if x["id"] == link["contractId"]), None)
        if not c:
            continue
        test_path = f"tests/test_{c['graphId']}.py"
        plan.append(
            {
                "action": "add_test",
                "graphId": c["graphId"],
                "contractId": c["id"],
                "path": test_path,
                "description": f"Add permanent test for {c['id']}: {c['requirement']}",
                "suggestedTest": _suggest_test_stub(c),
            }
        )

    for f in findings:
        if f["check"] == "asserts" and f.get("contractId") and f.get("path"):
            item: PlanItem = {
                "action": "add_assert",
                "description": f["message"],
                "path": f["path"],
            }
            if f.get("graphId"):
                item["graphId"] = f["graphId"]
            if f.get("contractId"):
                item["contractId"] = f["contractId"]
            plan.append(item)
        if f["check"] == "target" and f["severity"] == "error":
            ask: PlanItem = {"action": "ask_owner", "description": f["message"]}
            if f.get("graphId"):
                ask["graphId"] = f["graphId"]
            if f.get("contractId"):
                ask["contractId"] = f["contractId"]
            if f.get("path"):
                ask["path"] = f["path"]
            plan.append(ask)

    for cmd in commands[:3]:
        plan.append(
            {
                "action": "run_focused",
                "description": f"Prefer focused harness: {cmd}",
            }
        )

    return plan


def _suggest_test_stub(c: Contract) -> str:
    hints = "\n".join(f"    # assert: {h}" for h in c["assertHints"])
    module = c["graphId"]
    return f'''import pytest

from gssc_langgraph.graphs.{module}.graph import graph


def test_{c["id"].replace(".", "_")}():
    """Contract: {c["requirement"]}"""
    result = graph.invoke({{}})
{hints}
    assert result is not None
'''


def run_analysis(cs: ChangeSet) -> dict[str, object]:
    checks_run: list[TestDevCheckId] = []
    findings: list[Finding] = []

    graph_ids, scope_findings = resolve_scope(cs)
    checks_run.append("scope")
    findings.extend(scope_findings)

    contracts = resolve_contracts(cs, graph_ids)

    coverage, cov_findings = map_coverage(cs, contracts)
    checks_run.append("coverage_map")
    findings.extend(cov_findings)

    target_findings = check_target(cs, contracts, coverage)
    checks_run.append("target")
    findings.extend(target_findings)

    assert_findings = check_asserts(cs, contracts, coverage)
    checks_run.append("asserts")
    findings.extend(assert_findings)

    timing_findings, commands = check_timing(cs, graph_ids)
    checks_run.append("timing")
    findings.extend(timing_findings)

    plan = build_plan(contracts, coverage, findings, commands)

    return {
        "scopeGraphIds": graph_ids,
        "contracts": contracts,
        "coverage": coverage,
        "findings": findings,
        "checksRun": checks_run,
        "plan": plan,
        "commands": commands,
    }


def verdict_from(findings: list[Finding]) -> TestDevVerdict:
    return "FAIL" if any(f["severity"] == "error" for f in findings) else "PASS"


def summarize(
    verdict: TestDevVerdict,
    findings: list[Finding],
    plan: list[PlanItem],
) -> str:
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    adds = sum(1 for p in plan if p["action"] == "add_test")
    if verdict == "PASS" and warnings == 0 and adds == 0:
        return "PASS — in-scope contracts have permanent tests."
    if verdict == "PASS":
        return f"PASS with {warnings} warning(s); {adds} optional plan item(s)."
    return f"FAIL — {errors} error(s), {warnings} warning(s); {adds} test(s) to add."
