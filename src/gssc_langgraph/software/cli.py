"""
CLI entrypoint for the software_dev workflow.

Usage:
  software --goal "Add foo assistant"
  software --workspace
  software --diff path/to.patch
  software --plan-only --goal "…"
  software --json

Exit codes: 0 PASS / 1 FAIL / 2 usage or runtime error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from gssc_langgraph.review.collect import (
    collect_from_diff,
    collect_git_diff,
    collect_paths,
    collect_workspace,
)
from gssc_langgraph.software.checks import run_all_checks, summarize
from gssc_langgraph.software.plan import build_plan
from gssc_langgraph.software.synthesize import synthesize_software
from gssc_langgraph.software.types import ChangeSet, PlanStep, SoftwareFinding


def _format_finding(f: SoftwareFinding) -> str:
    loc = f"{f['path']}: " if f.get("path") else ""
    uid = f" [{f['uid']}]" if f.get("uid") else ""
    fix = f"\n    fix: {f['fix']}" if f.get("fix") else ""
    return f"  [{f['severity']}] ({f['check']}){uid} {loc}{f['message']}{fix}"


def _format_plan(plan: list[PlanStep]) -> str:
    lines: list[str] = []
    for i, step in enumerate(plan, start=1):
        lines.append(f"  {i}. [{step['id']}] {step['title']}\n     {step['detail']}")
    return "\n".join(lines)


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
        prog="software",
        description=(
            "gssc-langgraph software development bot — model-free plan + checks; "
            "optional LLM synthesis when XAI_API_KEY is set."
        ),
    )
    p.add_argument("--goal", default="", help="Development goal / task brief")
    p.add_argument(
        "--requirements",
        default="",
        help="Optional LLR / requirements excerpt",
    )
    p.add_argument(
        "--base",
        default="origin/master",
        help="Git base ref (default: origin/master)",
    )
    p.add_argument(
        "--workspace",
        action="store_true",
        help="Structural scan of the working tree",
    )
    p.add_argument("--diff", dest="diff_path", help="Review a unified diff file")
    p.add_argument(
        "--plan-only",
        action="store_true",
        help="Skip collecting a change set; plan from --goal only",
    )
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument("paths", nargs="*", help="Explicit paths")
    return p


async def _run(goal: str, requirements: str, cs: ChangeSet | None) -> dict[str, Any]:
    plan = build_plan(goal, cs)
    verdict, findings, checks_run = run_all_checks(goal, cs)
    summary = summarize(verdict, findings, len(plan))
    synthesis = await synthesize_software(
        {
            "verdict": verdict,
            "summary": summary,
            "goal": goal,
            "plan": plan,
            "findings": findings,
        }
    )
    return {
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "checksRun": checks_run,
        "plan": plan,
        "narrativeSummary": synthesis["narrativeSummary"] or summary or verdict,
        "proposedMemoryUpdates": synthesis["proposedMemoryUpdates"],
        "synthesisNote": synthesis["note"],
        "requirements": requirements,
    }


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    root = Path.cwd().resolve()
    cs: ChangeSet | None = None

    try:
        if args.plan_only:
            cs = None
        elif args.diff_path:
            diff = Path(root, args.diff_path).read_text(encoding="utf-8")
            cs = _to_change_set(
                collect_from_diff(str(root), diff, f"diff {args.diff_path}")
            )
        elif args.workspace:
            cs = _to_change_set(collect_workspace(str(root)))
        elif args.paths:
            cs = _to_change_set(collect_paths(str(root), args.paths))
        elif args.goal and not args.diff_path:
            try:
                cs = _to_change_set(collect_git_diff(str(root), args.base))
            except Exception:
                try:
                    cs = _to_change_set(collect_git_diff(str(root), "master"))
                except Exception:
                    cs = None
        else:
            try:
                cs = _to_change_set(collect_git_diff(str(root), args.base))
            except Exception:
                try:
                    cs = _to_change_set(collect_git_diff(str(root), "master"))
                except Exception:
                    cs = _to_change_set(collect_workspace(str(root)))
    except Exception as err:
        print(f"Failed to collect change set: {err}", file=sys.stderr)
        raise SystemExit(2) from err

    try:
        report = asyncio.run(_run(args.goal, args.requirements, cs))
    except Exception as err:
        print(f"software failed: {err}", file=sys.stderr)
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
                    "goal": args.goal,
                    "label": cs["label"] if cs else "plan-only",
                    "plan": report["plan"],
                    "checksRun": report["checksRun"],
                    "findings": report["findings"],
                },
                indent=2,
            )
        )
    else:
        print(f"software_dev — {cs['label'] if cs else 'plan-only'}")
        if args.goal:
            print(f"goal: {args.goal}")
        print(report["summary"])
        if report["synthesisNote"]:
            print(f"synthesis: {report['synthesisNote']}")
        print("plan:")
        print(_format_plan(report["plan"]))
        print(f"checks: {', '.join(report['checksRun']) or '(none)'}")
        if report["findings"]:
            print("findings:")
            for f in report["findings"]:
                print(_format_finding(f))
        print(f"verdict: {report['verdict']}")

    raise SystemExit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
