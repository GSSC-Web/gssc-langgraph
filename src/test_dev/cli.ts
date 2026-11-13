#!/usr/bin/env bun
/**
 * CLI entrypoint for the test_development workflow.
 *
 * Usage:
 *   bun run test-dev                  # git diff vs origin/master (fallback: master), else workspace
 *   bun run test-dev --base master
 *   bun run test-dev --workspace
 *   bun run test-dev --diff path/to.patch
 *   bun run test-dev --json
 *   bun run test-dev --run            # also execute suggested focused bun test commands
 */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { $ } from "bun";
import { threadConfig } from "../checkpoint/index.js";
import { graph } from "../graphs/test_development/graph.js";
import {
  collectFromDiff,
  collectGitDiff,
  collectPaths,
  collectWorkspace,
} from "../review/collect.js";
import type {
  ChangeSet,
  Finding,
  PlanItem,
  SpecialistNote,
  TestDevVerdict,
} from "./types.js";

type Args = {
  base: string;
  workspace: boolean;
  diffPath?: string;
  paths: string[];
  json: boolean;
  runFocused: boolean;
  help: boolean;
};

function parseArgs(argv: string[]): Args {
  const args: Args = {
    base: "origin/master",
    workspace: false,
    paths: [],
    json: false,
    runFocused: false,
    help: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === "--help" || a === "-h") args.help = true;
    else if (a === "--workspace") args.workspace = true;
    else if (a === "--json") args.json = true;
    else if (a === "--run") args.runFocused = true;
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
  console.log(`gssc-langgraph test development

Run the agentic test_development LangGraph (model-free) to map contracts →
permanent bun:test coverage, propose a plan, and optionally run focused tests.

Behavioral reference: gssc5 test agent / test-closeout-review (not a .agents scaffold).

Usage:
  bun run test-dev [options] [paths...]

Options:
  --base <ref>     Git base ref (default: origin/master)
  --workspace      Analyze the full working tree
  --diff <file>    Analyze a unified diff file
  --json           Emit machine-readable JSON
  --run            Execute suggested focused \`bun test\` commands after analysis
  -h, --help       Show help

Exit codes:
  0  PASS
  1  FAIL
  2  usage / runtime error
`);
}

function formatFinding(f: Finding): string {
  const loc = f.path ? `${f.path}: ` : "";
  const cid = f.contractId ? ` ${f.contractId}` : "";
  const fix = f.fix ? `\n    fix: ${f.fix}` : "";
  return `  [${f.severity}] (${f.check}${cid}) ${loc}${f.message}${fix}`;
}

function formatPlanItem(p: PlanItem): string {
  const where = p.path ? ` @ ${p.path}` : "";
  const cid = p.contractId ? ` (${p.contractId})` : "";
  return `  - [${p.action}]${cid}${where}: ${p.description}`;
}

async function runTestDev(cs: ChangeSet): Promise<{
  verdict: TestDevVerdict;
  summary: string;
  findings: Finding[];
  checksRun: string[];
  scopeGraphIds: string[];
  contracts: unknown[];
  coverage: unknown[];
  plan: PlanItem[];
  commands: string[];
  steps: string[];
  specialistNotes: SpecialistNote[];
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

  // One-shot CLI: fresh thread_id. Reuse a stable id for multi-turn memory.
  const result = await graph.invoke(
    {
      diff: cs.diff ?? "",
      files,
      fileStatuses,
      label: cs.label,
      changeSet: cs,
    },
    threadConfig(`test-dev-cli-${crypto.randomUUID()}`),
  );

  const verdict = (result.verdict || "FAIL") as TestDevVerdict;
  return {
    verdict,
    summary: result.summary || verdict,
    findings: result.findings ?? [],
    checksRun: result.checksRun ?? [],
    scopeGraphIds: result.scopeGraphIds ?? [],
    contracts: result.contracts ?? [],
    coverage: result.coverage ?? [],
    plan: result.plan ?? [],
    commands: result.commands ?? [],
    steps: result.steps ?? [],
    specialistNotes: result.specialistNotes ?? [],
  };
}

async function runFocusedCommands(commands: string[]): Promise<number> {
  // Prefer the first combined / focused command.
  const toRun = commands.slice(0, 1);
  let exit = 0;
  for (const cmd of toRun) {
    console.log(`\n→ ${cmd}`);
    const parts = cmd.split(/\s+/);
    if (parts[0] !== "bun" || parts[1] !== "test") {
      console.error(`Skipping non-bun-test command: ${cmd}`);
      continue;
    }
    const files = parts.slice(2);
    const result = await $`bun test ${files}`.nothrow();
    if (result.exitCode !== 0) exit = result.exitCode ?? 1;
  }
  return exit;
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
      try {
        cs = await collectGitDiff(root, args.base);
      } catch {
        try {
          cs = await collectGitDiff(root, "master");
        } catch {
          cs = await collectGitDiff(root, "main");
        }
      }
    }
  } catch (err) {
    console.error("Failed to collect change set:", err);
    process.exit(2);
  }

  // Adapt review ChangeSet → test_dev ChangeSet (same shape).
  const report = await runTestDev(cs as ChangeSet);

  if (args.json) {
    console.log(
      JSON.stringify(
        {
          verdict: report.verdict,
          summary: report.summary,
          label: cs.label,
          scopeGraphIds: report.scopeGraphIds,
          checksRun: report.checksRun,
          findings: report.findings,
          coverage: report.coverage,
          plan: report.plan,
          commands: report.commands,
          specialistNotes: report.specialistNotes,
          steps: report.steps,
        },
        null,
        2,
      ),
    );
  } else {
    console.log(`test_development — ${cs.label}`);
    console.log(report.summary);
    console.log(
      `scope: ${report.scopeGraphIds.join(", ") || "(none)"}`,
    );
    console.log(`checks: ${report.checksRun.join(", ") || "(none)"}`);
    if (report.findings.length) {
      console.log("findings:");
      for (const f of report.findings) console.log(formatFinding(f));
    }
    if (report.plan.length) {
      console.log("plan:");
      for (const p of report.plan) {
        console.log(formatPlanItem(p));
        if (p.suggestedTest) {
          console.log("    --- suggested test stub ---");
          for (const line of p.suggestedTest.trim().split("\n")) {
            console.log(`    ${line}`);
          }
          console.log("    ---");
        }
      }
    }
    if (report.commands.length) {
      console.log("focused commands:");
      for (const c of report.commands) console.log(`  ${c}`);
    }
    console.log(`verdict: ${report.verdict}`);
  }

  let focusedExit = 0;
  if (args.runFocused && report.commands.length) {
    focusedExit = await runFocusedCommands(report.commands);
  }

  if (focusedExit !== 0) process.exit(focusedExit);
  process.exit(report.verdict === "PASS" ? 0 : 1);
}

await main();
