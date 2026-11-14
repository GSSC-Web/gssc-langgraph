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
from gssc_langgraph.envelope.domains import pin_domains
from gssc_langgraph.test_dev.types import (
    ChangeSet,
    Contract,
    CoverageGap,
    CoverageLink,
    Finding,
    PlanItem,
    TestCase,
    TestDevCheckId,
    TestDevVerdict,
)
from gssc_langgraph.work_surface import classify_path, detect_work_surface

TEST_FILE_RE = re.compile(r"^tests/.+\.py$")
APP_TEST_FILE_RE = re.compile(r"(?i).+\.test\.(?:ts|js)$")


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


def _fe_files(cs: ChangeSet) -> list[str]:
    return [
        f["path"]
        for f in cs["files"]
        if f["status"] != "deleted" and classify_path(f["path"]) == "gssc5_fe"
    ]


def _be_files(cs: ChangeSet) -> list[str]:
    return [
        f["path"]
        for f in cs["files"]
        if f["status"] != "deleted" and classify_path(f["path"]) == "gssc5_be"
    ]


def _app_test_files(cs: ChangeSet, *, surface: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for f in cs["files"]:
        if not APP_TEST_FILE_RE.search(f["path"]) or f["status"] == "deleted":
            continue
        kind = classify_path(f["path"])
        if surface == "gssc5_fe" and kind == "gssc5_fe":
            out.append({"path": f["path"], "body": f.get("content") or ""})
        elif surface == "gssc5_be" and kind == "gssc5_be":
            out.append({"path": f["path"], "body": f.get("content") or ""})
    return out


def _fe_test_files(cs: ChangeSet) -> list[dict[str, str]]:
    return _app_test_files(cs, surface="gssc5_fe")


def _be_test_files(cs: ChangeSet) -> list[dict[str, str]]:
    return _app_test_files(cs, surface="gssc5_be")


def resolve_scope(cs: ChangeSet) -> tuple[list[str], list[Finding]]:
    findings: list[Finding] = []
    changed = changed_graph_ids(cs)
    all_ids = graph_ids_from_change_set(cs)
    label = cs.get("label") or ""
    surface = detect_work_surface(change_set=cs)

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
        if surface == "mixed" or (_be_files(cs) and _fe_files(cs)):
            findings.append(
                {
                    "check": "scope",
                    "severity": "info",
                    "message": (
                        "mixed gssc5 BE+FE change set — dual-domain Bun + "
                        "Angular tests (not winner-take-all)"
                    ),
                    "fix": (
                        "Prefer existing changeSet test loci for each domain "
                        "(`bun test` / `mise run //backend:test` and "
                        "`bunx ng test`); do not invent missing companions."
                    ),
                }
            )
        elif surface == "gssc5_be" or (_be_files(cs) and not _fe_files(cs)):
            findings.append(
                {
                    "check": "scope",
                    "severity": "info",
                    "message": (
                        "gssc5 backend change set — scoping Bun/Elysia tests "
                        "(not Angular FE or LangGraph graphs)"
                    ),
                    "fix": (
                        "Prefer `bun test` / `mise run //backend:test` beside "
                        "`apps/backend` sources; do not suggest `ng test`."
                    ),
                }
            )
        elif surface == "gssc5_fe" or _fe_files(cs):
            findings.append(
                {
                    "check": "scope",
                    "severity": "info",
                    "message": (
                        "gssc5 FE change set — scoping Angular/component tests "
                        "(not LangGraph graphs)"
                    ),
                    "fix": (
                        "Prefer companion `*.test.ts` beside the touched FE "
                        "files; graph.invoke pytest is for this service only."
                    ),
                }
            )
        else:
            findings.append(
                {
                    "check": "scope",
                    "severity": "warning",
                    "message": "No graphs in scope for test development",
                    "fix": (
                        "Pass --workspace, a diff that touches graphs, or "
                        "explicit paths. For gssc5 FE work, pass "
                        "`gssc5-web/…` paths so planners skip graph scope."
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
    surface = detect_work_surface(change_set=cs)

    if not scope_graph_ids and (
        surface in ("gssc5_be", "gssc5_fe", "mixed")
        or _be_files(cs)
        or _fe_files(cs)
    ):
        commands.extend(_app_test_commands(cs, surface))
        return findings, commands

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


def _companion_app_test(path: str) -> str | None:
    if APP_TEST_FILE_RE.search(path):
        return None
    if path.endswith(".html") or path.endswith(".ts"):
        stem = path.rsplit(".", 1)[0]
        if stem.endswith(".component"):
            stem = stem[: -len(".component")]
        dir_prefix, _, name = stem.rpartition("/")
        return f"{dir_prefix}/{name}.test.ts" if dir_prefix else f"{name}.test.ts"
    return None


def _existing_domain_tests(cs: ChangeSet, *, surface: str) -> list[str]:
    """Test paths that already appear in the change set for a domain."""
    return [t["path"] for t in _app_test_files(cs, surface=surface)]


def _nearest_existing_test(
    source_path: str, existing_tests: list[str]
) -> str | None:
    """Map a source to an existing test locus (same dir preferred)."""
    if not existing_tests:
        return None
    companion = _companion_app_test(source_path)
    if companion and companion in existing_tests:
        return companion
    src_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
    same_dir = [t for t in existing_tests if t.rsplit("/", 1)[0] == src_dir]
    if same_dir:
        return sorted(same_dir)[0]
    return sorted(existing_tests)[0]


def _app_test_commands(cs: ChangeSet, surface: str) -> list[str]:
    """Build harness commands using only existing changeSet test paths."""
    commands: list[str] = []
    want_be = surface in ("gssc5_be", "mixed") or (
        surface == "unknown" and _be_files(cs)
    )
    want_fe = surface in ("gssc5_fe", "mixed") or (
        surface == "unknown" and _fe_files(cs)
    )
    if want_be and _be_files(cs):
        be_tests = _existing_domain_tests(cs, surface="gssc5_be")
        commands.append("mise run //backend:test")
        for path in be_tests[:4]:
            commands.append(f"bun test {path}")
        # No invented companions when none exist in the change set.
    if want_fe and _fe_files(cs):
        fe_tests = _existing_domain_tests(cs, surface="gssc5_fe")
        if fe_tests:
            sample = fe_tests[0]
            if "prompt-overlay" in sample:
                commands.append(
                    "bunx ng test --watch=false "
                    "--include='**/prompt-overlay/**/*.test.ts'"
                )
            for t in fe_tests[:3]:
                commands.append(
                    "bunx ng test --watch=false "
                    f"--include='**/{t.rsplit('/', 1)[-1]}'"
                )
        else:
            # Point at touched FE modules without inventing a missing file.
            for path in _fe_files(cs)[:2]:
                name = path.rsplit("/", 1)[-1]
                commands.append(
                    f"bunx ng test --watch=false --include='**/{name}'"
                )
    return commands


def _domain_plan_items(
    cs: ChangeSet,
    *,
    surface: str,
    label: str,
) -> list[PlanItem]:
    """Suggest updates only against existing changeSet tests (no invented paths)."""
    plan: list[PlanItem] = []
    sources = _be_files(cs) if surface == "gssc5_be" else _fe_files(cs)
    existing = _existing_domain_tests(cs, surface=surface)
    seen: set[str] = set()
    for path in sources:
        if APP_TEST_FILE_RE.search(path):
            continue
        locus = _nearest_existing_test(path, existing)
        if not locus or locus in seen:
            continue
        seen.add(locus)
        plan.append(
            {
                "action": "update_test",
                "path": locus,
                "description": (
                    f"Update existing {label} test `{locus}` for changes in "
                    f"`{path}` — do not invent a new companion path"
                ),
            }
        )
    if not plan and sources:
        plan.append(
            {
                "action": "update_test",
                "description": (
                    f"Locate the existing {label} test locus for "
                    f"`{sources[0]}` (UID→Test mapping); do not invent "
                    "missing companions"
                ),
                "path": sources[0],
            }
        )
    return plan


def _build_fe_plan(cs: ChangeSet, commands: list[str]) -> list[PlanItem]:
    plan = _domain_plan_items(cs, surface="gssc5_fe", label="FE")
    for cmd in commands[:3]:
        plan.append(
            {
                "action": "run_focused",
                "description": f"Prefer focused harness: {cmd}",
            }
        )
    return plan


def _build_be_plan(cs: ChangeSet, commands: list[str]) -> list[PlanItem]:
    plan = _domain_plan_items(cs, surface="gssc5_be", label="backend Bun")
    for cmd in commands[:3]:
        plan.append(
            {
                "action": "run_focused",
                "description": f"Prefer focused harness: {cmd}",
            }
        )
    return plan


def _build_mixed_plan(cs: ChangeSet, commands: list[str]) -> list[PlanItem]:
    plan: list[PlanItem] = []
    plan.extend(_domain_plan_items(cs, surface="gssc5_be", label="backend Bun"))
    plan.extend(_domain_plan_items(cs, surface="gssc5_fe", label="FE"))
    for cmd in commands[:4]:
        plan.append(
            {
                "action": "run_focused",
                "description": f"Prefer focused harness: {cmd}",
            }
        )
    return plan


def build_plan(
    contracts: list[Contract],
    coverage: list[CoverageLink],
    findings: list[Finding],
    commands: list[str],
    *,
    change_set: ChangeSet | None = None,
) -> list[PlanItem]:
    plan: list[PlanItem] = []

    surface = detect_work_surface(change_set=change_set) if change_set else "unknown"
    has_graph_contracts = any(c.get("graphId") for c in contracts)
    if change_set and not has_graph_contracts:
        has_be = bool(_be_files(change_set))
        has_fe = bool(_fe_files(change_set))
        if surface == "mixed" or (has_be and has_fe):
            return _build_mixed_plan(change_set, commands)
        if surface == "gssc5_be" or (has_be and not has_fe):
            return _build_be_plan(change_set, commands)
        if surface == "gssc5_fe" or has_fe:
            return _build_fe_plan(change_set, commands)

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


_BOUNDARY_RE = re.compile(
    r"(?i)\b(straddl\w*|boundary|cross[- ]field|needle|negative case|"
    r"o\\nW|edge case)\b"
)
_UID_RE = re.compile(r"\b([A-Z]{2,6}-\d+)\b")


def build_test_cases_and_gaps(
    cs: ChangeSet,
    contracts: list[Contract],
    coverage: list[CoverageLink],
    *,
    requirements: str = "",
) -> tuple[list[TestCase], list[CoverageGap], list[Finding]]:
    """Map contracts + requirement cues → testCases/gaps (GLG-40).

    Contract gaps are listed for the payload; blocking FAIL for those
    still comes from existing coverage_map findings. Requirement-derived
    boundary cases add explicit blocking findings when missing.
    """
    cases: list[TestCase] = []
    gaps: list[CoverageGap] = []
    extra_findings: list[Finding] = []
    domains = pin_domains(change_set=cs, requirements=requirements)
    primary = domains[0] if domains else "unknown"
    cov_by_id = {c["contractId"]: c for c in coverage}

    for c in contracts:
        link = cov_by_id.get(c["id"])
        covered = bool(link and link.get("covered"))
        status = "present" if covered else "missing"
        case: TestCase = {
            "id": c["id"],
            "title": c["title"],
            "assertion": "; ".join(c.get("assertHints") or []) or c["requirement"],
            "status": status,  # type: ignore[typeddict-item]
            "domain": primary,
        }
        if link and link.get("testPath"):
            case["path"] = link["testPath"]
        cases.append(case)
        if not covered:
            gaps.append(
                {
                    "id": f"gap.{c['id']}",
                    "title": f"Missing coverage: {c['title']}",
                    "severity": "error",
                    "detail": c["requirement"],
                    "domain": primary,
                }
            )

    req = requirements.strip()
    if req and _BOUNDARY_RE.search(req):
        uids = _UID_RE.findall(req)
        uid = uids[0] if uids else None
        body_blob = " ".join(
            (f.get("content") or "") for f in cs.get("files") or [] if isinstance(f, dict)
        )
        present = bool(
            re.search(r"(?i)straddl|boundary|needle|o\\nW|cross.?field", body_blob)
        )
        case_id = f"req.boundary.{uid or 'case'}"
        title = "Boundary / straddling-needle negative"
        case2: TestCase = {
            "id": case_id,
            "title": title,
            "assertion": "Cover the boundary/negative case required by the ticket",
            "status": "present" if present else "missing",
            "domain": primary,
        }
        if uid:
            case2["uid"] = uid
        cases.append(case2)
        if not present:
            gap2: CoverageGap = {
                "id": f"gap.{case_id}",
                "title": title,
                "severity": "error",
                "detail": (
                    "Ticket requires a boundary/straddling/needle negative case "
                    "that is not evidenced in the change set tests"
                ),
                "domain": primary,
            }
            if uid:
                gap2["uid"] = uid
            gaps.append(gap2)
            finding: Finding = {
                "check": "coverage_map",
                "severity": "error",
                "code": "gap.boundary_required",
                "message": gap2["detail"],
            }
            if uid:
                finding["contractId"] = uid
            extra_findings.append(finding)

    return cases, gaps, extra_findings


def run_analysis(
    cs: ChangeSet,
    *,
    requirements: str = "",
) -> dict[str, object]:
    from gssc_langgraph.work_surface import looks_like_unified_diff

    checks_run: list[TestDevCheckId] = []
    findings: list[Finding] = []

    files = cs.get("files") or []
    diff = cs.get("diff") or ""
    if not files and not looks_like_unified_diff(diff):
        findings.append(
            {
                "check": "scope",
                "severity": "error",
                "code": "changeset.required",
                "message": (
                    "TestDev requires changeSet.files or a unified "
                    "`diff --git` (input ERROR)"
                ),
            }
        )
        return {
            "scopeGraphIds": [],
            "contracts": [],
            "coverage": [],
            "findings": findings,
            "checksRun": ["scope"],
            "plan": [],
            "commands": [],
            "testCases": [],
            "gaps": [],
        }

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

    plan = build_plan(contracts, coverage, findings, commands, change_set=cs)

    test_cases, gaps, gap_findings = build_test_cases_and_gaps(
        cs, contracts, coverage, requirements=requirements
    )
    findings.extend(gap_findings)

    return {
        "scopeGraphIds": graph_ids,
        "contracts": contracts,
        "coverage": coverage,
        "findings": findings,
        "checksRun": checks_run,
        "plan": plan,
        "commands": commands,
        "testCases": test_cases,
        "gaps": gaps,
    }


def verdict_from(findings: list[Finding]) -> TestDevVerdict:
    if any(
        f.get("severity") == "error"
        and str(f.get("code") or "").startswith(("changeset.", "input."))
        for f in findings
    ):
        return "ERROR"
    return "FAIL" if any(f["severity"] == "error" for f in findings) else "PASS"


def summarize(
    verdict: TestDevVerdict,
    findings: list[Finding],
    plan: list[PlanItem],
) -> str:
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    adds = sum(1 for p in plan if p["action"] == "add_test")
    if verdict == "ERROR":
        return f"ERROR — fix inputs and retry ({errors} input issue(s))."
    if verdict == "PASS" and warnings == 0 and adds == 0:
        return "PASS — in-scope contracts have permanent tests."
    if verdict == "PASS":
        return f"PASS with {warnings} warning(s); {adds} optional plan item(s)."
    return f"FAIL — {errors} error(s), {warnings} warning(s); {adds} test(s) to add."
