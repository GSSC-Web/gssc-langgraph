import { describe, expect, test } from "bun:test";
import { graph as closeoutGraph } from "../src/graphs/closeout_review/graph.js";
import {
  checkContracts,
  checkScope,
  checkSoftwareMatch,
  checkSoftwareTrace,
  checkSecrets,
  checkThirdParty,
  verdictFrom,
} from "../src/closeout/checks.js";
import { BASELINE_ASSISTANT_IDS } from "../src/closeout/criteria.js";
import { collectWorkspace } from "../src/review/collect.js";
import type { ChangeSet } from "../src/closeout/types.js";

describe("closeout_review graph", () => {
  test("is compiled", () => {
    expect(closeoutGraph).toBeDefined();
    expect(closeoutGraph.name).toBe("GSSC Closeout Review");
  });

  test("baseline contract is health only (not sample_agent)", () => {
    expect([...BASELINE_ASSISTANT_IDS]).toEqual(["health"]);
    expect(BASELINE_ASSISTANT_IDS).not.toContain("sample_agent");
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
    const result = await closeoutGraph.invoke({
      label: cs.label,
      changeSet: cs,
      files: Object.fromEntries(
        cs.files
          .filter((f) => f.content !== undefined)
          .map((f) => [f.path, f.content!]),
      ),
    });
    expect(result.verdict).toBe("PASS");
    expect(result.checksRun).toContain("scope");
    expect(result.checksRun).toContain("contracts");
    expect(result.checksRun).toContain("secrets");
    expect(result.steps).toContain("verdict");
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
            },
          }),
        },
      ],
    };
    const findings = [
      ...checkSoftwareTrace(cs),
      ...checkSoftwareMatch(cs),
    ];
    expect(findings.some((f) => f.check === "software_trace")).toBe(true);
    expect(verdictFrom(findings)).toBe("FAIL");
  });

  test("does not require sample_agent in contracts", () => {
    const findings = checkContracts({
      label: "diff",
      files: [
        {
          path: "langgraph.json",
          status: "modified",
          content: JSON.stringify({
            graphs: {
              health: "./src/graphs/health/graph.ts:graph",
              closeout_review: "./src/graphs/closeout_review/graph.ts:graph",
            },
          }),
          patch: `-  "sample_agent": "./src/graphs/sample_agent/graph.ts:graph",\n`,
        },
      ],
    });
    expect(
      findings.some(
        (f) => f.uid === "sample_agent" || f.message.includes("sample_agent"),
      ),
    ).toBe(false);
    expect(verdictFrom(findings)).toBe("PASS");
  });

  test("FAILs when baseline health removed", () => {
    const findings = checkContracts({
      label: "diff",
      files: [
        {
          path: "langgraph.json",
          status: "modified",
          content: JSON.stringify({
            graphs: {
              closeout_review: "./src/graphs/closeout_review/graph.ts:graph",
            },
          }),
          patch: `-  "health": "./src/graphs/health/graph.ts:graph",\n`,
        },
      ],
    });
    expect(
      findings.some(
        (f) => f.check === "contracts" && f.message.includes("health"),
      ),
    ).toBe(true);
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

  test("FAILs on committed secret-looking keys", () => {
    // Assemble at runtime so this test file itself does not trip workspace secrets.
    const fakeKey = ["sk", "-", "abcdefghijklmnopqrstuvwxyz012345"].join("");
    const findings = checkSecrets({
      label: "diff",
      files: [
        {
          path: "src/oops.ts",
          status: "added",
          content: `const k = "${fakeKey}";\n`,
        },
      ],
    });
    expect(findings.some((f) => f.check === "secrets")).toBe(true);
  });

  test("scope errors when empty", () => {
    const findings = checkScope(null);
    expect(verdictFrom(findings)).toBe("FAIL");
  });
});
