import { describe, expect, test } from "bun:test";
import { cpSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  createLoadGssc5ContextNode,
  checkoutGssc5ToCache,
  ensureGssc5Checkout,
  formatGssc5Context,
  isGssc5Root,
  listMemories,
  listSkills,
  loadGssc5Context,
  loadGssc5ContextForRole,
  looksLikeGitUrl,
  parseFrontmatter,
  resolveGssc5Root,
  selectAndLoad,
  tokenize,
  type GitRunner,
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

  test("GSSC5_ROOT must be a path, not a URL", () => {
    expect(looksLikeGitUrl("https://github.com/GSSC-Web/gssc5.git")).toBe(true);
    expect(looksLikeGitUrl("/abs/path/to/gssc5")).toBe(false);
    expect(resolveGssc5Root("https://github.com/GSSC-Web/gssc5.git")).toBe("");
  });
});

describe("gssc5 auto-checkout", () => {
  test("ensureGssc5Checkout rejects URL in root override", () => {
    const result = ensureGssc5Checkout({
      root: "https://github.com/GSSC-Web/gssc5.git",
      autoCheckout: false,
    });
    expect(result.root).toBe("");
    expect(result.note).toContain("filesystem path");
    expect(result.note).toContain("GSSC5_REPO_URL");
  });

  test("clones into cache when no local root (mock git)", () => {
    const cacheDir = mkdtempSync(join(tmpdir(), "gssc5-cache-"));
    const git: GitRunner = (args) => {
      if (args[0] === "clone") {
        const target = args[args.length - 1]!;
        mkdirSync(target, { recursive: true });
        cpSync(FIXTURE_ROOT, target, { recursive: true });
        // Minimal .git so later isGitRepo checks can pass if re-run.
        mkdirSync(join(target, ".git"), { recursive: true });
        writeFileSync(join(target, ".git", "HEAD"), "ref: refs/heads/master\n");
        return { status: 0, stdout: "", stderr: "" };
      }
      if (args[0] === "rev-parse") {
        return { status: 0, stdout: "true\n", stderr: "" };
      }
      return { status: 0, stdout: "", stderr: "" };
    };

    const prevRoot = process.env.GSSC5_ROOT;
    delete process.env.GSSC5_ROOT;
    try {
      const result = ensureGssc5Checkout({
        cacheDir,
        autoCheckout: true,
        git,
        // Force miss on sibling by using a cwd without ../gssc5
        cwd: cacheDir,
      });
      expect(result.source).toBe("cache");
      expect(result.root).toBe(join(cacheDir, "gssc5"));
      expect(isGssc5Root(result.root)).toBe(true);
      expect(existsSync(join(result.root, ".agents", "skills"))).toBe(true);
    } finally {
      if (prevRoot !== undefined) process.env.GSSC5_ROOT = prevRoot;
      rmSync(cacheDir, { recursive: true, force: true });
    }
  });

  test("updates existing cache checkout (mock fetch)", () => {
    const cacheDir = mkdtempSync(join(tmpdir(), "gssc5-cache-upd-"));
    const target = join(cacheDir, "gssc5");
    cpSync(FIXTURE_ROOT, target, { recursive: true });
    mkdirSync(join(target, ".git"), { recursive: true });
    writeFileSync(join(target, ".git", "HEAD"), "ref: refs/heads/master\n");

    const calls: string[][] = [];
    const git: GitRunner = (args) => {
      calls.push([...args]);
      if (args[0] === "rev-parse") {
        return { status: 0, stdout: "true\n", stderr: "" };
      }
      return { status: 0, stdout: "", stderr: "" };
    };

    // Exercise cache update directly — ensureGssc5Checkout would classify
    // <cache>/gssc5 as a local ./gssc5 sibling when cwd === cacheDir.
    const result = checkoutGssc5ToCache({
      cacheDir,
      git,
      cwd: cacheDir,
    });
    expect(result.root).toBe(target);
    expect(result.source).toBe("cache");
    expect(calls.some((c) => c[0] === "fetch")).toBe(true);
    rmSync(cacheDir, { recursive: true, force: true });
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
      autoCheckout: false,
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
