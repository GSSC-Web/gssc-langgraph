import {
  BASELINE_ASSISTANT_IDS,
  CUSTOM_SERVER_HINTS,
  SECRET_PATTERNS,
} from "./criteria.js";
import type { ChangeSet, ChangedFile, Finding, ReviewCheckId } from "./types.js";

const GRAPH_FILE_RE = /^src\/graphs\/([^/]+)\/graph\.tsx?$/;
const TEST_FILE_RE = /^tests\/.+\.test\.tsx?$/;

function fileByPath(cs: ChangeSet, path: string): ChangedFile | undefined {
  return cs.files.find((f) => f.path === path);
}

function textOf(file: ChangedFile | undefined): string {
  return file?.content ?? file?.patch ?? "";
}

function parseLanggraphJson(raw: string): {
  graphs?: Record<string, string>;
} | null {
  try {
    return JSON.parse(raw) as { graphs?: Record<string, string> };
  } catch {
    return null;
  }
}

function graphDirsFromFiles(cs: ChangeSet): string[] {
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "deleted") ids.add(m[1]!);
  }
  return [...ids].sort();
}

function changedGraphIds(cs: ChangeSet): string[] {
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "unchanged") ids.add(m[1]!);
  }
  return [...ids].sort();
}

function hasTestTouching(cs: ChangeSet, graphId: string): boolean {
  return cs.files.some((f) => {
    if (!TEST_FILE_RE.test(f.path) || f.status === "deleted") return false;
    const body = textOf(f);
    return (
      body.includes(`src/graphs/${graphId}/`) ||
      body.includes(`graphs/${graphId}/`) ||
      body.includes(`"${graphId}"`) ||
      body.includes(`'${graphId}'`) ||
      // common describe("health graph") style
      body.toLowerCase().includes(graphId.replace(/_/g, " "))
    );
  });
}

export function checkRegistry(cs: ChangeSet): Finding[] {
  const findings: Finding[] = [];
  const lg = fileByPath(cs, "langgraph.json");
  const raw = textOf(lg);
  if (!raw && lg?.status === "deleted") {
    findings.push({
      check: "registry",
      severity: "error",
      path: "langgraph.json",
      message: "langgraph.json was deleted",
      fix: "Restore langgraph.json and register all shipped graphs.",
    });
    return findings;
  }
  if (!raw) {
    // Workspace scans should always include it; diff-only reviews may omit.
    if (cs.files.some((f) => GRAPH_FILE_RE.test(f.path))) {
      findings.push({
        check: "registry",
        severity: "warning",
        path: "langgraph.json",
        message:
          "Graph files changed but langgraph.json content was not in the change set",
        fix: "Include langgraph.json when adding/renaming graphs, or run a workspace review.",
      });
    }
    return findings;
  }

  const parsed = parseLanggraphJson(
    lg?.content ?? (raw.trim().startsWith("{") ? raw : ""),
  );
  // When we only have a patch, try to recover full JSON from workspace-style content only.
  const graphs = parsed?.graphs;
  if (!graphs) {
    if (lg?.content) {
      findings.push({
        check: "registry",
        severity: "error",
        path: "langgraph.json",
        message: "langgraph.json is missing a valid graphs map",
        fix: 'Add a "graphs" object mapping assistant_id → "./src/graphs/<id>/graph.ts:graph".',
      });
    }
    return findings;
  }

  for (const [id, entry] of Object.entries(graphs)) {
    const expected = `./src/graphs/${id}/graph.ts:graph`;
    const alt = `./src/graphs/${id}/graph.tsx:graph`;
    if (entry !== expected && entry !== alt) {
      findings.push({
        check: "registry",
        severity: "warning",
        path: "langgraph.json",
        message: `Assistant "${id}" points to "${entry}" (expected ${expected})`,
        fix: "Keep registry paths aligned with src/graphs/<id>/graph.ts exports.",
      });
    }
    const graphFile = fileByPath(cs, `src/graphs/${id}/graph.ts`);
    const graphTsx = fileByPath(cs, `src/graphs/${id}/graph.tsx`);
    if (
      graphFile?.status === "deleted" ||
      (graphFile === undefined &&
        graphTsx === undefined &&
        cs.label === "workspace")
    ) {
      // Only error on missing file when we have a full workspace snapshot.
      if (cs.label === "workspace" && !graphFile && !graphTsx) {
        findings.push({
          check: "registry",
          severity: "error",
          path: "langgraph.json",
          message: `Registered assistant "${id}" has no src/graphs/${id}/graph.ts`,
          fix: "Add the graph module or remove the registry entry.",
        });
      }
    }
  }

  if (cs.label === "workspace") {
    for (const id of graphDirsFromFiles(cs)) {
      if (!(id in graphs)) {
        findings.push({
          check: "registry",
          severity: "error",
          path: `src/graphs/${id}/graph.ts`,
          message: `Graph "${id}" exists on disk but is not registered in langgraph.json`,
          fix: `Add "${id}": "./src/graphs/${id}/graph.ts:graph" to langgraph.json.`,
        });
      }
    }
  } else {
    for (const id of changedGraphIds(cs)) {
      const added = cs.files.some(
        (f) =>
          f.path === `src/graphs/${id}/graph.ts` && f.status === "added",
      );
      if (added && graphs && !(id in graphs)) {
        findings.push({
          check: "registry",
          severity: "error",
          path: `src/graphs/${id}/graph.ts`,
          message: `New graph "${id}" is not registered in langgraph.json`,
          fix: `Register "${id}" in langgraph.json graphs map.`,
        });
      }
    }
  }

  return findings;
}

