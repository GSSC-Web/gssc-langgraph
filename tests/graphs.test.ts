import { describe, expect, test } from "bun:test";
import { graph as healthGraph } from "../src/graphs/health/graph.js";

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
