"""
CLI entrypoint for the closeout_review workflow.

Usage:
  closeout                  # git diff vs origin/master, else workspace
  closeout --base master
  closeout --workspace
  closeout --diff path/to.patch
  closeout --json

Exit codes: 0 PASS / 1 FAIL / 2 usage or runtime error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from gssc_langgraph.closeout.checks import run_all_checks
from gssc_langgraph.closeout.synthesize import synthesize_closeout
from gssc_langgraph.closeout.types import ChangeSet, CloseoutFinding
from gssc_langgraph.review.collect import (
    collect_from_diff,
    collect_git_diff,
    collect_paths,
    collect_workspace,
)


def _format_finding(f: CloseoutFinding) -> str:
    loc = f"{f['path']}: " if f.get("path") else ""
    uid = f" [{f['uid']}]" if f.get("uid") else ""
    fix = f"\n    fix: {f['fix']}" if f.get("fix") else ""
    return f"  [{f['severity']}] ({f['check']}){uid} {loc}{f['message']}{fix}"


def _to_change_set(cs: Any) -> ChangeSet:
    if isinstance(cs, dict):
        files = []
        for f in cs.get("files") or []:
            item: dict[str, Any] = {
                "path": f["path"] if isinstance(f, dict) else f.path,
                "status": f["status"] if isinstance(f, dict) else f.status,
            }
            content = f.get("content") if isinstance(f, dict) else getattr(f, "content", None)
            patch = f.get("patch") if isinstance(f, dict) else getattr(f, "patch", None)
            if content is not None:
                item["content"] = content
            if patch is not None:
                item["patch"] = patch
            files.append(item)  # type: ignore[arg-type]
        out: ChangeSet = {
            "label": cs.get("label") if isinstance(cs, dict) else getattr(cs, "label", "diff"),
            "files": files,  # type: ignore[typeddict-item]
        }
        diff = cs.get("diff") if isinstance(cs, dict) else getattr(cs, "diff", None)
        if diff is not None:
            out["diff"] = diff
        return out
    raise TypeError(f"unexpected change set type: {type(cs)!r}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="closeout",
        description=(
            "gssc-langgraph closeout review — model-free checks; optional LLM "
            "synthesis when XAI_API_KEY is set."
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
        help="Structural closeout of the working tree (ignore git range)",
    )
    p.add_argument("--diff", dest="diff_path", help="Review a unified diff file")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    p.add_argument(
        "paths",
        nargs="*",
        help="Explicit paths to include in the change set",
    )
    return p


async def _run(cs: ChangeSet) -> dict[str, Any]:
    verdict, summary, findings, checks_run = run_all_checks(cs)
    synthesis = await synthesize_closeout(
        {
            "verdict": verdict,
            "summary": summary,
            "findings": findings,
        }
    )
    return {
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "checksRun": checks_run,
        "narrativeSummary": synthesis["narrativeSummary"] or summary or verdict,
        "proposedMemoryUpdates": synthesis["proposedMemoryUpdates"],
        "synthesisNote": synthesis["note"],
    }


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
                    cs = _to_change_set(collect_workspace(str(root)))
    except Exception as err:
        print(f"Failed to collect change set: {err}", file=sys.stderr)
        raise SystemExit(2) from err

    try:
        report = asyncio.run(_run(cs))
    except Exception as err:
        print(f"closeout failed: {err}", file=sys.stderr)
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
                    "checksRun": report["checksRun"],
                    "findings": report["findings"],
                },
                indent=2,
            )
        )
    else:
        print(f"closeout_review — {cs['label']}")
        print(report["summary"])
        if report["synthesisNote"]:
            print(f"synthesis: {report['synthesisNote']}")
        print(f"checks: {', '.join(report['checksRun']) or '(none)'}")
        if report["findings"]:
            print("findings:")
            for f in report["findings"]:
                print(_format_finding(f))
        print(f"verdict: {report['verdict']}")

    raise SystemExit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
