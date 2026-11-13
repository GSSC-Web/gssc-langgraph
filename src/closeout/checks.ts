/**
 * Deterministic closeout checks for the closeout_review assistant.
 *
 * Mirrors gssc5 peer closeout skills (requirements / software / test) adapted
 * for this LangGraph Agent Server. No StrictDoc `@relation` audits.
 */
import {
  BASELINE_ASSISTANT_IDS,
  GRAPH_GOD_FILE_LINES,
  MODEL_FREE_ASSISTANT_IDS,
  REINVENTED_SERVER_HINTS,
  SECRET_PATTERNS,
} from "./criteria.js";
import type {
  ChangeSet,
  ChangedFile,
  CloseoutCheckId,
  CloseoutFinding,
} from "./types.js";

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

function changedGraphIds(cs: ChangeSet): string[] {
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "unchanged" && f.status !== "deleted") {
      ids.add(m[1]!);
    }
  }
  return [...ids].sort();
}

function graphDirsFromFiles(cs: ChangeSet): string[] {
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "deleted") ids.add(m[1]!);
  }
  return [...ids].sort();
}

function usesChatModel(body: string): boolean {
  return /ChatOpenAI|ChatAnthropic|ChatXAI|initChatModel|createChatModel|from\s+["']@langchain\/openai["']|from\s+["']@langchain\/anthropic["']|from\s+["']@langchain\/xai["']/.test(
    body,
  );
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
      body.toLowerCase().includes(graphId.replace(/_/g, " "))
    );
  });
}

/** Scope: need a reviewable change set (gssc5 Scope across peer skills). */
export function checkScope(cs: ChangeSet | null): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];
  if (!cs || cs.files.length === 0) {
    findings.push({
      check: "scope",
      severity: "error",
      message: "No change set — nothing in scope for closeout review",
      fix: "Pass a git range / --workspace / --diff / paths.",
    });
  }
  return findings;
}

/**
 * Contracts: requirements-closeout analogue — baseline assistants + docs stay
 * intact; no silent contract rewrites. Baseline is `health` only (`sample_agent`
 * is being removed in a parallel PR and must not be required).
 */
export function checkContracts(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];

  for (const f of cs.files) {
    if (f.path !== "langgraph.json") continue;
    const patch = f.patch ?? "";
    const content = f.content ?? "";
    for (const id of BASELINE_ASSISTANT_IDS) {
      if (patch) {
        const removed = new RegExp(`^-\\s*"${id}"\\s*:`, "m").test(patch);
        const added = new RegExp(`^\\+\\s*"${id}"\\s*:`, "m").test(patch);
        if (removed && !added) {
          findings.push({
            check: "contracts",
            severity: "error",
            path: "langgraph.json",
            uid: id,
            message: `Diff removes baseline assistant_id "${id}" (silent contract rewrite)`,
            fix: "Do not drop baseline assistants without explicit owner approval.",
          });
        }
      }
      if (content) {
        const parsed = parseLanggraphJson(content);
        if (parsed?.graphs && !(id in parsed.graphs)) {
          findings.push({
            check: "contracts",
            severity: "error",
            path: "langgraph.json",
            uid: id,
            message: `Baseline assistant_id "${id}" missing from registry`,
            fix: `Keep "${id}" registered or get owner approval to break the gssc5 contract.`,
          });
        }
      }
    }
  }

  if (cs.files.some((f) => f.path === "README.md" && f.status === "deleted")) {
    findings.push({
      check: "contracts",
      severity: "error",
      path: "README.md",
      message: "README deleted — would silently drop gssc5 contract docs",
      fix: "Restore README; update docs in place instead of deleting.",
    });
  }

  // Workspace / full registry: baseline must be present when langgraph.json is.
  if (cs.label === "workspace") {
    const lg = fileByPath(cs, "langgraph.json");
    const parsed = lg?.content ? parseLanggraphJson(lg.content) : null;
    if (parsed?.graphs) {
      for (const id of BASELINE_ASSISTANT_IDS) {
        if (!(id in parsed.graphs)) {
          findings.push({
            check: "contracts",
            severity: "error",
            path: "langgraph.json",
            uid: id,
            message: `Baseline assistant_id "${id}" missing from workspace registry`,
            fix: `Register "${id}" in langgraph.json.`,
          });
        }
      }
    }
  }

  return findings;
}

