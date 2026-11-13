"""
CLI entrypoint for the test_development workflow.

Usage:
  test-dev                  # git diff vs origin/master (fallback: master/main)
  test-dev --base master
  test-dev --workspace
  test-dev --diff path/to.patch
  test-dev --json
  test-dev --run            # execute suggested focused pytest commands

Exit codes: 0 PASS / 1 FAIL / 2 usage or runtime error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from gssc_langgraph.review.collect import (
    collect_from_diff,
    collect_git_diff,
    collect_paths,
    collect_workspace,
)
from gssc_langgraph.test_dev.analyze import run_analysis, summarize, verdict_from
from gssc_langgraph.test_dev.synthesize import synthesize_test_dev
from gssc_langgraph.test_dev.types import ChangeSet, Finding, PlanItem


def _format_finding(f: Finding) -> str:
    loc = f"{f['path']}: " if f.get("path") else ""
    cid = f" {f['contractId']}" if f.get("contractId") else ""
    fix = f"\n    fix: {f['fix']}" if f.get("fix") else ""
    return f"  [{f['severity']}] ({f['check']}{cid}) {loc}{f['message']}{fix}"


def _format_plan_item(p: PlanItem) -> str:
    where = f" @ {p['path']}" if p.get("path") else ""
    cid = f" ({p['contractId']})" if p.get("contractId") else ""
    return f"  - [{p['action']}]{cid}{where}: {p['description']}"


def _to_change_set(cs: Any) -> ChangeSet:
    if not isinstance(cs, dict):
        raise TypeError(f"unexpected change set type: {type(cs)!r}")
    files = []
    for f in cs.get("files") or []:
        item: dict[str, Any] = {"path": f["path"], "status": f["status"]}
        if f.get("content") is not None:
            item["content"] = f["content"]
        if f.get("patch") is not None:
            item["patch"] = f["patch"]
        files.append(item)
    out: ChangeSet = {"label": cs.get("label", "diff"), "files": files}  # type: ignore[typeddict-item]
    if cs.get("diff") is not None:
        out["diff"] = cs["diff"]
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test-dev",
        description=(
            "gssc-langgraph test development — model-free analysis; optional "
            "LLM synthesis when XAI_API_KEY is set."
        ),
    )
    p.add_argument(
        "--base",
        default="origin/master",
        help="Git base ref (default: origin/master)",
    )
    p.add_argument(
        "--workspace",
        action="store_true",
        help="Analyze the full working tree",
    )
    p.add_argument("--diff", dest="diff_path", help="Analyze a unified diff file")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument(
        "--run",
        dest="run_focused",
        action="store_true",
        help="Execute suggested focused pytest commands after analysis",
    )
    p.add_argument("paths", nargs="*", help="Explicit paths")
    return p


async def _run(cs: ChangeSet) -> dict[str, Any]:
    analysis = run_analysis(cs)
    findings = analysis["findings"]  # type: ignore[assignment]
    plan = analysis["plan"]  # type: ignore[assignment]
    verdict = verdict_from(findings)  # type: ignore[arg-type]
    summary = summarize(verdict, findings, plan)  # type: ignore[arg-type]
    synthesis = await synthesize_test_dev(
        {
            "verdict": verdict,
            "summary": summary,
            "findings": findings,  # type: ignore[typeddict-item]
            "plan": plan,  # type: ignore[typeddict-item]
            "scopeGraphIds": analysis["scopeGraphIds"],  # type: ignore[typeddict-item]
            "commands": analysis["commands"],  # type: ignore[typeddict-item]
        }
    )
    return {
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "checksRun": analysis["checksRun"],
        "scopeGraphIds": analysis["scopeGraphIds"],
        "contracts": analysis["contracts"],
        "coverage": analysis["coverage"],
        "plan": plan,
        "commands": analysis["commands"],
        "narrativeSummary": synthesis["narrativeSummary"] or summary or verdict,
        "proposedMemoryUpdates": synthesis["proposedMemoryUpdates"],
        "synthesisNote": synthesis["note"],
    }


def _run_focused_commands(commands: list[str]) -> int:
    if not commands:
        return 0
    cmd = commands[0]
    print(f"\n→ {cmd}")
    parts = shlex.split(cmd)
    # Accept: pytest … | uv run pytest …
    if parts[:2] == ["uv", "run"] and len(parts) >= 3 and parts[2] == "pytest":
        pass
    elif parts and parts[0] == "pytest":
        pass
    else:
        print(f"Skipping non-pytest command: {cmd}", file=sys.stderr)
        return 0
    result = subprocess.run(parts, check=False)
    return result.returncode


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    root = Path.cwd().resolve()

    try:
        if args.diff_path:
            diff = Path(root, args.diff_path).read_text(encoding="utf-8")
            cs = _to_change_set(
                collect_from_diff(str(root), diff, f"diff {args.diff_path}")
            )
        elif args.workspace:
            cs = _to_change_set(collect_workspace(str(root)))
        elif args.paths:
            cs = _to_change_set(collect_paths(str(root), args.paths))
        else:
            try:
                cs = _to_change_set(collect_git_diff(str(root), args.base))
            except Exception:
                try:
                    cs = _to_change_set(collect_git_diff(str(root), "master"))
                except Exception:
                    cs = _to_change_set(collect_git_diff(str(root), "main"))
    except Exception as err:
        print(f"Failed to collect change set: {err}", file=sys.stderr)
        raise SystemExit(2) from err

    try:
        report = asyncio.run(_run(cs))
    except Exception as err:
        print(f"test-dev failed: {err}", file=sys.stderr)
        raise SystemExit(2) from err

    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report["verdict"],
                    "summary": report["summary"],
                    "narrativeSummary": report["narrativeSummary"],
                    "proposedMemoryUpdates": report["proposedMemoryUpdates"],
                    "synthesisNote": report["synthesisNote"],
                    "label": cs["label"],
                    "scopeGraphIds": report["scopeGraphIds"],
                    "checksRun": report["checksRun"],
                    "findings": report["findings"],
                    "coverage": report["coverage"],
                    "plan": report["plan"],
                    "commands": report["commands"],
                },
                indent=2,
            )
        )
    else:
        print(f"test_development — {cs['label']}")
        print(report["summary"])
        if report["synthesisNote"]:
            print(f"synthesis: {report['synthesisNote']}")
        print(f"scope: {', '.join(report['scopeGraphIds']) or '(none)'}")
        print(f"checks: {', '.join(report['checksRun']) or '(none)'}")
        if report["findings"]:
            print("findings:")
            for f in report["findings"]:
                print(_format_finding(f))
        if report["plan"]:
            print("plan:")
            for p in report["plan"]:
                print(_format_plan_item(p))
                if p.get("suggestedTest"):
                    print("    --- suggested test stub ---")
                    for line in p["suggestedTest"].strip().splitlines():
                        print(f"    {line}")
                    print("    ---")
        if report["commands"]:
            print("focused commands:")
            for c in report["commands"]:
                print(f"  {c}")
        print(f"verdict: {report['verdict']}")

    focused_exit = 0
    if args.run_focused and report["commands"]:
        focused_exit = _run_focused_commands(report["commands"])

    if focused_exit != 0:
        raise SystemExit(focused_exit)
    raise SystemExit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
