import { describe, expect, test } from "bun:test";
import { graph as healthGraph } from "../src/graphs/health/graph.js";
import { graph as sampleAgentGraph } from "../src/graphs/sample_agent/graph.js";

describe("health graph", () => {
  test("is compiled", () => {
    expect(healthGraph).toBeDefined();
    expect(healthGraph.name).toBe("GSSC Health");
  });

  test("returns ok", async () => {
    const result = await healthGraph.invoke({});
    expect(result.status).toBe("ok");
    expect(result.service).toBe("gssc-langgraph");
    expect(result.checkedAt).toBeTruthy();
  });
});

describe("sample_agent graph", () => {
  test("is compiled", () => {
    expect(sampleAgentGraph).toBeDefined();
    expect(sampleAgentGraph.name).toBe("GSSC Sample Agent");
  });

  test("echoes message", async () => {
    const result = await sampleAgentGraph.invoke({
      message: "hello from gssc5",
    });
    expect(result.reply).toContain("hello from gssc5");
    expect(result.steps).toEqual(["respond"]);
  });
});