/** Software trace: registry ↔ graph files (Implementation @relation analogue). */
export function checkSoftwareTrace(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];
  const lg = fileByPath(cs, "langgraph.json");
  const raw = lg?.content ?? "";
  const parsed = raw ? parseLanggraphJson(raw) : null;
  const graphs = parsed?.graphs;

  if (lg?.status === "deleted") {
    findings.push({
      check: "software_trace",
      severity: "error",
      path: "langgraph.json",
      message: "langgraph.json was deleted",
      fix: "Restore langgraph.json and register all shipped graphs.",
    });
    return findings;
  }

  for (const id of changedGraphIds(cs)) {
    const graphPath = `src/graphs/${id}/graph.ts`;
    const added = cs.files.some(
      (f) => f.path === graphPath && f.status === "added",
    );
    if (added) {
      if (graphs && !(id in graphs)) {
        findings.push({
          check: "software_trace",
          severity: "error",
          path: graphPath,
          uid: id,
          message: `New assistant "${id}" is not registered in langgraph.json`,
          fix: `Add "${id}": "./src/graphs/${id}/graph.ts:graph" (gssc5 software-trace analogue).`,
        });
      }
      const readme = fileByPath(cs, "README.md");
      const readmeText = textOf(readme);
      if (readme && readme.status !== "deleted" && readmeText && !readmeText.includes(id)) {
        findings.push({
          check: "software_trace",
          severity: "warning",
          path: "README.md",
          uid: id,
          message: `New assistant "${id}" is not mentioned in README`,
          fix: "Document the assistant id and input shape for gssc5 consumers.",
        });
      } else if (!readmeText && added) {
        findings.push({
          check: "software_trace",
          severity: "info",
          path: "README.md",
          uid: id,
          message: `README not in change set — cannot verify docs for new assistant "${id}"`,
          fix: "Include README.md when adding assistants, or run --workspace.",
        });
      }
    }
  }

  if (cs.label === "workspace" && graphs) {
    for (const id of graphDirsFromFiles(cs)) {
      if (!(id in graphs)) {
        findings.push({
          check: "software_trace",
          severity: "error",
          path: `src/graphs/${id}/graph.ts`,
          uid: id,
          message: `Graph "${id}" exists on disk but is not registered`,
          fix: `Register "${id}" in langgraph.json.`,
        });
      }
    }
    for (const [id, entry] of Object.entries(graphs)) {
      const expected = `src/graphs/${id}/graph.ts`;
      const onDisk = cs.files.some(
        (f) =>
          (f.path === expected || f.path === `src/graphs/${id}/graph.tsx`) &&
          f.status !== "deleted",
      );
      if (!onDisk) {
        findings.push({
          check: "software_trace",
          severity: "error",
          path: "langgraph.json",
          uid: id,
          message: `Registry entry "${id}" → ${entry} has no matching graph file in workspace`,
          fix: `Add ${expected} or remove the orphan registry entry.`,
        });
      }
    }
  } else if (!raw && cs.files.some((f) => GRAPH_FILE_RE.test(f.path))) {
    findings.push({
      check: "software_trace",
      severity: "warning",
      path: "langgraph.json",
      message:
        "Graph files changed but langgraph.json content was not in the change set",
      fix: "Include langgraph.json when adding/renaming graphs, or run --workspace.",
    });
  }

  return findings;
}

