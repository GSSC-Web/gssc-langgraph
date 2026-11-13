import { describe, expect, test } from "bun:test";
import { Annotation, StateGraph } from "@langchain/langgraph";
import {
  compileWithMemory,
  threadConfig,
} from "../src/checkpoint/index.js";
import { graph as conversationGraph } from "../src/graphs/conversation/graph.js";
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

describe("conversation graph", () => {
  test("is compiled with MemorySaver", () => {
    expect(conversationGraph).toBeDefined();
    expect(conversationGraph.name).toBe("GSSC Conversation");
  });

  test("echoes message when thread_id is provided", async () => {
    const result = await conversationGraph.invoke(
      { message: "hello from gssc5" },
      threadConfig(`conversation-echo-${crypto.randomUUID()}`),
    );
    expect(result.reply).toContain("hello from gssc5");
    expect(result.steps).toEqual(["respond"]);
  });

  test("persists reducer state across turns with the same thread_id", async () => {
    const config = threadConfig(`conversation-multi-${crypto.randomUUID()}`);

    const first = await conversationGraph.invoke(
      { message: "turn-one" },
      config,
    );
    expect(first.reply).toContain("turn-one");
    expect(first.steps).toEqual(["respond"]);

    const second = await conversationGraph.invoke(
      { message: "turn-two" },
      config,
    );
    expect(second.reply).toContain("turn-two");
    // `steps` uses an append reducer — MemorySaver keeps prior turn values.
    expect(second.steps).toEqual(["respond", "respond"]);

    const snapshot = await conversationGraph.getState(config);
    expect(snapshot.values.steps).toEqual(["respond", "respond"]);
    expect(snapshot.values.reply).toContain("turn-two");
  });

  test("isolates state across different thread_ids", async () => {
    const a = threadConfig(`conversation-a-${crypto.randomUUID()}`);
    const b = threadConfig(`conversation-b-${crypto.randomUUID()}`);

    await conversationGraph.invoke({ message: "only-a" }, a);
    const resultB = await conversationGraph.invoke({ message: "only-b" }, b);

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
