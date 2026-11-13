/**
 * Sample single-step agent graph.
 *
 * Intentionally model-free so local `bun run dev` works without API keys.
 * Replace `respond` with tool/LLM nodes when adding GSSC domain workflows.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import type { RunnableConfig } from "@langchain/core/runnables";

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

export const graph = builder.compile();
graph.name = "GSSC Sample Agent";
