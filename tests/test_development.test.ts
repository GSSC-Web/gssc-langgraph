import { describe, expect, test } from "bun:test";
import { graph as testDevGraph } from "../src/graphs/test_development/graph.js";
import {
  mapCoverage,
  resolveScope,
  runAnalysis,
  verdictFrom,
} from "../src/test_dev/analyze.js";
import { BASELINE_CONTRACTS, resolveContracts } from "../src/test_dev/contracts.js";
import { collectWorkspace } from "../src/review/collect.js";
import type { ChangeSet } from "../src/test_dev/types.js";

describe("test_development graph", () => {
  test("is compiled", () => {
    expect(testDevGraph).toBeDefined();
    expect(testDevGraph.name).toBe("GSSC Test Development");
  });

  test("invoke smoke — model-free", async () => {
    const result = await testDevGraph.invoke({
      label: "files",
      files: {
        "langgraph.json": JSON.stringify({
          graphs: {
            health: "./src/graphs/health/graph.ts:graph",
          },
        }),
        "src/graphs/health/graph.ts": `
import { Annotation, StateGraph } from "@langchain/langgraph";
const S = Annotation.Root({ status: Annotation<string>() });
export const graph = new StateGraph(S)
  .addNode("n", async () => ({ status: "ok" }))
  .addEdge("__start__", "n")
  .compile();
graph.name = "GSSC Health";
`,
        "tests/graphs.test.ts": `
import { describe, expect, test } from "bun:test";
import { graph as healthGraph } from "../src/graphs/health/graph.js";
describe("health graph", () => {
  test("returns ok", async () => {
    const result = await healthGraph.invoke({});
    expect(result.status).toBe("ok");
    expect(result.service).toBe("gssc-langgraph");
    expect(result.checkedAt).toBeTruthy();
  });
});
`,
      },
    });
    expect(result.steps).toContain("verdict");
    expect(result.checksRun).toContain("coverage_map");
    expect(result.verdict === "PASS" || result.verdict === "FAIL").toBe(true);
  });

  test("PASSes current workspace for baseline + tooling contracts", async () => {
    const cs = await collectWorkspace(process.cwd());
    const result = await testDevGraph.invoke({
      label: cs.label,
      changeSet: cs,
      files: Object.fromEntries(
        cs.files
          .filter((f) => f.content !== undefined)
          .map((f) => [f.path, f.content!]),
      ),
    });
    expect(result.verdict).toBe("PASS");
    expect(result.scopeGraphIds).toContain("health");
    expect(result.scopeGraphIds).toContain("test_development");
    expect(result.steps).toContain("verdict");
  });
});

describe("test_development analyzers", () => {
  test("maps baseline contracts from health tests", async () => {
    const cs = await collectWorkspace(process.cwd());
    const scope = resolveScope(cs);
    expect(scope.graphIds).toContain("health");
    const contracts = resolveContracts(cs, ["health"]);
    expect(contracts.length).toBeGreaterThanOrEqual(BASELINE_CONTRACTS.length);
    const { coverage, findings } = mapCoverage(cs, contracts);
    expect(coverage.every((c) => c.covered)).toBe(true);
    expect(findings.filter((f) => f.severity === "error")).toHaveLength(0);
  });

  test("FAILs when a scoped graph has no covering test", () => {
    const cs: ChangeSet = {
      label: "diff",
      files: [
        {
          path: "src/graphs/orphan_bot/graph.ts",
          status: "added",
          content: `
import { Annotation, StateGraph } from "@langchain/langgraph";
const S = Annotation.Root({ x: Annotation<string>() });
const builder = new StateGraph(S).addNode("n", async () => ({ x: "1" })).addEdge("__start__", "n");
export const graph = builder.compile();
graph.name = "Orphan Bot";
`,
        },
        {
          path: "langgraph.json",
          status: "modified",
          content: JSON.stringify({
            graphs: {
              orphan_bot: "./src/graphs/orphan_bot/graph.ts:graph",
            },
          }),
        },
      ],
    };
    const result = runAnalysis(cs);
    expect(result.scopeGraphIds).toContain("orphan_bot");
    expect(result.findings.some((f) => f.check === "coverage_map")).toBe(true);
    expect(verdictFrom(result.findings)).toBe("FAIL");
    expect(result.plan.some((p) => p.action === "add_test")).toBe(true);
  });
});