/** Software match: real StateGraph assistants, not hollow stubs. */
export function checkSoftwareMatch(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (!m || f.status === "deleted") continue;
    const body = f.content ?? "";
    if (!body) continue;
    const id = m[1]!;

    const hasCompile =
      /\.compile\s*\(/.test(body) ||
      /\bcompileWithMemory\s*\(/.test(body) ||
      /\bcompileGraph\s*\(/.test(body);
    if (!/StateGraph\s*\(/.test(body) || !hasCompile) {
      findings.push({
        check: "software_match",
        severity: "error",
        path: f.path,
        uid: id,
        message: `Graph "${id}" does not look like a compiled StateGraph assistant`,
        fix: "Use Annotation + StateGraph + compile()/compileWithMemory like health/conversation.",
      });
    }
    if (!/export\s+const\s+graph\b/.test(body)) {
      findings.push({
        check: "software_match",
        severity: "error",
        path: f.path,
        uid: id,
        message: `Graph "${id}" must export compiled \`graph\` for Agent Server`,
        fix: "export const graph = builder.compile(); // or compileWithMemory(...)",
      });
    }
    if (/StateGraph\s*\(/.test(body) && !/\.addNode\s*\(/.test(body)) {
      findings.push({
        check: "software_match",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Graph "${id}" has no nodes — likely does not realize intended behavior`,
        fix: "Add at least one node that implements the closeout / domain behavior.",
      });
    }
  }
  return findings;
}

/** Software quality: fail-fast, size, graph.name, model-free smoke/tooling. */
export function checkSoftwareQuality(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];
  const modelFree = new Set<string>(MODEL_FREE_ASSISTANT_IDS);

  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (!m || f.status === "deleted") continue;
    const body = f.content ?? "";
    if (!body) continue;
    const id = m[1]!;
    const lines = body.split("\n").length;

    if (lines > GRAPH_GOD_FILE_LINES) {
      findings.push({
        check: "software_quality",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Graph module "${id}" is large (${lines} lines) — risk of god file`,
        fix: "Split checks/helpers into sibling modules under src/<domain>/.",
      });
    }

    if (/catch\s*\([^)]*\)\s*\{\s*\}/.test(body) || /catch\s*\{\s*\}/.test(body)) {
      findings.push({
        check: "software_quality",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Empty catch in "${id}" — prefer fail-fast or explicit handling`,
        fix: "Surface errors or rethrow; do not swallow failures silently.",
      });
    }

    const hasName =
      /graph\.name\s*=/.test(body) ||
      /\b(?:compile|compileWithMemory|compileGraph)\s*\(\s*[^)]*\bname\s*:/.test(
        body,
      );
    if (!hasName) {
      findings.push({
        check: "software_quality",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Graph "${id}" does not set graph.name`,
        fix: 'Set graph.name = "…" or compileWithMemory(builder, { name: "…" }).',
      });
    }

    if (modelFree.has(id) && usesChatModel(body)) {
      findings.push({
        check: "software_quality",
        severity: "error",
        path: f.path,
        uid: id,
        message: `Smoke/tooling assistant "${id}" should stay model-free`,
        fix: "Keep closeout/smoke assistants free of LLM nodes, or add a separate domain graph.",
      });
    }
  }
  return findings;
}

/** Third-party-first: LangGraph/Bun; flag reinvented servers / Python. */
export function checkThirdParty(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];
  const criteriaExclude = new Set([
    "src/closeout/criteria.ts",
    "src/software/criteria.ts",
    "src/review/criteria.ts",
  ]);

  for (const f of cs.files) {
    if (f.status === "deleted") continue;
    const body = textOf(f);

    if (
      f.path.endsWith(".py") ||
      f.path === "pyproject.toml" ||
      f.path === "requirements.txt"
    ) {
      findings.push({
        check: "third_party",
        severity: "error",
        path: f.path,
        message: "Python packaging / modules are out of stack policy",
        fix: "Keep this service TypeScript + Bun + LangGraph.js only.",
      });
    }

    if (
      (f.path.startsWith("src/") || f.path === "package.json") &&
      body &&
      !criteriaExclude.has(f.path)
    ) {
      for (const re of REINVENTED_SERVER_HINTS) {
        if (re.test(body)) {
          findings.push({
            check: "third_party",
            severity: "warning",
            path: f.path,
            message:
              "Custom HTTP framework detected — prefer @langchain/langgraph-cli Agent Server (third-party-first)",
            fix: "Serve via bun run dev / langgraph-cli unless the owner approved a custom server.",
          });
          break;
        }
      }
    }
  }

  const pkg = fileByPath(cs, "package.json");
  const pkgText = pkg?.content ?? "";
  if (pkgText) {
    if (!/"@langchain\/langgraph"/.test(pkgText)) {
      findings.push({
        check: "third_party",
        severity: "error",
        path: "package.json",
        message: "Missing adopted @langchain/langgraph dependency",
        fix: "Add @langchain/langgraph.",
      });
    }
    if (!/"packageManager"\s*:\s*"bun@/.test(pkgText)) {
      findings.push({
        check: "third_party",
        severity: "warning",
        path: "package.json",
        message: "packageManager is not pinned to bun",
        fix: 'Set "packageManager": "bun@…".',
      });
    }
  }

  return findings;
}

/** Test coverage: permanent bun:test per changed / workspace graph (Test @relation analogue). */
export function checkTestCoverage(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];
  const ids =
    cs.label === "workspace" ? graphDirsFromFiles(cs) : changedGraphIds(cs);

  for (const id of ids) {
    if (!hasTestTouching(cs, id)) {
      // Diff-only: tests may exist but not be in the change set.
      const anyTests = cs.files.some((f) => TEST_FILE_RE.test(f.path));
      if (cs.label === "workspace" || anyTests || changedGraphIds(cs).includes(id)) {
        findings.push({
          check: "test_coverage",
          severity: cs.label === "workspace" ? "error" : "warning",
          path: `src/graphs/${id}/graph.ts`,
          uid: id,
          message: `No bun:test coverage found for graph "${id}" in the change set`,
          fix: `Add or include tests/<name>.test.ts that imports/invokes graphs/${id} (test-closeout Trace analogue).`,
        });
      }
    }
  }
  return findings;
}

/**
 * Test target: asserts look intentional; do not delete covering tests while
 * editing SW (gssc5: fix wrong tests; ask if SW vs requirements conflict).
 */
export function checkTestTarget(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];

  for (const f of cs.files) {
    if (!TEST_FILE_RE.test(f.path) || f.status === "deleted") continue;
    const body = f.content ?? "";
    if (!body) continue;

    if (!/\bexpect\s*\(/.test(body)) {
      findings.push({
        check: "test_target",
        severity: "warning",
        path: f.path,
        message: "Test file has no expect(…) asserts — may not lock a contract",
        fix: "Assert documented contract behavior (status/reply/steps), not incidental SW.",
      });
    }
    if (/expect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)/.test(body)) {
      findings.push({
        check: "test_target",
        severity: "warning",
        path: f.path,
        message: "Tautological expect(true).toBe(true) — does not validate a contract",
        fix: "Assert the documented contract verb/status/body.",
      });
    }
  }

  const touchedGraphs = changedGraphIds(cs);
  if (touchedGraphs.length > 0) {
    const deletedTests = cs.files.filter(
      (f) => TEST_FILE_RE.test(f.path) && f.status === "deleted",
    );
    for (const t of deletedTests) {
      const body = `${t.patch ?? ""}\n${t.content ?? ""}`;
      const covers = touchedGraphs.some(
        (id) =>
          body.includes(`graphs/${id}/`) ||
          body.includes(`"${id}"`) ||
          body.toLowerCase().includes(id.replace(/_/g, " ")),
      );
      if (covers) {
        findings.push({
          check: "test_target",
          severity: "error",
          path: t.path,
          message:
            "Deleting tests that cover changed software — do not “fix” by removing coverage (ask if SW vs contracts conflict)",
          fix: "Restore or rewrite tests to assert the intended contract; peer with test_development for test planning.",
        });
      } else if (!body.trim()) {
        findings.push({
          check: "test_target",
          severity: "warning",
          path: t.path,
          message:
            "Test file deleted while graphs changed — confirm it was not covering the SW under edit",
          fix: "Include the deleted test contents in the change set, or restore coverage.",
        });
      }
    }
  }

  return findings;
}

/** Secrets: never commit real keys (gssc5 agents.md). */
export function checkSecrets(cs: ChangeSet): CloseoutFinding[] {
  const findings: CloseoutFinding[] = [];

  for (const f of cs.files) {
    if (f.status === "deleted") continue;
    const body = textOf(f);
    if (!body) continue;

    // .env.example must stay placeholder-only.
    if (f.path === ".env.example") {
      for (const { name, re } of SECRET_PATTERNS) {
        if (re.test(body)) {
          findings.push({
            check: "secrets",
            severity: "error",
            path: f.path,
            message: `.env.example looks like it contains a real ${name}`,
            fix: "Keep placeholders empty or clearly fake (e.g. xai-… truncated).",
          });
        }
      }
      continue;
    }

    // Skip lockfiles / this criteria module (pattern definitions).
    if (
      f.path.endsWith(".lock") ||
      f.path === "bun.lock" ||
      f.path === "src/closeout/criteria.ts" ||
      f.path === "src/review/criteria.ts"
    ) {
      continue;
    }

    for (const { name, re } of SECRET_PATTERNS) {
      if (re.test(body)) {
        findings.push({
          check: "secrets",
          severity: "error",
          path: f.path,
          message: `Possible committed secret (${name})`,
          fix: "Remove the secret; use .env (gitignored) and placeholders in .env.example.",
        });
        break;
      }
    }
  }

  return findings;
}

export const CHECK_RUNNERS: Record<
  CloseoutCheckId,
  (cs: ChangeSet | null) => CloseoutFinding[]
> = {
  scope: (cs) => checkScope(cs),
  contracts: (cs) => (cs ? checkContracts(cs) : []),
  software_trace: (cs) => (cs ? checkSoftwareTrace(cs) : []),
  software_match: (cs) => (cs ? checkSoftwareMatch(cs) : []),
  software_quality: (cs) => (cs ? checkSoftwareQuality(cs) : []),
  third_party: (cs) => (cs ? checkThirdParty(cs) : []),
  test_coverage: (cs) => (cs ? checkTestCoverage(cs) : []),
  test_target: (cs) => (cs ? checkTestTarget(cs) : []),
  secrets: (cs) => (cs ? checkSecrets(cs) : []),
};

export function verdictFrom(findings: CloseoutFinding[]): "PASS" | "FAIL" {
  return findings.some((f) => f.severity === "error") ? "FAIL" : "PASS";
}

export function summarize(
  verdict: "PASS" | "FAIL",
  findings: CloseoutFinding[],
): string {
  const errors = findings.filter((f) => f.severity === "error").length;
  const warnings = findings.filter((f) => f.severity === "warning").length;
  if (verdict === "PASS" && warnings === 0) {
    return "PASS — closeout review clean.";
  }
  if (verdict === "PASS") {
    return `PASS with ${warnings} warning(s).`;
  }
  return `FAIL — ${errors} error(s), ${warnings} warning(s).`;
}
