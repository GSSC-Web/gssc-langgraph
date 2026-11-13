import { describe, expect, test } from "bun:test";
import { Annotation, StateGraph } from "@langchain/langgraph";
import { graph as healthGraph } from "../src/graphs/health/graph.js";
import {
  compileWithMemory,
  threadConfig,
} from "../src/checkpoint/index.js";

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

describe("compileWithMemory helper", () => {
  test("enables multi-turn persistence for a fresh graph", async () => {
    const State = Annotation.Root({
      n: Annotation<number>({
        reducer: (left, right) => (left ?? 0) + (right ?? 0),
        default: () => 0,
      }),
    });
    const builder = new StateGraph(State)
      .addNode("inc", async () => ({ n: 1 }))
      .addEdge("__start__", "inc");
    const graph = compileWithMemory(builder, { name: "checkpoint-smoke" });
    expect(graph.name).toBe("checkpoint-smoke");

    const config = threadConfig(`helper-${crypto.randomUUID()}`);
    await graph.invoke({}, config);
    const second = await graph.invoke({}, config);
    expect(second.n).toBe(2);
  });
});
