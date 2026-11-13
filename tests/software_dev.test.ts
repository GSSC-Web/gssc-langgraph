import { describe, expect, test } from "bun:test";
import { graph as softwareGraph } from "../src/graphs/software_dev/graph.js";
import {
  checkDiscipline,
  checkMatch,
  checkScope,
  checkThirdParty,
  checkTrace,
  verdictFrom,
} from "../src/software/checks.js";
import { buildPlan } from "../src/software/plan.js";
import { collectWorkspace } from "../src/review/collect.js";
import type { ChangeSet } from "../src/software/types.js";

describe("software_dev graph", () => {
  test("is compiled", () => {
    expect(softwareGraph).toBeDefined();
    expect(softwareGraph.name).toBe("GSSC Software Dev");
  });

  test("PASSes current workspace closeout", async () => {
    const raw = await collectWorkspace(process.cwd());
    const cs: ChangeSet = {
      label: raw.label,
      diff: raw.diff,
      files: raw.files.map((f) => ({
        path: f.path,
        content: f.content,
        patch: f.patch,
        status: f.status,
      })),
    };
    const result = await softwareGraph.invoke({
      goal: "Close out current gssc-langgraph software",
      label: cs.label,
      changeSet: cs,
      files: Object.fromEntries(
        cs.files
          .filter((f) => f.content !== undefined)
          .map((f) => [f.path, f.content!]),
      ),
    });
    expect(result.verdict).toBe("PASS");
    expect(result.plan.length).toBeGreaterThan(0);
    expect(result.checksRun).toContain("scope");
    expect(result.checksRun).toContain("discipline");
    expect(result.steps).toContain("verdict");
  });

  test("plans from goal alone (plan-only)", async () => {
    const result = await softwareGraph.invoke({
      goal: "Add a new domain graph for membership lookups",
    });
    expect(result.verdict).toBe("PASS");
    expect(result.plan.some((s) => s.id === "scaffold_graph")).toBe(true);
    expect(result.plan.some((s) => s.id === "closeout")).toBe(true);
  });

  test("FAILs when new graph is unregistered", () => {
    const cs: ChangeSet = {
      label: "diff",
      files: [
        {
          path: "src/graphs/orphan/graph.ts",
          status: "added",
          content: `
import { Annotation, StateGraph } from "@langchain/langgraph";
const S = Annotation.Root({ x: Annotation<string>() });
const builder = new StateGraph(S)
  .addNode("n", async () => ({ x: "1" }))
  .addEdge("__start__", "n");
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
      ...checkTrace(cs),
      ...checkMatch(cs),
    ];
    expect(findings.some((f) => f.check === "trace")).toBe(true);
    expect(verdictFrom(findings)).toBe("FAIL");
  });

  test("FAILs on python stack files", () => {
    const findings = checkThirdParty({
      label: "diff",
      files: [
        {
          path: "pyproject.toml",
          status: "added",
          content: "[project]\nname='x'\n",
        },
      ],
    });
    expect(findings.some((f) => f.severity === "error")).toBe(true);
  });

  test("FAILs when baseline assistant removed", () => {
    const findings = checkDiscipline({
      label: "diff",
      files: [
        {
          path: "langgraph.json",
          status: "modified",
          content: JSON.stringify({
            graphs: {
              sample_agent: "./src/graphs/sample_agent/graph.ts:graph",
            },
          }),
          patch: `-  "health": "./src/graphs/health/graph.ts:graph",\n`,
        },
      ],
    });
    expect(
      findings.some(
        (f) => f.check === "discipline" && f.message.includes("health"),
      ),
    ).toBe(true);
  });

  test("scope errors when empty", () => {
    const findings = checkScope("", null);
    expect(verdictFrom(findings)).toBe("FAIL");
  });

  test("buildPlan mentions closeout and third_party", () => {
    const plan = buildPlan("fix health checkedAt", null);
    expect(plan.some((s) => s.id === "reproduce_fix")).toBe(true);
    expect(plan.some((s) => s.id === "third_party")).toBe(true);
    expect(plan.some((s) => s.id === "closeout")).toBe(true);
  });
});
