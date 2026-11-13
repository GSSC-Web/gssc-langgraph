#!/usr/bin/env bun
/**
 * CLI entrypoint for the closeout_review workflow.
 *
 * Usage:
 *   bun run closeout                  # git diff vs origin/master, else workspace
 *   bun run closeout --base master
 *   bun run closeout --workspace
 *   bun run closeout --diff path/to.patch
 *   bun run closeout --json
 *
 * Default git base is origin/master (repo default branch).
 */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { graph } from "../graphs/closeout_review/graph.js";
import {
  collectFromDiff,
  collectGitDiff,
  collectPaths,
  collectWorkspace,
} from "../review/collect.js";
import type {
  ChangeSet,
  CloseoutFinding,
  CloseoutVerdict,
} from "./types.js";

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
    base: "origin/master",
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
  console.log(`gssc-langgraph closeout review

Run the agentic closeout_review LangGraph (model-free). Behavioral reference:
gssc5 requirements / software / test closeout-review skills (PASS/FAIL, scoped
checks, no silent contract rewrites) — adapted for this Agent Server.

Usage:
  bun run closeout [options] [paths...]

Options:
  --base <ref>     Git base ref (default: origin/master)
  --workspace      Structural closeout of the working tree (ignore git range)
  --diff <file>    Review a unified diff file
  --json           Emit machine-readable JSON
  -h, --help       Show help

Exit codes:
  0  PASS
  1  FAIL
  2  usage / runtime error

Peers: software_dev and test_development are separate assistants — this bot is
pre-merge closeout review only (not a revival of service_review).
`);
}

function formatFinding(f: CloseoutFinding): string {
  const loc = f.path ? `${f.path}: ` : "";
  const uid = f.uid ? ` [${f.uid}]` : "";
  const fix = f.fix ? `\n    fix: ${f.fix}` : "";
  return `  [${f.severity}] (${f.check})${uid} ${loc}${f.message}${fix}`;
}

function toChangeSet(cs: {
  label: string;
  files: Array<{
    path: string;
    content?: string;
    patch?: string;
    status: "added" | "modified" | "deleted" | "unchanged";
  }>;
  diff?: string;
}): ChangeSet {
  return {
    label: cs.label,
    diff: cs.diff,
    files: cs.files.map((f) => ({
      path: f.path,
      content: f.content,
      patch: f.patch,
      status: f.status,
    })),
  };
}

async function runCloseout(cs: ChangeSet): Promise<{
  verdict: CloseoutVerdict;
  summary: string;
  findings: CloseoutFinding[];
  checksRun: string[];
  steps: string[];
}> {
  const files: Record<string, string> = {};
  const fileStatuses: Record<
    string,
    "added" | "modified" | "deleted" | "unchanged"
  > = {};
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

  const verdict = (result.verdict || "FAIL") as CloseoutVerdict;
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
      cs = toChangeSet(
        await collectFromDiff(root, diff, `diff ${args.diffPath}`),
      );
    } else if (args.workspace) {
      cs = toChangeSet(await collectWorkspace(root));
    } else if (args.paths.length > 0) {
      cs = toChangeSet(await collectPaths(root, args.paths));
    } else {
      try {
        cs = toChangeSet(await collectGitDiff(root, args.base));
      } catch {
        try {
          cs = toChangeSet(await collectGitDiff(root, "master"));
        } catch {
          cs = toChangeSet(await collectWorkspace(root));
        }
      }
    }
  } catch (err) {
    console.error("Failed to collect change set:", err);
    process.exit(2);
  }

  const report = await runCloseout(cs);

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
    console.log(`closeout_review — ${cs.label}`);
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
