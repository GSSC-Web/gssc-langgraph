#!/usr/bin/env bun
/**
 * CLI entrypoint for the software_dev workflow.
 *
 * Usage:
 *   bun run software --goal "Add foo assistant"
 *   bun run software --goal "…"                  # + git diff vs origin/master
 *   bun run software --workspace
 *   bun run software --diff path/to.patch
 *   bun run software --json
 *
 * Default git base is origin/master (repo default branch).
 */
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { threadConfig } from "../checkpoint/index.js";
import { graph } from "../graphs/software_dev/graph.js";
import {
  collectFromDiff,
  collectGitDiff,
  collectPaths,
  collectWorkspace,
} from "../review/collect.js";
import type {
  ChangeSet,
  PlanStep,
  SoftwareFinding,
  SoftwareVerdict,
  SpecialistNote,
} from "./types.js";

type Args = {
  base: string;
  workspace: boolean;
  diffPath?: string;
  goal: string;
  requirements: string;
  paths: string[];
  json: boolean;
  help: boolean;
  planOnly: boolean;
};

function parseArgs(argv: string[]): Args {
  const args: Args = {
    base: "origin/master",
    workspace: false,
    goal: "",
    requirements: "",
    paths: [],
    json: false,
    help: false,
    planOnly: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === "--help" || a === "-h") args.help = true;
    else if (a === "--workspace") args.workspace = true;
    else if (a === "--json") args.json = true;
    else if (a === "--plan-only") args.planOnly = true;
    else if (a === "--base") {
      args.base = argv[++i] ?? args.base;
    } else if (a === "--diff") {
      args.diffPath = argv[++i];
    } else if (a === "--goal") {
      args.goal = argv[++i] ?? "";
    } else if (a === "--requirements") {
      args.requirements = argv[++i] ?? "";
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
  console.log(`gssc-langgraph software development bot

Run the agentic software_dev LangGraph (model-free): implementation plan +
software closeout checks inspired by gssc5 software agent / software-closeout-review.

Usage:
  bun run software [options] [paths...]

Options:
  --goal <text>           Development goal / task brief (recommended)
  --requirements <text>   Optional LLR / requirements excerpt
  --base <ref>            Git base ref (default: origin/master)
  --workspace             Structural scan of the working tree
  --diff <file>           Review a unified diff file
  --plan-only             Skip collecting a change set; plan from --goal only
  --json                  Emit machine-readable JSON
  -h, --help              Show help

Exit codes:
  0  PASS
  1  FAIL
  2  usage / runtime error

Peer: test development bot is a separate assistant (test_dev) — do not conflate.
`);
}

function formatFinding(f: SoftwareFinding): string {
  const loc = f.path ? `${f.path}: ` : "";
  const uid = f.uid ? ` [${f.uid}]` : "";
  const fix = f.fix ? `\n    fix: ${f.fix}` : "";
  return `  [${f.severity}] (${f.check})${uid} ${loc}${f.message}${fix}`;
}

function formatPlan(plan: PlanStep[]): string {
  return plan
    .map((s, i) => `  ${i + 1}. [${s.id}] ${s.title}\n     ${s.detail}`)
    .join("\n");
}

function toSoftwareChangeSet(cs: {
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

async function runSoftware(input: {
  goal: string;
  requirements: string;
  cs: ChangeSet | null;
}): Promise<{
  verdict: SoftwareVerdict;
  summary: string;
  findings: SoftwareFinding[];
  checksRun: string[];
  steps: string[];
  plan: PlanStep[];
  specialistNotes: SpecialistNote[];
}> {
  const files: Record<string, string> = {};
  const fileStatuses: Record<
    string,
    "added" | "modified" | "deleted" | "unchanged"
  > = {};
  if (input.cs) {
    for (const f of input.cs.files) {
      if (f.content !== undefined) files[f.path] = f.content;
      fileStatuses[f.path] = f.status;
    }
  }

  // One-shot CLI: fresh thread_id. Reuse a stable id for multi-turn memory.
  const result = await graph.invoke(
    {
      goal: input.goal,
      requirements: input.requirements,
      diff: input.cs?.diff ?? "",
      files,
      fileStatuses,
      label: input.cs?.label ?? "",
      changeSet: input.cs,
    },
    threadConfig(`software-cli-${crypto.randomUUID()}`),
  );

  const verdict = (result.verdict || "FAIL") as SoftwareVerdict;
  return {
    verdict,
    summary: result.summary || verdict,
    findings: result.findings ?? [],
    checksRun: result.checksRun ?? [],
    steps: result.steps ?? [],
    plan: result.plan ?? [],
    specialistNotes: result.specialistNotes ?? [],
  };
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    process.exit(0);
  }

  const root = resolve(process.cwd());
  let cs: ChangeSet | null = null;

  try {
    if (args.planOnly) {
      cs = null;
    } else if (args.diffPath) {
      const diff = await readFile(resolve(root, args.diffPath), "utf8");
      cs = toSoftwareChangeSet(
        await collectFromDiff(root, diff, `diff ${args.diffPath}`),
      );
    } else if (args.workspace) {
      cs = toSoftwareChangeSet(await collectWorkspace(root));
    } else if (args.paths.length > 0) {
      cs = toSoftwareChangeSet(await collectPaths(root, args.paths));
    } else if (args.goal && !args.diffPath) {
      // Goal + best-effort git range; fall back to plan-only if git fails.
      try {
        cs = toSoftwareChangeSet(await collectGitDiff(root, args.base));
      } catch {
        try {
          cs = toSoftwareChangeSet(await collectGitDiff(root, "master"));
        } catch {
          cs = null;
        }
      }
    } else {
      try {
        cs = toSoftwareChangeSet(await collectGitDiff(root, args.base));
      } catch {
        try {
          cs = toSoftwareChangeSet(await collectGitDiff(root, "master"));
        } catch {
          cs = toSoftwareChangeSet(await collectWorkspace(root));
        }
      }
    }
  } catch (err) {
    console.error("Failed to collect change set:", err);
    process.exit(2);
  }

  const report = await runSoftware({
    goal: args.goal,
    requirements: args.requirements,
    cs,
  });

  if (args.json) {
    console.log(
      JSON.stringify(
        {
          verdict: report.verdict,
          summary: report.summary,
          goal: args.goal,
          label: cs?.label ?? "plan-only",
          plan: report.plan,
          checksRun: report.checksRun,
          findings: report.findings,
          specialistNotes: report.specialistNotes,
          steps: report.steps,
        },
        null,
        2,
      ),
    );
  } else {
    console.log(`software_dev — ${cs?.label ?? "plan-only"}`);
    if (args.goal) console.log(`goal: ${args.goal}`);
    console.log(report.summary);
    console.log("plan:");
    console.log(formatPlan(report.plan));
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
