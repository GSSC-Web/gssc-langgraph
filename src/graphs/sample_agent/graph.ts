/**
 * Sample single-step agent graph.
 *
 * Intentionally model-free so local `bun run dev` works without API keys.
 * Domain graphs that need an LLM should use the shared helper under `src/llm`
 * (xAI / Grok by default) — keep this smoke assistant free of provider clients.
 *
 * Compiled with MemorySaver so multi-turn clients can pass `thread_id` and
 * accumulate reducer state (e.g. `steps`) across runs. See `src/checkpoint`.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import type { RunnableConfig } from "@langchain/core/runnables";
import { compileWithMemory } from "../../checkpoint/index.js";

const AgentState = Annotation.Root({
  message: Annotation<string>(),
  reply: Annotation<string>(),
  steps: Annotation<string[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
});

type SampleConfig = RunnableConfig<{ replyPrefix?: string }>;

const respond = async (
  state: typeof AgentState.State,
  config: SampleConfig,
): Promise<typeof AgentState.Update> => {
  const prefix = config.configurable?.replyPrefix ?? "gssc-sample";
  const text = (state.message ?? "").trim() || "(empty message)";
  return {
    reply: `[${prefix}] received: ${text}`,
    steps: ["respond"],
  };
};

const builder = new StateGraph(AgentState)
  .addNode("respond", respond)
  .addEdge("__start__", "respond");

export const graph = compileWithMemory(builder, { name: "GSSC Sample Agent" });