export function checkGraphQuality(cs: ChangeSet): Finding[] {
  const findings: Finding[] = [];
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (!m || f.status === "deleted") continue;
    const body = f.content ?? "";
    if (!body) continue; // patch-only: light checks via patch below
    const id = m[1]!;

    if (!/Annotation\.Root/.test(body) && !/Annotation</.test(body)) {
      findings.push({
        check: "graph_quality",
        severity: "warning",
        path: f.path,
        message: `Graph "${id}" does not use LangGraph Annotation state`,
        fix: "Prefer Annotation.Root + StateGraph like health/sample_agent.",
      });
    }
    if (!/StateGraph\s*\(/.test(body)) {
      findings.push({
        check: "graph_quality",
        severity: "error",
        path: f.path,
        message: `Graph "${id}" does not construct a StateGraph`,
        fix: "Build the workflow with new StateGraph(...).",
      });
    }
    if (!/export\s+const\s+graph\b/.test(body)) {
      findings.push({
        check: "graph_quality",
        severity: "error",
        path: f.path,
        message: `Graph "${id}" must export compiled \`graph\``,
        fix: "export const graph = builder.compile();",
      });
    }
    if (!/\.compile\s*\(/.test(body)) {
      findings.push({
        check: "graph_quality",
        severity: "error",
        path: f.path,
        message: `Graph "${id}" never calls compile()`,
        fix: "Compile the StateGraph before export.",
      });
    }
    if (!/graph\.name\s*=/.test(body)) {
      findings.push({
        check: "graph_quality",
        severity: "warning",
        path: f.path,
        message: `Graph "${id}" does not set graph.name`,
        fix: 'Set graph.name = "…" for Studio / ops clarity.',
      });
    }

    const usesChatModel =
      /ChatOpenAI|ChatAnthropic|initChatModel|from\s+["']@langchain\/openai["']|from\s+["']@langchain\/anthropic["']/.test(
        body,
      );
    if (
      (id === "health" || id === "sample_agent") &&
      usesChatModel
    ) {
      findings.push({
        check: "graph_quality",
        severity: "error",
        path: f.path,
        message: `Smoke assistant "${id}" should stay model-free (no API key required)`,
        fix: "Keep health/sample_agent free of LLM nodes, or introduce a separate domain graph.",
      });
    }
  }
  return findings;
}

export function checkStack(cs: ChangeSet): Finding[] {
  const findings: Finding[] = [];

  for (const f of cs.files) {
    if (f.status === "deleted") continue;
    const body = textOf(f);

    if (
      f.path.endsWith(".py") ||
      f.path === "pyproject.toml" ||
      f.path === "requirements.txt"
    ) {
      findings.push({
        check: "stack",
        severity: "error",
        path: f.path,
        message: "Python LangGraph / Python packaging is out of stack policy",
        fix: "Keep this service TypeScript + Bun only.",
      });
    }

    if (
      (f.path.startsWith("src/") || f.path === "package.json") &&
      body &&
      f.path !== "src/review/criteria.ts"
    ) {
      for (const re of CUSTOM_SERVER_HINTS) {
        if (re.test(body)) {
          findings.push({
            check: "stack",
            severity: "warning",
            path: f.path,
            message:
              "Custom HTTP server framework detected; prefer @langchain/langgraph-cli Agent Server",
            fix: "Serve graphs via bun run dev / langgraph-cli unless the owner approved a custom server.",
          });
          break;
        }
      }
    }
  }

  const pkg = fileByPath(cs, "package.json");
  const pkgText = pkg?.content ?? "";
  if (pkgText) {
    if (!/"packageManager"\s*:\s*"bun@/.test(pkgText)) {
      findings.push({
        check: "stack",
        severity: "warning",
        path: "package.json",
        message: "packageManager is not pinned to bun",
        fix: 'Set "packageManager": "bun@…".',
      });
    }
    if (!/"@langchain\/langgraph"/.test(pkgText)) {
      findings.push({
        check: "stack",
        severity: "error",
        path: "package.json",
        message: "Missing @langchain/langgraph dependency",
        fix: "Add @langchain/langgraph.",
      });
    }
  }

  return findings;
}

export function checkGssc5Contract(cs: ChangeSet): Finding[] {
  const findings: Finding[] = [];
  const lg = fileByPath(cs, "langgraph.json");
  const raw = lg?.content ?? "";
  if (raw) {
    const parsed = parseLanggraphJson(raw);
    const graphs = parsed?.graphs ?? {};
    for (const id of BASELINE_ASSISTANT_IDS) {
      if (!(id in graphs)) {
        findings.push({
          check: "gssc5_contract",
          severity: "error",
          path: "langgraph.json",
          message: `Baseline assistant_id "${id}" missing from registry (gssc5 contract)`,
          fix: `Keep "${id}" registered or get explicit owner approval to break the contract.`,
        });
      }
    }
  }

  // Detect assistant id renames / deletions in diffs.
  for (const f of cs.files) {
    if (f.path !== "langgraph.json" || !f.patch) continue;
    for (const id of BASELINE_ASSISTANT_IDS) {
      const removed = new RegExp(`^-\\s*"${id}"\\s*:`, "m").test(f.patch);
      const added = new RegExp(`^\\+\\s*"${id}"\\s*:`, "m").test(f.patch);
      if (removed && !added) {
        findings.push({
          check: "gssc5_contract",
          severity: "error",
          path: "langgraph.json",
          message: `Diff removes baseline assistant_id "${id}"`,
          fix: "Do not remove baseline assistants without owner acknowledgment.",
        });
      }
    }
  }

  const sample = fileByPath(cs, "src/graphs/sample_agent/graph.ts");
  const sampleBody = sample?.content ?? "";
  if (sample && sampleBody && sample.status !== "deleted") {
    if (!/\bmessage\b/.test(sampleBody)) {
      findings.push({
        check: "gssc5_contract",
        severity: "error",
        path: sample.path,
        message:
          "sample_agent no longer exposes a `message` input field (README / gssc5 contract)",
        fix: "Keep `{ message: string }` input or update README + get owner approval.",
      });
    }
  }

  const readme = fileByPath(cs, "README.md");
  if (readme?.status === "deleted") {
    findings.push({
      check: "gssc5_contract",
      severity: "error",
      path: "README.md",
      message: "README deleted — gssc5 contract docs live there",
      fix: "Restore README contract section.",
    });
  }

  return findings;
}

export function checkTests(cs: ChangeSet): Finding[] {
  const findings: Finding[] = [];
  for (const id of changedGraphIds(cs)) {
    const graphPath = `src/graphs/${id}/graph.ts`;
    const graph = fileByPath(cs, graphPath);
    if (!graph || graph.status === "deleted" || graph.status === "unchanged") {
      continue;
    }
    // Prefer evidence from test files in the change set; for workspace, any test file counts.
    const coveredInChangeset = hasTestTouching(cs, id);
    if (!coveredInChangeset) {
      // If reviewing a diff that only touches the graph, require a test file change too.
      if (cs.diff || cs.label !== "workspace") {
        findings.push({
          check: "tests",
          severity: "error",
          path: graphPath,
          message: `Graph "${id}" changed without a matching test update`,
          fix: `Add or update tests under tests/ that invoke src/graphs/${id}/graph.ts.`,
        });
      } else {
        // workspace: look for any test file that mentions the graph
        const anyTest = cs.files.some(
          (f) =>
            TEST_FILE_RE.test(f.path) &&
            f.status !== "deleted" &&
            textOf(f).includes(`graphs/${id}/`),
        );
        if (!anyTest) {
          findings.push({
            check: "tests",
            severity: "error",
            path: graphPath,
            message: `Graph "${id}" has no bun:test coverage referencing it`,
            fix: `Add tests/<name>.test.ts covering ${id}.`,
          });
        }
      }
    }
  }
  return findings;
}

export function checkSecrets(cs: ChangeSet): Finding[] {
  const findings: Finding[] = [];
  for (const f of cs.files) {
    if (f.status === "deleted") continue;
    if (f.path === ".env" || /(^|\/)\.env$/.test(f.path)) {
      findings.push({
        check: "secrets",
        severity: "error",
        path: f.path,
        message: ".env files must not be committed",
        fix: "Keep secrets local; document keys in .env.example only.",
      });
    }
    const body = textOf(f);
    if (!body) continue;
    // Skip our own pattern definitions file for literal examples.
    if (f.path === "src/review/criteria.ts") continue;
    for (const { name, re } of SECRET_PATTERNS) {
      if (re.test(body)) {
        findings.push({
          check: "secrets",
          severity: "error",
          path: f.path,
          message: `Possible secret material detected (${name})`,
          fix: "Remove the secret; rotate if it was real; use env placeholders.",
        });
      }
    }
  }

  const example = fileByPath(cs, ".env.example");
  const exampleBody = example?.content ?? "";
  if (exampleBody) {
    for (const { name, re } of SECRET_PATTERNS) {
      if (re.test(exampleBody)) {
        findings.push({
          check: "secrets",
          severity: "error",
          path: ".env.example",
          message: `.env.example contains a real-looking secret (${name})`,
          fix: "Use empty values or obvious placeholders only.",
        });
      }
    }
  }

  return findings;
}

export const CHECK_RUNNERS: Record<
  ReviewCheckId,
  (cs: ChangeSet) => Finding[]
> = {
  registry: checkRegistry,
  graph_quality: checkGraphQuality,
  stack: checkStack,
  gssc5_contract: checkGssc5Contract,
  tests: checkTests,
  secrets: checkSecrets,
};

export function runAllChecks(cs: ChangeSet): Finding[] {
  return (Object.keys(CHECK_RUNNERS) as ReviewCheckId[]).flatMap((id) =>
    CHECK_RUNNERS[id](cs),
  );
}

export function verdictFrom(findings: Finding[]): "PASS" | "FAIL" {
  return findings.some((f) => f.severity === "error") ? "FAIL" : "PASS";
}

export function summarize(
  verdict: "PASS" | "FAIL",
  findings: Finding[],
): string {
  const errors = findings.filter((f) => f.severity === "error").length;
  const warnings = findings.filter((f) => f.severity === "warning").length;
  if (verdict === "PASS" && warnings === 0) {
    return "PASS — no findings.";
  }
  if (verdict === "PASS") {
    return `PASS with ${warnings} warning(s).`;
  }
  return `FAIL — ${errors} error(s), ${warnings} warning(s).`;
}
