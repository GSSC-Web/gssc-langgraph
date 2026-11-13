import { describe, expect, test } from "bun:test";
import { graph as reviewGraph } from "../src/graphs/service_review/graph.js";
import {
  checkGraphQuality,
  checkGssc5Contract,
  checkRegistry,
  checkSecrets,
  checkStack,
  checkTests,
  verdictFrom,
} from "../src/review/checks.js";
import { collectWorkspace } from "../src/review/collect.js";
import type { ChangeSet } from "../src/review/types.js";

describe("service_review graph", () => {
  test("is compiled", () => {
    expect(reviewGraph).toBeDefined();
    expect(reviewGraph.name).toBe("GSSC Service Review");
  });

  test("PASSes current workspace", async () => {
    const cs = await collectWorkspace(process.cwd());
    const result = await reviewGraph.invoke({
      label: cs.label,
      changeSet: cs,
      files: Object.fromEntries(
        cs.files
          .filter((f) => f.content !== undefined)
          .map((f) => [f.path, f.content!]),
      ),
    });
    expect(result.verdict).toBe("PASS");
    expect(result.checksRun).toContain("registry");
    expect(result.checksRun).toContain("secrets");
    expect(result.steps).toContain("verdict");
  });

  test("FAILs when a new graph is unregistered", async () => {
    const cs: ChangeSet = {
      label: "diff",
      files: [
        {
          path: "src/graphs/orphan/graph.ts",
          status: "added",
          content: `
import { Annotation, StateGraph } from "@langchain/langgraph";
const S = Annotation.Root({ x: Annotation<string>() });
const builder = new StateGraph(S).addNode("n", async () => ({ x: "1" })).addEdge("__start__", "n");
export const graph = builder.compile();
graph.name = "Orphan";
`,
        },
        {
          path: "langgraph.json",
          status: "unchanged",
          content: JSON.stringify({
            graphs: {
              health: "./src/graphs/health/graph.ts:graph",
              sample_agent: "./src/graphs/sample_agent/graph.ts:graph",
            },
          }),
        },
      ],
    };
    const findings = [
      ...checkRegistry(cs),
      ...checkGraphQuality(cs),
      ...checkTests(cs),
    ];
    expect(findings.some((f) => f.check === "registry")).toBe(true);
    expect(verdictFrom(findings)).toBe("FAIL");
  });

  test("FAILs on python stack files", () => {
    const findings = checkStack({
      label: "diff",
      files: [{ path: "pyproject.toml", status: "added", content: "[project]\nname='x'\n" }],
    });
    expect(findings.some((f) => f.severity === "error")).toBe(true);
  });

  test("FAILs when baseline assistant removed", () => {
    const findings = checkGssc5Contract({
      label: "diff",
      files: [
        {
          path: "langgraph.json",
          status: "modified",
          content: JSON.stringify({
            graphs: { sample_agent: "./src/graphs/sample_agent/graph.ts:graph" },
          }),
          patch: `-  "health": "./src/graphs/health/graph.ts:graph",\n`,
        },
      ],
    });
    expect(
      findings.some(
        (f) => f.check === "gssc5_contract" && f.message.includes("health"),
      ),
    ).toBe(true);
  });

  test("FAILs on secret-like tokens", () => {
    // Build at runtime so this test file itself does not look like a committed secret.
    const token = ["sk-", "abcdefghijklmnopqrstuvwxyz", "123456"].join("");
    const findings = checkSecrets({
      label: "diff",
      files: [
        {
          path: "src/graphs/leaky/graph.ts",
          status: "added",
          content: `const k = "${token}";\n`,
        },
      ],
    });
    expect(findings.some((f) => f.check === "secrets")).toBe(true);
  });
});
