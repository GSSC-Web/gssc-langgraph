import { describe, expect, test } from "bun:test";
import { graph as healthGraph } from "../src/graphs/health/graph.js";
import { graph as sampleAgentGraph } from "../src/graphs/sample_agent/graph.js";
import {
  compileWithMemory,
  threadConfig,
} from "../src/checkpoint/index.js";
import { Annotation, StateGraph } from "@langchain/langgraph";

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
    // MemorySaver requires configurable.thread_id on every invoke.
    const result = await sampleAgentGraph.invoke(
      { message: "hello from gssc5" },
      threadConfig(`sample-echo-${crypto.randomUUID()}`),
    );
    expect(result.reply).toContain("hello from gssc5");
    expect(result.steps).toEqual(["respond"]);
  });

  test("persists reducer state across turns with the same thread_id", async () => {
    const config = threadConfig(`sample-multi-${crypto.randomUUID()}`);

    const first = await sampleAgentGraph.invoke(
      { message: "turn-one" },
      config,
    );
    expect(first.reply).toContain("turn-one");
    expect(first.steps).toEqual(["respond"]);

    const second = await sampleAgentGraph.invoke(
      { message: "turn-two" },
      config,
    );
    expect(second.reply).toContain("turn-two");
    // `steps` uses an append reducer — MemorySaver keeps prior turn values.
    expect(second.steps).toEqual(["respond", "respond"]);

    const snapshot = await sampleAgentGraph.getState(config);
    expect(snapshot.values.steps).toEqual(["respond", "respond"]);
    expect(snapshot.values.reply).toContain("turn-two");
  });

  test("isolates state across different thread_ids", async () => {
    const a = threadConfig(`sample-a-${crypto.randomUUID()}`);
    const b = threadConfig(`sample-b-${crypto.randomUUID()}`);

    await sampleAgentGraph.invoke({ message: "only-a" }, a);
    const resultB = await sampleAgentGraph.invoke({ message: "only-b" }, b);

    expect(resultB.steps).toEqual(["respond"]);
    expect(resultB.reply).toContain("only-b");
    expect(resultB.reply).not.toContain("only-a");
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
