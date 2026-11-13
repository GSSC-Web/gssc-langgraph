#!/usr/bin/env bun
/**
 * CLI entrypoint for the service_review workflow.
 *
 * Usage:
 *   bun run review                  # git diff vs origin/main (fallback: main), else workspace
 *   bun run review --base main
 *   bun run review --workspace
 *   bun run review --diff path/to.patch
 *   bun run review --json
 */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { graph } from "../graphs/service_review/graph.js";
import {
  collectFromDiff,
  collectGitDiff,
  collectPaths,
  collectWorkspace,
} from "./collect.js";
import type { ChangeSet, Finding, ReviewVerdict } from "./types.js";

type Args = {
  base: string;
  workspace: boolean;
  diffPath?: string;
  paths: string[];
  json: boolean;
  help: boolean;
};

function parseArgs(argv: string[]): Args {
  const args: Args = {
    base: "origin/main",
    workspace: false,
    paths: [],
    json: false,
    help: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === "--help" || a === "-h") args.help = true;
    else if (a === "--workspace") args.workspace = true;
    else if (a === "--json") args.json = true;
    else if (a === "--base") {
      args.base = argv[++i] ?? args.base;
    } else if (a === "--diff") {
      args.diffPath = argv[++i];
    } else if (a === "--") {
      args.paths.push(...argv.slice(i + 1));
      break;
    } else if (a.startsWith("-")) {
      console.error(`Unknown flag: ${a}`);
      args.help = true;
    } else {
      args.paths.push(a);
    }
  }
  return args;
}

function printHelp(): void {
  console.log(`gssc-langgraph service review

Run the agentic service_review LangGraph (model-free) against a diff or workspace.

Usage:
  bun run review [options] [paths...]

Options:
  --base <ref>     Git base ref (default: origin/main)
  --workspace      Structural review of the working tree (ignore git range)
  --diff <file>    Review a unified diff file
  --json           Emit machine-readable JSON
  -h, --help       Show help

Exit codes:
  0  PASS
  1  FAIL
  2  usage / runtime error
`);
}

function formatFinding(f: Finding): string {
  const loc = f.path ? `${f.path}: ` : "";
  const fix = f.fix ? `\n    fix: ${f.fix}` : "";
  return `  [${f.severity}] (${f.check}) ${loc}${f.message}${fix}`;
}

async function runReview(cs: ChangeSet): Promise<{
  verdict: ReviewVerdict;
  summary: string;
  findings: Finding[];
  checksRun: string[];
  steps: string[];
}> {
  const files: Record<string, string> = {};
  const fileStatuses: Record<string, "added" | "modified" | "deleted" | "unchanged"> =
    {};
  for (const f of cs.files) {
    if (f.content !== undefined) files[f.path] = f.content;
    fileStatuses[f.path] = f.status;
  }

  const result = await graph.invoke({
    diff: cs.diff ?? "",
    files,
    fileStatuses,
    label: cs.label,
    changeSet: cs,
  });

  const verdict = (result.verdict || "FAIL") as ReviewVerdict;
  return {
    verdict,
    summary: result.summary || verdict,
    findings: result.findings ?? [],
    checksRun: result.checksRun ?? [],
    steps: result.steps ?? [],
  };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    process.exit(0);
  }

  const root = resolve(process.cwd());
  let cs: ChangeSet;

  try {
    if (args.diffPath) {
      const diff = await readFile(resolve(root, args.diffPath), "utf8");
      cs = await collectFromDiff(root, diff, `diff ${args.diffPath}`);
    } else if (args.workspace) {
      cs = await collectWorkspace(root);
    } else if (args.paths.length > 0) {
      cs = await collectPaths(root, args.paths);
    } else {
      // Try origin/main, then main.
      try {
        cs = await collectGitDiff(root, args.base);
      } catch {
        cs = await collectGitDiff(root, "main");
      }
    }
  } catch (err) {
    console.error("Failed to collect change set:", err);
    process.exit(2);
  }

  const report = await runReview(cs);

  if (args.json) {
    console.log(
      JSON.stringify(
        {
          verdict: report.verdict,
          summary: report.summary,
          label: cs.label,
          checksRun: report.checksRun,
          findings: report.findings,
          steps: report.steps,
        },
        null,
        2,
      ),
    );
  } else {
    console.log(`service_review — ${cs.label}`);
    console.log(report.summary);
    console.log(`checks: ${report.checksRun.join(", ") || "(none)"}`);
    if (report.findings.length) {
      console.log("findings:");
      for (const f of report.findings) console.log(formatFinding(f));
    }
    console.log(`verdict: ${report.verdict}`);
  }

  process.exit(report.verdict === "PASS" ? 0 : 1);
}

await main();
