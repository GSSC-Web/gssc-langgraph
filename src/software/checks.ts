import {
  BASELINE_ASSISTANT_IDS,
  GRAPH_GOD_FILE_LINES,
  REINVENTED_SERVER_HINTS,
} from "./criteria.js";
import type {
  ChangeSet,
  ChangedFile,
  SoftwareCheckId,
  SoftwareFinding,
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

/** Scope: need a goal and/or a reviewable change set. */
export function checkScope(
  goal: string,
  cs: ChangeSet | null,
): SoftwareFinding[] {
  const findings: SoftwareFinding[] = [];
  const hasGoal = goal.trim().length > 0;
  const hasFiles = (cs?.files.length ?? 0) > 0;
  if (!hasGoal && !hasFiles) {
    findings.push({
      check: "scope",
      severity: "error",
      message:
        "No development goal and no change set — nothing to implement or close out",
      fix: "Pass --goal \"…\" and/or a git range / --workspace / --diff.",
    });
    return findings;
  }
  if (!hasGoal) {
    findings.push({
      check: "scope",
      severity: "info",
      message:
        "No free-text goal; running software closeout against the change set only",
    });
  }
  if (hasGoal && goal.trim().length < 8) {
    findings.push({
      check: "scope",
      severity: "warning",
      message: "Goal is very short — prefer a concrete LLR/task-style statement",
      fix: 'Example: --goal "Add software_dev assistant that plans LangGraph graph changes".',
    });
  }
  return findings;
}

/** Trace: new graphs registered + documented (adapted from Implementation @relation). */
export function checkTrace(cs: ChangeSet): SoftwareFinding[] {
  const findings: SoftwareFinding[] = [];
  const lg = fileByPath(cs, "langgraph.json");
  const raw = lg?.content ?? "";
  const parsed = raw ? parseLanggraphJson(raw) : null;
  const graphs = parsed?.graphs;

  for (const id of changedGraphIds(cs)) {
    const graphPath = `src/graphs/${id}/graph.ts`;
    const added = cs.files.some(
      (f) => f.path === graphPath && f.status === "added",
    );
    if (added) {
      if (graphs && !(id in graphs)) {
        findings.push({
          check: "trace",
          severity: "error",
          path: graphPath,
          uid: id,
          message: `New assistant "${id}" is not registered in langgraph.json`,
          fix: `Add "${id}": "./src/graphs/${id}/graph.ts:graph" (gssc5 software trace analogue).`,
        });
      }
      const readme = fileByPath(cs, "README.md");
      const readmeText = textOf(readme);
      if (readme && readme.status !== "deleted" && readmeText && !readmeText.includes(id)) {
        findings.push({
          check: "trace",
          severity: "warning",
          path: "README.md",
          uid: id,
          message: `New assistant "${id}" is not mentioned in README`,
          fix: "Document the assistant id and input shape for gssc5 consumers.",
        });
      } else if (!readmeText && added) {
        findings.push({
          check: "trace",
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
          check: "trace",
          severity: "error",
          path: `src/graphs/${id}/graph.ts`,
          uid: id,
          message: `Graph "${id}" exists on disk but is not registered`,
          fix: `Register "${id}" in langgraph.json.`,
        });
      }
    }
  }

  return findings;
}

/** Match: graphs look like real LangGraph assistants, not hollow stubs. */
export function checkMatch(cs: ChangeSet): SoftwareFinding[] {
  const findings: SoftwareFinding[] = [];
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
        check: "match",
        severity: "error",
        path: f.path,
        uid: id,
        message: `Graph "${id}" does not look like a compiled StateGraph assistant`,
        fix: "Use Annotation + StateGraph + compile()/compileWithMemory like health.",
      });
    }
    if (!/export\s+const\s+graph\b/.test(body)) {
      findings.push({
        check: "match",
        severity: "error",
        path: f.path,
        uid: id,
        message: `Graph "${id}" must export compiled \`graph\` for Agent Server`,
        fix: "export const graph = builder.compile(); // or compileWithMemory(...)",
      });
    }
    // Hollow stub: compile with zero addNode calls.
    if (/StateGraph\s*\(/.test(body) && !/\.addNode\s*\(/.test(body)) {
      findings.push({
        check: "match",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Graph "${id}" has no nodes — likely does not realize intended behavior`,
        fix: "Add at least one node that implements the goal.",
      });
    }
  }
  return findings;
}

/** Quality: fail-fast, size, model-free smoke assistants, graph.name. */
export function checkQuality(cs: ChangeSet): SoftwareFinding[] {
  const findings: SoftwareFinding[] = [];
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (!m || f.status === "deleted") continue;
    const body = f.content ?? "";
    if (!body) continue;
    const id = m[1]!;
    const lines = body.split("\n").length;

    if (lines > GRAPH_GOD_FILE_LINES) {
      findings.push({
        check: "quality",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Graph module "${id}" is large (${lines} lines) — risk of god file`,
        fix: "Split checks/helpers into sibling modules under src/<domain>/.",
      });
    }

    if (/catch\s*\([^)]*\)\s*\{\s*\}/.test(body) || /catch\s*\{\s*\}/.test(body)) {
      findings.push({
        check: "quality",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Empty catch in "${id}" — prefer fail-fast or explicit handling`,
        fix: "Surface errors or rethrow; do not swallow failures silently.",
      });
    }

    if (
      !/graph\.name\s*=/.test(body) &&
      !/\b(?:compile|compileWithMemory|compileGraph)\s*\(\s*[^)]*\bname\s*:/.test(
        body,
      )
    ) {
      findings.push({
        check: "quality",
        severity: "warning",
        path: f.path,
        uid: id,
        message: `Graph "${id}" does not set graph.name`,
        fix: 'Set graph.name = "…" or compileWithMemory(builder, { name: "…" }).',
      });
    }

    const usesChatModel =
      /ChatOpenAI|ChatAnthropic|initChatModel|from\s+["']@langchain\/openai["']|from\s+["']@langchain\/anthropic["']/.test(
        body,
      );
    if ((id === "health" || id === "conversation") && usesChatModel) {
      findings.push({
        check: "quality",
        severity: "error",
        path: f.path,
        uid: id,
        message: `Smoke assistant "${id}" should stay model-free`,
        fix: "Keep health/conversation free of LLM nodes, or add a separate domain graph.",
      });
    }
  }
  return findings;
}

/** Third-party-first: LangGraph/Bun; flag reinvented servers / Python. */
export function checkThirdParty(cs: ChangeSet): SoftwareFinding[] {
  const findings: SoftwareFinding[] = [];

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
      f.path !== "src/software/criteria.ts"
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

/**
 * Discipline: no silent baseline/contract drops; don't delete covering tests
 * while changing the graphs they cover (software must not chase broken tests
 * by removing them).
 */
export function checkDiscipline(cs: ChangeSet): SoftwareFinding[] {
  const findings: SoftwareFinding[] = [];

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
            check: "discipline",
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
            check: "discipline",
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
          check: "discipline",
          severity: "error",
          path: t.path,
          message:
            "Deleting tests that cover changed software — do not “fix” by removing coverage (ask if SW vs requirements conflict)",
          fix: "Restore or rewrite tests to assert the intended contract; peer with test_dev for test closeout.",
        });
      } else if (!body.trim()) {
        findings.push({
          check: "discipline",
          severity: "warning",
          path: t.path,
          message:
            "Test file deleted while graphs changed — confirm it was not covering the SW under edit",
          fix: "Include the deleted test contents in the change set, or restore coverage.",
        });
      }
    }
  }

  if (cs.files.some((f) => f.path === "README.md" && f.status === "deleted")) {
    findings.push({
      check: "discipline",
      severity: "error",
      path: "README.md",
      message: "README deleted — would silently drop gssc5 contract docs",
      fix: "Restore README; update docs in place instead of deleting.",
    });
  }

  return findings;
}

export const CHECK_RUNNERS: Record<
  SoftwareCheckId,
  (goal: string, cs: ChangeSet | null) => SoftwareFinding[]
> = {
  scope: (goal, cs) => checkScope(goal, cs),
  trace: (_goal, cs) => (cs ? checkTrace(cs) : []),
  match: (_goal, cs) => (cs ? checkMatch(cs) : []),
  quality: (_goal, cs) => (cs ? checkQuality(cs) : []),
  third_party: (_goal, cs) => (cs ? checkThirdParty(cs) : []),
  discipline: (_goal, cs) => (cs ? checkDiscipline(cs) : []),
};

export function verdictFrom(findings: SoftwareFinding[]): "PASS" | "FAIL" {
  return findings.some((f) => f.severity === "error") ? "FAIL" : "PASS";
}

export function summarize(
  verdict: "PASS" | "FAIL",
  findings: SoftwareFinding[],
  planCount: number,
): string {
  const errors = findings.filter((f) => f.severity === "error").length;
  const warnings = findings.filter((f) => f.severity === "warning").length;
  const planBit = `${planCount} plan step(s)`;
  if (verdict === "PASS" && warnings === 0) {
    return `PASS — ${planBit}, no findings.`;
  }
  if (verdict === "PASS") {
    return `PASS with ${warnings} warning(s) — ${planBit}.`;
  }
  return `FAIL — ${errors} error(s), ${warnings} warning(s) — ${planBit}.`;
}
