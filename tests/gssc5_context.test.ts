import { describe, expect, test } from "bun:test";
import { join } from "node:path";
import {
  createLoadGssc5ContextNode,
  formatGssc5Context,
  isGssc5Root,
  listMemories,
  listSkills,
  loadGssc5Context,
  loadGssc5ContextForRole,
  parseFrontmatter,
  resolveGssc5Root,
  selectAndLoad,
  tokenize,
} from "../src/gssc5/index.js";
import { graph as softwareGraph } from "../src/graphs/software_dev/graph.js";
import { graph as testDevGraph } from "../src/graphs/test_development/graph.js";

const FIXTURE_ROOT = join(import.meta.dir, "fixtures", "gssc5");

describe("gssc5 root resolution", () => {
  test("detects fixture as gssc5 root", () => {
    expect(isGssc5Root(FIXTURE_ROOT)).toBe(true);
  });

  test("resolveGssc5Root honors override", () => {
    expect(resolveGssc5Root(FIXTURE_ROOT)).toBe(FIXTURE_ROOT);
  });

  test("resolveGssc5Root returns empty for nonsense", () => {
    const prev = process.env.GSSC5_ROOT;
    delete process.env.GSSC5_ROOT;
    try {
      expect(resolveGssc5Root("/tmp/does-not-exist-gssc5-xyz")).toBe("");
    } finally {
      if (prev !== undefined) process.env.GSSC5_ROOT = prev;
    }
  });
});

describe("frontmatter + catalog", () => {
  test("parses folded description", () => {
    const raw = `---
id: sample
description: >-
  Line one
  line two
enabled: true
---

# Body
`;
    const parsed = parseFrontmatter(raw);
    expect(parsed.meta.id).toBe("sample");
    expect(String(parsed.meta.description)).toContain("Line one");
    expect(parsed.body.trim()).toBe("# Body");
  });

  test("lists fixture skills and memories", () => {
    const skills = listSkills(FIXTURE_ROOT);
    const memories = listMemories(FIXTURE_ROOT);
    expect(skills.map((s) => s.id)).toContain("software-closeout-review");
    expect(skills.map((s) => s.id)).toContain("test-closeout-review");
    expect(skills.map((s) => s.id)).toContain("kaneo-create-task");
    expect(memories.map((m) => m.id)).toContain("backend-arch");
    expect(memories.map((m) => m.id)).toContain("public-arch");
  });
});

describe("select / load relevance", () => {
  test("tokenize drops stopwords", () => {
    expect(tokenize("the software closeout for backend")).toEqual([
      "software",
      "closeout",
      "backend",
    ]);
  });

  test("software query prefers software-closeout + backend memory", () => {
    const { skills, memories, selected } = selectAndLoad(FIXTURE_ROOT, {
      query: "software closeout for backend elysia prisma",
      preferSkills: ["software-closeout-review"],
      preferMemories: ["backend-arch"],
      maxSkills: 2,
      maxMemories: 1,
    });
    expect(skills[0]?.id).toBe("software-closeout-review");
    expect(memories[0]?.id).toBe("backend-arch");
    expect(selected.some((s) => s.id === "software-closeout-review")).toBe(true);
    expect(skills[0]?.body).toContain("Software closeout review");
  });

  test("kaneo/defect query ranks kaneo-create-task", () => {
    const { skills } = selectAndLoad(FIXTURE_ROOT, {
      query: "create kaneo defect ticket for weekly scan",
      maxSkills: 1,
      maxMemories: 0,
    });
    expect(skills[0]?.id).toBe("kaneo-create-task");
  });

  test("requireSkills hard-includes even with weak query", () => {
    const { skills } = selectAndLoad(FIXTURE_ROOT, {
      query: "zzz",
      requireSkills: ["test-closeout-review"],
      maxSkills: 1,
      maxMemories: 0,
      minScore: 50,
    });
    expect(skills.map((s) => s.id)).toEqual(["test-closeout-review"]);
  });

  test("loadGssc5ContextForRole(software) requires closeout skill", () => {
    const bundle = loadGssc5ContextForRole("software", {
      root: FIXTURE_ROOT,
      query: "implement LLR in backend",
    });
    expect(bundle.root).toBe(FIXTURE_ROOT);
    expect(bundle.skills.some((s) => s.id === "software-closeout-review")).toBe(
      true,
    );
    expect(formatGssc5Context(bundle)).toContain("## Skill: software-closeout-review");
  });

  test("missing root yields empty bundle note", () => {
    const bundle = loadGssc5Context({
      root: "/tmp/missing-gssc5-root",
      query: "anything",
    });
    expect(bundle.skills).toEqual([]);
    expect(bundle.note).toContain("not found");
  });
});

describe("graph wiring", () => {
  test("createLoadGssc5ContextNode writes context fields", async () => {
    const node = createLoadGssc5ContextNode({
      role: "general",
      queryField: "message",
    });
    const out = await node(
      { message: "backend elysia software closeout" },
      { configurable: { gssc5Root: FIXTURE_ROOT } },
    );
    expect(out.gssc5Root).toBe(FIXTURE_ROOT);
    expect(out.gssc5Context?.skills.length).toBeGreaterThan(0);
    expect(out.steps).toEqual(["load_gssc5_context"]);
  });

  test("software_dev includes load_gssc5_context step", async () => {
    const result = await softwareGraph.invoke(
      { goal: "Add backend membership graph with elysia" },
      { configurable: { gssc5Root: FIXTURE_ROOT } },
    );
    expect(result.steps).toContain("load_gssc5_context");
    expect(
      result.gssc5Context?.skills.some((s) => s.id === "software-closeout-review"),
    ).toBe(true);
    expect(result.verdict).toBe("PASS");
  });

  test("test_development includes load_gssc5_context step", async () => {
    const result = await testDevGraph.invoke(
      {
        label: "test closeout",
        files: {
          "langgraph.json": JSON.stringify({
            graphs: { health: "./src/graphs/health/graph.ts:graph" },
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
      },
      { configurable: { gssc5Root: FIXTURE_ROOT } },
    );
    expect(result.steps).toContain("load_gssc5_context");
    expect(
      result.gssc5Context?.skills.some((s) => s.id === "test-closeout-review"),
    ).toBe(true);
  });
});
